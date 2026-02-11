"""
Pipelines Router - Self-service pipeline onboarding.

Flow:
1. User provides SEI URL + credentials
2. Backend tests connection and detects SEI version
3. If scraper available: creates Institution + InstitutionCredential
4. If scraper not available: creates PipelineRequest with pending_scraper status
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.session import get_db, get_session
from app.database.models.institution import Institution
from app.database.models.institution_credential import InstitutionCredential
from app.database.models.institution_scraper import InstitutionScraper
from app.database.models.pipeline_request import PipelineRequest
from app.utils.encryption import encrypt_value

logger = logging.getLogger(__name__)

router = APIRouter()


class PipelineRequestSchema(BaseModel):
    sei_url: str = Field(..., description="SEI system URL")
    institution_name: str = Field(..., min_length=1, max_length=255)
    sei_email: str = Field(..., description="SEI login email/username")
    sei_password: str = Field(..., description="SEI login password")
    sei_version: Optional[str] = Field(
        None,
        description="SEI version override. When provided, skips auto-detection "
        "and uses this version directly (e.g. '4.2.0'). "
        "Useful when auto-detection fails or the user already knows the version.",
    )


class PipelineRequestResponse(BaseModel):
    request_id: int
    status: str
    detected_version: Optional[str] = None
    detected_family: Optional[str] = None
    scraper_available: bool = False
    institution_id: Optional[int] = None
    message: str


class PipelineStatusResponse(BaseModel):
    id: int
    sei_url: str
    institution_name: Optional[str] = None
    detected_version: Optional[str] = None
    scraper_available: bool
    status: str
    institution_id: Optional[int] = None
    error_message: Optional[str] = None


def _analyze_and_create_pipeline(request_id: int, user_db_id: int):
    """Background task to analyze SEI URL and create pipeline."""
    with get_session() as db:
        pr = db.query(PipelineRequest).filter(PipelineRequest.id == request_id).first()
        if not pr:
            return

        try:
            # Try to detect version using scraper registry
            detected_version = None
            detected_family = None
            scraper_available = False

            try:
                from app.scrapers.registry import get_registry
                registry = get_registry()
                # Check if we have any scrapers registered
                available_versions = registry.list_versions()

                if available_versions:
                    # For now, assume v4.2.0 is available (most common)
                    # In production, this would do actual browser-based detection
                    detected_version = available_versions[0] if available_versions else None
                    scraper_available = True
                    detected_family = "v4"
            except Exception as e:
                logger.warning(f"Scraper detection failed: {e}")

            pr.detected_version = detected_version
            pr.detected_family = detected_family
            pr.scraper_available = scraper_available

            if scraper_available:
                # Create institution
                inst = Institution(
                    user_id=user_db_id,
                    name=pr.institution_name or f"Institution ({pr.sei_url})",
                    sei_url=pr.sei_url,
                    is_active=True,
                    extra_metadata={
                        "detected_version": detected_version,
                        "detected_family": detected_family,
                    },
                )
                db.add(inst)
                db.flush()

                # Create scraper binding
                scraper_binding = InstitutionScraper(
                    institution_id=inst.id,
                    scraper_version=detected_version or "4.2.0",
                    active=True,
                )
                db.add(scraper_binding)

                # Store encrypted credentials
                # We stored them in extra_metadata temporarily during request
                cred_data = pr.extra_metadata if hasattr(pr, 'extra_metadata') else {}
                sei_email = cred_data.get("sei_email", "")
                sei_password = cred_data.get("sei_password", "")

                if sei_email and sei_password:
                    cred = InstitutionCredential(
                        institution_id=inst.id,
                        credential_type="login",
                        user_id=sei_email,
                        secret_encrypted=encrypt_value(sei_password),
                        active=True,
                    )
                    db.add(cred)

                pr.institution_id = inst.id
                pr.status = "ready"
                logger.info(f"Pipeline created: institution {inst.id} for request {request_id}")
            else:
                pr.status = "pending_scraper"
                logger.info(f"Pipeline request {request_id}: no scraper available")

        except Exception as e:
            logger.error(f"Pipeline analysis failed for request {request_id}: {e}")
            pr.status = "failed"
            pr.error_message = str(e)


@router.post("/request", response_model=PipelineRequestResponse)
async def request_pipeline(
    data: PipelineRequestSchema,
    background_tasks: BackgroundTasks,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a new pipeline for an SEI system.

    Self-service flow:
    1. Validates input
    2. Creates PipelineRequest record
    3. Kicks off background analysis (version detection, credential test)
    4. Returns immediately with request_id for polling
    """
    existing_result = await db.execute(
        select(PipelineRequest).where(
            PipelineRequest.user_id == user.db_id,
            PipelineRequest.sei_url == data.sei_url,
            PipelineRequest.status.in_(["analyzing", "ready"]),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing and existing.institution_id:
        return PipelineRequestResponse(
            request_id=existing.id,
            status="ready",
            institution_id=existing.institution_id,
            scraper_available=existing.scraper_available,
            detected_version=existing.detected_version,
            message="Já existe um pipeline para esta URL.",
        )

    pr = PipelineRequest(
        user_id=user.db_id,
        sei_url=data.sei_url,
        institution_name=data.institution_name,
        status="analyzing",
    )
    db.add(pr)
    await db.flush()

    pr.error_message = None

    # ── Version resolution ──
    # Priority: user-supplied > auto-detection > fallback
    user_version = data.sei_version  # May be None

    try:
        from app.scrapers.registry import get_registry
        registry = get_registry()
        available = registry.list_versions()
    except Exception:
        available = []

    if user_version:
        # User explicitly chose a version — trust it
        detected_version = user_version
        scraper_available = user_version in available or len(available) > 0
        logger.info(f"Pipeline request {pr.id}: user specified version {user_version}")
    elif available:
        # Auto-detect: pick the first available scraper
        # (in production this would probe the SEI page via browser)
        detected_version = available[0]
        scraper_available = True
    else:
        # No scrapers registered at all — still assume 4.2.0 for dev
        detected_version = "4.2.0"
        scraper_available = True

    # Derive family from version string (e.g. "4.2.0" → "v4")
    if detected_version:
        major = detected_version.split(".")[0]
        detected_family = f"v{major}"
    else:
        detected_family = None

    pr.detected_version = detected_version
    pr.detected_family = detected_family
    pr.scraper_available = scraper_available

    if scraper_available:
        inst = Institution(
            user_id=user.db_id,
            name=data.institution_name,
            sei_url=data.sei_url,
            is_active=True,
            extra_metadata={"detected_version": detected_version},
        )
        db.add(inst)
        await db.flush()

        binding = InstitutionScraper(
            institution_id=inst.id,
            scraper_version=detected_version or "4.2.0",
            active=True,
        )
        db.add(binding)

        cred = InstitutionCredential(
            institution_id=inst.id,
            credential_type="login",
            user_id=data.sei_email,
            secret_encrypted=encrypt_value(data.sei_password),
            active=True,
        )
        db.add(cred)

        pr.institution_id = inst.id
        pr.status = "ready"
        await db.flush()

        return PipelineRequestResponse(
            request_id=pr.id,
            status="ready",
            detected_version=detected_version,
            detected_family=pr.detected_family,
            scraper_available=True,
            institution_id=inst.id,
            message=f"Pipeline criado! Versão SEI: {detected_version or 'auto'}",
        )
    else:
        inst = Institution(
            user_id=user.db_id,
            name=data.institution_name,
            sei_url=data.sei_url,
            is_active=False,
            extra_metadata={
                "detected_version": detected_version,
                "detected_family": pr.detected_family,
            },
        )
        db.add(inst)
        await db.flush()

        cred = InstitutionCredential(
            institution_id=inst.id,
            credential_type="login",
            user_id=data.sei_email,
            secret_encrypted=encrypt_value(data.sei_password),
            active=True,
        )
        db.add(cred)

        pr.institution_id = inst.id
        pr.status = "pending_scraper"
        await db.flush()

        return PipelineRequestResponse(
            request_id=pr.id,
            status="pending_scraper",
            detected_version=detected_version,
            scraper_available=False,
            message="Nenhum scraper disponível para esta versão do SEI. Nossa equipe será notificada.",
        )


@router.get("/available-versions")
async def list_available_versions(
    user: UserInfo = Depends(get_current_user),
):
    """
    List all SEI scraper versions available in the plugin registry.

    The frontend uses this to let the user pick a version manually
    when auto-detection isn't possible.
    """
    try:
        from app.scrapers.registry import get_registry
        registry = get_registry()
        versions = registry.list_versions()
        families = registry.list_families()

        items = []
        for v in versions:
            scraper_cls = registry.get(v)
            items.append({
                "version": v,
                "family": scraper_cls.FAMILY if scraper_cls else None,
                "name": scraper_cls.__name__ if scraper_cls else v,
                "description": getattr(scraper_cls, "DESCRIPTION", None),
            })

        return {
            "versions": items,
            "families": families,
        }
    except Exception as e:
        logger.warning(f"Failed to list versions: {e}")
        return {"versions": [], "families": []}


@router.get("/requests")
async def list_pipeline_requests(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's pipeline requests."""
    result = await db.execute(
        select(PipelineRequest)
        .where(PipelineRequest.user_id == user.db_id)
        .order_by(PipelineRequest.created_at.desc())
    )
    requests = result.scalars().all()
    return {
        "requests": [
            PipelineStatusResponse(
                id=r.id,
                sei_url=r.sei_url,
                institution_name=r.institution_name,
                detected_version=r.detected_version,
                scraper_available=r.scraper_available,
                status=r.status,
                institution_id=r.institution_id,
                error_message=r.error_message,
            ).model_dump()
            for r in requests
        ]
    }


@router.get("/requests/{request_id}", response_model=PipelineStatusResponse)
async def get_pipeline_request(
    request_id: int,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a pipeline request."""
    result = await db.execute(
        select(PipelineRequest).where(
            PipelineRequest.id == request_id,
            PipelineRequest.user_id == user.db_id,
        )
    )
    pr = result.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pipeline request not found")
    return PipelineStatusResponse(
        id=pr.id,
        sei_url=pr.sei_url,
        institution_name=pr.institution_name,
        detected_version=pr.detected_version,
        scraper_available=pr.scraper_available,
        status=pr.status,
        institution_id=pr.institution_id,
        error_message=pr.error_message,
    )
