"""
Scheduler Service - APScheduler integration for automated extractions.

Manages scheduled extraction jobs per institution.
"""
import logging
from typing import Optional, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from app.database.session import get_session
from app.database.models.extraction_schedule import ExtractionSchedule
from app.database.models.extraction_task import ExtractionTask

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the singleton scheduler."""
    global _scheduler

    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(3)},
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        logger.info("APScheduler initialized")

    return _scheduler


def start_scheduler():
    """Start scheduler and load active schedules from DB."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
        _load_all_schedules()


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler shutdown")


def get_scheduler_jobs() -> List[dict]:
    """List all active scheduler jobs."""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]


def _load_all_schedules():
    """Load active schedules from DB and create jobs."""
    try:
        with get_session() as db:
            schedules = db.query(ExtractionSchedule).filter(
                ExtractionSchedule.active == True  # noqa
            ).all()

            logger.info(f"Loading {len(schedules)} active schedules")
            for sched in schedules:
                _add_job(sched)
    except Exception as e:
        err_msg = str(e).lower()
        if "extraction_schedules" in err_msg and ("does not exist" in err_msg or "undefinedtable" in err_msg):
            logger.warning(
                "Table extraction_schedules does not exist. Run migrations: alembic upgrade head"
            )
        else:
            logger.warning(f"Failed to load schedules: {e}")


def _add_job(schedule: ExtractionSchedule):
    """Add a job to the scheduler from a schedule config."""
    scheduler = get_scheduler()
    job_id = f"extraction_{schedule.institution_id}"

    # Remove existing
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    if schedule.schedule_type == "interval":
        minutes = schedule.interval_minutes or 30
        trigger = IntervalTrigger(minutes=minutes)
    elif schedule.schedule_type == "cron":
        trigger = CronTrigger(
            hour=schedule.cron_hour or 0,
            minute=schedule.cron_minute or 0,
        )
    else:
        logger.error(f"Invalid schedule type: {schedule.schedule_type}")
        return

    scheduler.add_job(
        func=_run_scheduled_extraction,
        trigger=trigger,
        id=job_id,
        args=[schedule.institution_id],
        replace_existing=True,
    )
    logger.info(f"Scheduled job: {job_id} ({schedule.schedule_type})")


def _run_scheduled_extraction(institution_id: int):
    """Execute a scheduled extraction (called by APScheduler)."""
    logger.info(f"[Scheduler] Running extraction for institution {institution_id}")

    try:
        with get_session() as db:
            task = ExtractionTask(
                institution_id=institution_id,
                trigger_type="schedule",
                status="running",
            )
            db.add(task)
            db.flush()

            # TODO: Integrate with actual ProcessExtractor
            # For now, mark as finished
            task.status = "finished"
            task.result_summary = {"message": "Scheduled extraction placeholder"}

            logger.info(f"[Scheduler] Extraction task {task.id} completed")
    except Exception as e:
        logger.error(f"[Scheduler] Extraction failed for {institution_id}: {e}")
