"""
Processes Router - CRUD and search for SEI processes.

Multi-tenant: processes are filtered by user's institutions.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.institution import Institution
from app.database.models.process import Process
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _process_to_dict(p: Process) -> dict:
    return {
        "id": p.id,
        "institution_id": p.institution_id,
        "process_number": p.process_number,
        "links": p.links,
        "best_current_link": p.best_current_link,
        "access_type": p.access_type,
        "category": p.category,
        "category_status": p.category_status,
        "unit": p.unit,
        "authority": p.authority,
        "no_valid_links": p.no_valid_links,
        "nickname": p.nickname,
        "documents_data": p.documents_data,
        "last_checked_at": p.last_checked_at.isoformat() if p.last_checked_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
async def list_processes(
    institution_id: Optional[int] = Query(None),
    access_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    category_status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List processes with filters. Scoped to user's institutions."""
    q = select(Process).join(Institution).where(Institution.user_id == user.db_id)
    if institution_id:
        q = q.where(Process.institution_id == institution_id)
    if access_type:
        q = q.where(Process.access_type == access_type)
    if category:
        q = q.where(Process.category == category)
    if category_status:
        q = q.where(Process.category_status == category_status)

    count_where = [Institution.user_id == user.db_id]
    if institution_id:
        count_where.append(Process.institution_id == institution_id)
    if access_type:
        count_where.append(Process.access_type == access_type)
    if category:
        count_where.append(Process.category == category)
    if category_status:
        count_where.append(Process.category_status == category_status)
    total = (await db.execute(
        select(func.count()).select_from(Process).join(Institution).where(*count_where)
    )).scalar_one() or 0

    q = q.order_by(Process.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = result.scalars().unique().all()
    return {
        "items": [_process_to_dict(p) for p in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/pending-categorization")
async def list_pending(
    institution_id: Optional[int] = Query(None),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List processes pending categorization."""
    q = select(Process).join(Institution).where(
        Institution.user_id == user.db_id,
        Process.category_status == "pendente",
    )
    if institution_id:
        q = q.where(Process.institution_id == institution_id)
    result = await db.execute(q)
    items = result.scalars().unique().all()
    return {"items": [_process_to_dict(p) for p in items], "total": len(items)}


@router.get("/{process_id}")
async def get_process(
    process_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get process by ID."""
    result = await db.execute(
        select(Process)
        .join(Institution)
        .where(Process.id == process_id, Institution.user_id == user.db_id)
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return _process_to_dict(process)


@router.get("/by-number/{process_number:path}")
async def get_by_number(
    process_number: str = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get process by number."""
    result = await db.execute(
        select(Process)
        .join(Institution)
        .where(Process.process_number == process_number, Institution.user_id == user.db_id)
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return _process_to_dict(process)


@router.post("", status_code=201)
async def create_process(
    data: dict = Body(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new process."""
    institution_id = data.get("institution_id")
    process_number = data.get("process_number")
    if not institution_id or not process_number:
        raise HTTPException(status_code=400, detail="institution_id and process_number required")

    inst_result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    if not inst_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Institution not found")

    existing = (await db.execute(select(Process).where(Process.process_number == process_number))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Process already exists")

    process = Process(
        institution_id=institution_id,
        process_number=process_number,
        links=data.get("links", {}),
        documents_data=data.get("documents_data", {}),
        extra_metadata=data.get("extra_metadata", {}),
    )
    db.add(process)
    await db.flush()
    return _process_to_dict(process)


@router.put("/{process_id}")
async def update_process(
    process_id: int = Path(...),
    data: dict = Body(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a process."""
    result = await db.execute(
        select(Process)
        .join(Institution)
        .where(Process.id == process_id, Institution.user_id == user.db_id)
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    allowed = {
        "access_type", "category", "category_status", "best_current_link",
        "unit", "authority", "no_valid_links", "nickname", "links",
        "documents_data", "extra_metadata",
    }
    for key, value in data.items():
        if key in allowed:
            setattr(process, key, value)
    await db.flush()
    return _process_to_dict(process)


@router.delete("/{process_id}", status_code=204)
async def delete_process(
    process_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a process."""
    result = await db.execute(
        select(Process)
        .join(Institution)
        .where(Process.id == process_id, Institution.user_id == user.db_id)
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    db.delete(process)


@router.post("/search")
async def search_processes(
    data: dict = Body(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search using ParadeDB BM25."""
    query_text = data.get("query", "")
    limit = min(data.get("limit", 20), 100)
    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")

    try:
        sql = text("""
            SELECT p.id, p.process_number, p.institution_id, p.authority,
                   p.category, p.access_type, p.nickname,
                   paradedb.score(p.id) as score
            FROM processes p
            JOIN institutions i ON p.institution_id = i.id
            WHERE i.user_id = :user_id
              AND p.process_number ||| :query
            ORDER BY score DESC
            LIMIT :limit
        """)
        result = await db.execute(sql, {"user_id": user.db_id, "query": query_text, "limit": limit})
        rows = result.fetchall()
        return {
            "results": [
                {
                    "id": r.id,
                    "process_number": r.process_number,
                    "institution_id": r.institution_id,
                    "authority": r.authority,
                    "category": r.category,
                    "access_type": r.access_type,
                    "nickname": r.nickname,
                    "score": float(r.score) if r.score else 0.0,
                }
                for r in rows
            ],
            "total": len(rows),
            "query": query_text,
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        q = (
            select(Process)
            .join(Institution)
            .where(
                Institution.user_id == user.db_id,
                Process.process_number.ilike(f"%{query_text}%"),
            )
            .limit(limit)
        )
        res = await db.execute(q)
        items = res.scalars().unique().all()
        return {
            "results": [_process_to_dict(p) for p in items],
            "total": len(items),
            "query": query_text,
        }
