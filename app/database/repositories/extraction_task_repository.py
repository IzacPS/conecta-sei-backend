"""
Repository for ExtractionTask database operations.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.extraction_task import ExtractionTask


class ExtractionTaskRepository:
    """Handles database operations for extraction tasks."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, institution_id: str, trigger_type: str) -> ExtractionTask:
        """Create new extraction task."""
        task = ExtractionTask(
            institution_id=institution_id,
            trigger_type=trigger_type,
            status="pending"
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> ExtractionTask | None:
        """Get task by ID."""
        return self.db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()

    def update_status(self, task_id: str, status: str, error_message: str = None) -> ExtractionTask:
        """Update task status."""
        task = self.get_by_id(task_id)
        if task:
            # SQLAlchemy permite atribuição direta aos campos
            object.__setattr__(task, 'status', status)
            if status == "running" and not task.started_at:
                object.__setattr__(task, 'started_at', datetime.utcnow())
            elif status in ("completed", "failed"):
                object.__setattr__(task, 'completed_at', datetime.utcnow())
            if error_message:
                object.__setattr__(task, 'error_message', error_message)
            self.db.commit()
            self.db.refresh(task)
        return task

    def update_progress(self, task_id: str, total: int = None, processed: int = None) -> ExtractionTask:
        """Update task progress."""
        task = self.get_by_id(task_id)
        if task:
            if total is not None:
                object.__setattr__(task, 'total_processes', str(total))
            if processed is not None:
                object.__setattr__(task, 'processed_count', str(processed))
            self.db.commit()
            self.db.refresh(task)
        return task

    def set_result(self, task_id: str, result_summary: dict) -> ExtractionTask:
        """Set task result summary."""
        task = self.get_by_id(task_id)
        if task:
            object.__setattr__(task, 'result_summary', result_summary)
            self.db.commit()
            self.db.refresh(task)
        return task

    def get_by_institution(self, institution_id: str, limit: int = 50) -> list[ExtractionTask]:
        """Get recent tasks for institution."""
        return (
            self.db.query(ExtractionTask)
            .filter(ExtractionTask.institution_id == institution_id)
            .order_by(ExtractionTask.created_at.desc())
            .limit(limit)
            .all()
        )
