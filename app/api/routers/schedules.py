"""
Schedules Router - APScheduler configuration for automated extractions.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.extraction_schedule import ExtractionSchedule
from app.database.models.institution import Institution
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _schedule_to_dict(s: ExtractionSchedule) -> dict:
    return {
        "id": s.id,
        "institution_id": s.institution_id,
        "schedule_type": s.schedule_type,
        "interval_minutes": s.interval_minutes,
        "cron_hour": s.cron_hour,
        "cron_minute": s.cron_minute,
        "active": s.active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.post("/institutions/{institution_id}/schedule")
async def create_or_update_schedule(
    institution_id: int = Path(...),
    data: dict = Body(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update extraction schedule for an institution."""
    inst_result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    if not inst_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Institution not found")

    sched_result = await db.execute(
        select(ExtractionSchedule).where(ExtractionSchedule.institution_id == institution_id)
    )
    schedule = sched_result.scalar_one_or_none()
    schedule_type = data.get("schedule_type", "interval")
    interval_minutes = data.get("interval_minutes", 60)

    if schedule:
        schedule.schedule_type = schedule_type
        schedule.interval_minutes = interval_minutes
        schedule.cron_hour = data.get("cron_hour")
        schedule.cron_minute = data.get("cron_minute")
        schedule.active = data.get("active", True)
    else:
        schedule = ExtractionSchedule(
            institution_id=institution_id,
            schedule_type=schedule_type,
            interval_minutes=interval_minutes,
            cron_hour=data.get("cron_hour"),
            cron_minute=data.get("cron_minute"),
            active=data.get("active", True),
        )
        db.add(schedule)
    await db.flush()
    return _schedule_to_dict(schedule)


@router.get("/institutions/{institution_id}/schedule")
async def get_schedule(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get schedule for an institution."""
    inst_result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    if not inst_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Institution not found")
    sched_result = await db.execute(
        select(ExtractionSchedule).where(ExtractionSchedule.institution_id == institution_id)
    )
    schedule = sched_result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule configured")
    return _schedule_to_dict(schedule)


@router.delete("/institutions/{institution_id}/schedule", status_code=204)
async def delete_schedule(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete schedule for an institution."""
    sched_result = await db.execute(
        select(ExtractionSchedule).where(ExtractionSchedule.institution_id == institution_id)
    )
    schedule = sched_result.scalar_one_or_none()
    if schedule:
        db.delete(schedule)


@router.post("/institutions/{institution_id}/schedule/toggle")
async def toggle_schedule(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle schedule active/inactive."""
    inst_result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    if not inst_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Institution not found")
    sched_result = await db.execute(
        select(ExtractionSchedule).where(ExtractionSchedule.institution_id == institution_id)
    )
    schedule = sched_result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule configured")
    schedule.active = not schedule.active
    await db.flush()
    return _schedule_to_dict(schedule)


@router.get("/schedules")
async def list_all_schedules(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all schedules for user's institutions."""
    result = await db.execute(
        select(ExtractionSchedule)
        .join(Institution)
        .where(Institution.user_id == user.db_id)
    )
    schedules = result.scalars().unique().all()
    return {"schedules": [_schedule_to_dict(s) for s in schedules]}


@router.get("/schedules/jobs")
async def list_active_jobs(user: UserInfo = Depends(get_current_user)):
    """List active APScheduler jobs (debug)."""
    try:
        from app.core.services.scheduler_service import get_scheduler_jobs
        return {"jobs": get_scheduler_jobs()}
    except Exception as e:
        return {"jobs": [], "error": str(e)}
