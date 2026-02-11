"""
Pipeline Stages Router - Modular pipeline execution.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.session import get_db, get_session
from app.database.models.institution import Institution
from app.database.models.extraction_task import ExtractionTask

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_institution(db: AsyncSession, institution_id: int, user: UserInfo) -> Institution:
    """Verify institution belongs to user."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst


async def _create_task(
    db: AsyncSession,
    institution_id: int,
    user: UserInfo,
    stage: str,
) -> ExtractionTask:
    """Create extraction task for a specific stage."""
    task = ExtractionTask(
        institution_id=institution_id,
        user_id=user.db_id,
        trigger_type="manual",
        status="pending",
        result_summary={"stage": stage},
    )
    db.add(task)
    await db.flush()
    return task


def _get_task_status_sync(task_id: int) -> dict | None:
    """Sync helper to poll task status (run in thread to avoid blocking)."""
    with get_session() as poll_db:
        task = poll_db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()
        if not task:
            return None
        return {
            "status": task.status,
            "total_processes": task.total_processes,
            "processed_processes": task.processed_processes,
            "result_summary": task.result_summary,
            "last_error": task.last_error,
        }


@router.post("/institutions/{institution_id}/pipeline/discover")
async def stage_discover(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stage 1: Process Discovery - fast table scrape."""
    await _verify_institution(db, institution_id, user)
    task = await _create_task(db, institution_id, user, "discover")
    task.status = "pending"
    await db.flush()
    return {
        "task_id": task.id,
        "stage": "discover",
        "status": "pending",
        "message": "Stage 1 (Process Discovery) queued",
    }


@router.post("/institutions/{institution_id}/pipeline/validate")
async def stage_validate(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stage 2: Link Validation."""
    await _verify_institution(db, institution_id, user)
    task = await _create_task(db, institution_id, user, "validate")
    task.status = "pending"
    await db.flush()
    return {
        "task_id": task.id,
        "stage": "validate",
        "status": "pending",
        "message": "Stage 2 (Link Validation) queued",
    }


@router.post("/institutions/{institution_id}/pipeline/documents")
async def stage_documents(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stage 3: Document Discovery."""
    await _verify_institution(db, institution_id, user)
    task = await _create_task(db, institution_id, user, "documents")
    task.status = "pending"
    await db.flush()
    return {
        "task_id": task.id,
        "stage": "documents",
        "status": "pending",
        "message": "Stage 3 (Document Discovery) queued",
    }


@router.post("/institutions/{institution_id}/pipeline/download")
async def stage_download(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stage 4: Document Download."""
    await _verify_institution(db, institution_id, user)
    task = await _create_task(db, institution_id, user, "download")
    task.status = "pending"
    await db.flush()
    return {
        "task_id": task.id,
        "stage": "download",
        "status": "pending",
        "message": "Stage 4 (Document Download) queued",
    }


@router.post("/institutions/{institution_id}/pipeline/full")
async def stage_full(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full Pipeline - all stages sequentially."""
    await _verify_institution(db, institution_id, user)
    task = await _create_task(db, institution_id, user, "full")
    task.status = "pending"
    await db.flush()
    return {
        "task_id": task.id,
        "stage": "full",
        "status": "pending",
        "message": "Full pipeline queued (Stages 1-4)",
    }


@router.get("/institutions/{institution_id}/pipeline/progress/{task_id}")
async def stream_progress(
    institution_id: int = Path(...),
    task_id: int = Path(...),
    request: Request = None,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time pipeline progress."""
    await _verify_institution(db, institution_id, user)

    async def event_generator():
        last_status = None
        last_processed = -1
        while True:
            if request and await request.is_disconnected():
                break
            task_data = await asyncio.to_thread(_get_task_status_sync, task_id)
            if task_data is None:
                yield f"event: error\ndata: {json.dumps({'message': 'Task not found'})}\n\n"
                break
            if task_data["status"] != last_status:
                last_status = task_data["status"]
                yield f"event: status\ndata: {json.dumps({'status': task_data['status'], 'task_id': task_id})}\n\n"
            if task_data["processed_processes"] != last_processed:
                last_processed = task_data["processed_processes"]
                yield f"event: progress\ndata: {json.dumps({'total': task_data['total_processes'], 'processed': task_data['processed_processes']})}\n\n"
            if task_data["status"] in ("finished", "failed"):
                summary = task_data.get("result_summary") or {}
                if task_data["status"] == "finished":
                    yield f"event: complete\ndata: {json.dumps({'summary': summary})}\n\n"
                else:
                    yield f"event: error\ndata: {json.dumps({'message': task_data.get('last_error') or 'Unknown error'})}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
