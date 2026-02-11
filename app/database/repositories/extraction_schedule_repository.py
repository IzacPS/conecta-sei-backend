"""
Repository for ExtractionSchedule database operations.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.extraction_schedule import ExtractionSchedule


class ExtractionScheduleRepository:
    """Handles database operations for extraction schedules."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        institution_id: str,
        schedule_type: str,
        interval_minutes: int | None,
        cron_hour: str | None,
        cron_minute: str | None,
        active: bool = True
    ) -> ExtractionSchedule:
        """Create new extraction schedule."""
        schedule = ExtractionSchedule(
            institution_id=institution_id,
            schedule_type=schedule_type,
            interval_minutes=str(interval_minutes) if interval_minutes else None,
            cron_hour=cron_hour,
            cron_minute=cron_minute,
            active=active
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def get_by_id(self, schedule_id: str) -> ExtractionSchedule | None:
        """Get schedule by ID."""
        return self.db.query(ExtractionSchedule).filter(
            ExtractionSchedule.id == schedule_id
        ).first()

    def get_by_institution(self, institution_id: str) -> ExtractionSchedule | None:
        """Get schedule for institution (one-to-one relationship)."""
        return self.db.query(ExtractionSchedule).filter(
            ExtractionSchedule.institution_id == institution_id
        ).first()

    def get_all_active(self) -> list[ExtractionSchedule]:
        """Get all active schedules."""
        return self.db.query(ExtractionSchedule).filter(
            ExtractionSchedule.active == True
        ).all()

    def update(
        self,
        schedule_id: str,
        schedule_type: str | None,
        interval_minutes: int | None,
        cron_hour: str | None,
        cron_minute: str | None,
        active: bool | None
    ) -> ExtractionSchedule:
        """Update schedule configuration."""
        schedule = self.get_by_id(schedule_id)
        if schedule:
            if schedule_type is not None:
                schedule.schedule_type = schedule_type
            if interval_minutes is not None:
                schedule.interval_minutes = str(interval_minutes)
            if cron_hour is not None:
                schedule.cron_hour = cron_hour
            if cron_minute is not None:
                schedule.cron_minute = cron_minute
            if active is not None:
                schedule.active = active

            schedule.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(schedule)
        return schedule

    def delete(self, schedule_id: str) -> bool:
        """Delete schedule."""
        schedule = self.get_by_id(schedule_id)
        if schedule:
            self.db.delete(schedule)
            self.db.commit()
            return True
        return False

    def toggle_active(self, schedule_id: str) -> ExtractionSchedule:
        """Toggle schedule active status."""
        schedule = self.get_by_id(schedule_id)
        if schedule:
            schedule.active = not schedule.active
            schedule.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(schedule)
        return schedule
