"""Database models package - import all models so Alembic can discover them."""

from app.database.models.model_base import SqlAlchemyModel
from app.database.models.user import User
from app.database.models.institution import Institution
from app.database.models.institution_credential import InstitutionCredential
from app.database.models.institution_scraper import InstitutionScraper
from app.database.models.process import Process
from app.database.models.document import Document
from app.database.models.document_history import DocumentHistory
from app.database.models.receipt import Receipt
from app.database.models.extraction_task import ExtractionTask
from app.database.models.extraction_schedule import ExtractionSchedule
from app.database.models.pipeline_request import PipelineRequest
from app.database.models.scraper_order import ScraperOrder
from app.database.models.payment import Payment
from app.database.models.subscription import Subscription
from app.database.models.system_configuration import SystemConfiguration

__all__ = [
    "SqlAlchemyModel",
    "User",
    "Institution",
    "InstitutionCredential",
    "InstitutionScraper",
    "Process",
    "Document",
    "DocumentHistory",
    "Receipt",
    "ExtractionTask",
    "ExtractionSchedule",
    "PipelineRequest",
    "ScraperOrder",
    "Payment",
    "Subscription",
    "SystemConfiguration",
]
