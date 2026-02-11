"""
String constants for process fields.
Using plain strings (not Enums) for flexibility and legacy compatibility.
"""


class ProcessAccessType:
    PARTIAL = "parcial"
    INTEGRAL = "integral"


class ProcessCategory:
    RESTRITO = "restrito"
    CONFIDENCIAL = "confidencial"


class ProcessStatus:
    CATEGORIZADO = "categorizado"
    PENDENTE = "pendente"


class ExtractionStatus:
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class PipelineRequestStatus:
    ANALYZING = "analyzing"
    READY = "ready"
    PENDING_SCRAPER = "pending_scraper"
    QUOTE_SENT = "quote_sent"
    PENDING_PAYMENT = "pending_payment"
    IN_DEVELOPMENT = "in_development"
    REJECTED = "rejected"
    FAILED = "failed"
