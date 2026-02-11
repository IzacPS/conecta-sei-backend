"""
Documents Router - Document download management and Firebase Storage URLs.

All downloaded documents live in a Firebase Storage bucket.
The API never exposes raw bucket paths — instead it generates
short-lived signed URLs on demand.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.document import Document
from app.database.models.document_history import DocumentHistory
from app.database.models.institution import Institution
from app.database.models.process import Process
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/download")
async def request_download(
    data: dict = Body(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request document download (background task)."""
    process_id = data.get("process_id")
    if not process_id:
        raise HTTPException(status_code=400, detail="process_id required")
    # TODO: Implement background download task
    return {
        "task_id": f"download-{process_id}",
        "status": "pending",
        "message": "Download queued",
    }


@router.get("/download/{task_id}/status")
async def get_download_status(
    task_id: str = Path(...),
    user: UserInfo = Depends(get_current_user),
):
    """Check download task status."""
    return {
        "task_id": task_id,
        "status": "pending",
        "progress": {"total": 0, "completed": 0},
    }


@router.get("/history")
async def get_download_history(
    process_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document download history (only for current user's processes)."""
    base_where = [
        Institution.user_id == user.db_id,
    ]
    if process_id:
        base_where.append(DocumentHistory.process_id == process_id)

    count_q = (
        select(func.count())
        .select_from(DocumentHistory)
        .join(Process, DocumentHistory.process_id == Process.id)
        .join(Institution, Process.institution_id == Institution.id)
        .where(*base_where)
    )
    total = (await db.execute(count_q)).scalar_one() or 0

    q = (
        select(DocumentHistory)
        .join(Process, DocumentHistory.process_id == Process.id)
        .join(Institution, Process.institution_id == Institution.id)
        .where(*base_where)
        .order_by(DocumentHistory.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    items = result.scalars().unique().all()

    process_ids = list({h.process_id for h in items})
    inst_by_process = {}
    if process_ids:
        proc_result = await db.execute(select(Process).where(Process.id.in_(process_ids)))
        procs = proc_result.scalars().all()
        inst_by_process = {p.id: p.institution_id for p in procs}

    return {
        "items": [
            {
                "id": h.id,
                "process_id": h.process_id,
                "institution_id": inst_by_process.get(h.process_id),
                "document_number": h.document_number,
                "action": h.action,
                "old_status": h.old_status,
                "new_status": h.new_status,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None,
                "extra_metadata": h.extra_metadata,
            }
            for h in items
        ],
        "total": total,
    }


@router.get("/by-process/{process_id}/urls")
async def get_process_document_urls(
    process_id: int = Path(..., description="Process PK"),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return download URLs for all downloaded documents of a process."""
    proc_result = await db.execute(
        select(Process)
        .join(Institution, Process.institution_id == Institution.id)
        .where(Process.id == process_id, Institution.user_id == user.db_id)
    )
    process = proc_result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")

    docs_result = await db.execute(
        select(Document).where(
            Document.process_id == process_id,
            Document.storage_path.isnot(None),
        )
    )
    docs = docs_result.scalars().all()

    from app.utils.storage_service import get_download_url

    items = []
    for doc in docs:
        url = get_download_url(doc.storage_path)
        items.append({
            "document_id": doc.id,
            "document_number": doc.document_number,
            "document_type": doc.document_type,
            "status": doc.status,
            "storage_path": doc.storage_path,
            "download_url": url,
        })
    return {"process_id": process_id, "documents": items, "total": len(items)}


@router.get("/{document_id}/url")
async def get_document_download_url(
    document_id: int = Path(..., description="Document PK"),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a temporary signed download URL for a document in Firebase Storage."""
    result = await db.execute(
        select(Document)
        .join(Process, Document.process_id == Process.id)
        .join(Institution, Process.institution_id == Institution.id)
        .where(Document.id == document_id, Institution.user_id == user.db_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.storage_path:
        raise HTTPException(
            status_code=404,
            detail="Document has not been downloaded to storage yet",
        )
    from app.utils.storage_service import get_download_url
    url = get_download_url(doc.storage_path)
    if not url:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate download URL from Firebase Storage",
        )
    return {
        "document_id": doc.id,
        "document_number": doc.document_number,
        "download_url": url,
        "storage_path": doc.storage_path,
    }


@router.delete("/download/{task_id}")
async def cancel_download(
    task_id: str = Path(...),
    user: UserInfo = Depends(get_current_user),
):
    """Cancel a download task."""
    return {"task_id": task_id, "status": "cancelled"}
