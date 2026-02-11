"""
Extraction Router - Pipeline execution and monitoring.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.session import get_db, get_session
from app.database.models.institution import Institution
from app.database.models.extraction_task import ExtractionTask

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_extraction_task(task_id: int, institution_id: int, user_id: int):
    """Execute extraction pipeline in background (sync, runs in thread)."""
    with get_session() as db:
        task = db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()
        if not task:
            return
        try:
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.flush()
            # TODO: Implement actual extraction via ProcessExtractor
            task.status = "finished"
            task.finished_at = datetime.utcnow()
            task.result_summary = {
                "total_processes": 0,
                "new_processes": 0,
                "new_documents": 0,
                "message": "Extraction pipeline placeholder",
            }
        except Exception as e:
            logger.error(f"Extraction task {task_id} failed: {e}")
            task.status = "failed"
            task.last_error = str(e)
            task.finished_at = datetime.utcnow()


@router.post("/institutions/{institution_id}/processes/extract")
async def start_extraction(
    institution_id: int = Path(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a full extraction pipeline for an institution."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    task = ExtractionTask(
        institution_id=institution_id,
        user_id=user.db_id,
        trigger_type="manual",
        status="pending",
    )
    db.add(task)
    await db.flush()

    background_tasks.add_task(_run_extraction_task, task.id, institution_id, user.db_id)
    return {
        "message": f"Extraction started (Task ID: {task.id})",
        "task_id": task.id,
        "status": "pending",
    }


@router.get("/extraction-tasks")
async def list_all_tasks(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all extraction tasks for the current user (all institutions)."""
    base = (
        select(ExtractionTask)
        .join(Institution, ExtractionTask.institution_id == Institution.id)
        .where(Institution.user_id == user.db_id)
    )
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one() or 0

    q = (
        select(ExtractionTask, Institution.name.label("institution_name"))
        .join(Institution, ExtractionTask.institution_id == Institution.id)
        .where(Institution.user_id == user.db_id)
        .order_by(ExtractionTask.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()

    tasks = []
    for t, inst_name in rows:
        tasks.append({
            "id": t.id,
            "institution_id": t.institution_id,
            "institution_name": inst_name,
            "status": t.status,
            "trigger_type": t.trigger_type,
            "total_processes": t.total_processes,
            "processed_processes": t.processed_processes,
            "result_summary": t.result_summary,
            "queued_at": t.queued_at.isoformat() if t.queued_at else None,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
        })
    return {"tasks": tasks, "total": total}


@router.get("/extraction-tasks/{task_id}")
async def get_task(
    task_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get extraction task status (must belong to user's institution)."""
    result = await db.execute(
        select(ExtractionTask)
        .join(Institution, ExtractionTask.institution_id == Institution.id)
        .where(ExtractionTask.id == task_id, Institution.user_id == user.db_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "institution_id": task.institution_id,
        "status": task.status,
        "trigger_type": task.trigger_type,
        "progress": {"total": task.total_processes, "processed": task.processed_processes},
        "result_summary": task.result_summary,
        "last_error": task.last_error,
        "queued_at": task.queued_at.isoformat() if task.queued_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


@router.get("/institutions/{institution_id}/extraction-tasks")
async def list_tasks(
    institution_id: int = Path(...),
    limit: int = Query(50, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List extraction tasks for an institution."""
    inst_result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    if not inst_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Institution not found")

    result = await db.execute(
        select(ExtractionTask)
        .where(ExtractionTask.institution_id == institution_id)
        .order_by(ExtractionTask.created_at.desc())
        .limit(limit)
    )
    tasks = result.scalars().all()
    return {
        "tasks": [
            {
                "id": t.id,
                "status": t.status,
                "trigger_type": t.trigger_type,
                "total_processes": t.total_processes,
                "queued_at": t.queued_at.isoformat() if t.queued_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }
