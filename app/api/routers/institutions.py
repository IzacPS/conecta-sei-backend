"""
Institutions Router - CRUD for multi-tenant institution management.

All endpoints require authentication.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.institution import (
    InstitutionCreate,
    InstitutionListResponse,
    InstitutionResponse,
    InstitutionUpdate,
)
from app.api.schemas.schemas_old import MessageResponse
from app.core.auth import UserInfo, get_current_user
from app.database.models.institution import Institution
from app.database.models.process import Process
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=InstitutionListResponse)
async def list_institutions(
    active_only: bool = Query(False, description="Filter only active institutions"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List institutions owned by the current user."""
    where_clauses = [Institution.user_id == user.db_id]
    if active_only:
        where_clauses.append(Institution.is_active == True)  # noqa: E712
    total = (await db.execute(
        select(func.count()).select_from(Institution).where(*where_clauses)
    )).scalar_one() or 0
    q = select(Institution).where(*where_clauses).order_by(
        Institution.created_at.desc()
    ).offset(skip).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()
    return InstitutionListResponse(
        items=[InstitutionResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get("/{institution_id}", response_model=InstitutionResponse)
async def get_institution(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get institution by ID (must belong to current user)."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return InstitutionResponse.model_validate(inst)


@router.post("", response_model=InstitutionResponse, status_code=201)
async def create_institution(
    data: InstitutionCreate,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new institution for the current user."""
    inst = Institution(
        user_id=user.db_id,
        name=data.name,
        sei_url=data.sei_url,
        is_active=True,
        extra_metadata=data.extra_metadata,
    )
    db.add(inst)
    await db.flush()
    logger.info(f"Institution created: {inst.id} by user {user.email}")
    return InstitutionResponse.model_validate(inst)


@router.put("/{institution_id}", response_model=InstitutionResponse)
async def update_institution(
    data: InstitutionUpdate,
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an institution."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")
    for key, value in update_dict.items():
        setattr(inst, key, value)

    await db.flush()
    logger.info(f"Institution updated: {institution_id}")
    return InstitutionResponse.model_validate(inst)


@router.delete("/{institution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_institution(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete institution and all associated data (CASCADE)."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    db.delete(inst)
    logger.warning(f"Institution deleted: {institution_id}")


@router.get("/{institution_id}/stats")
async def get_institution_stats(
    institution_id: int = Path(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for an institution."""
    result = await db.execute(
        select(Institution).where(
            Institution.id == institution_id,
            Institution.user_id == user.db_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    result = await db.execute(select(Process).where(Process.institution_id == institution_id))
    processes = result.scalars().all()

    by_access = {}
    by_category = {}
    pending = 0
    invalid = 0
    for p in processes:
        at = p.access_type or "unknown"
        by_access[at] = by_access.get(at, 0) + 1
        cat = p.category or "uncategorized"
        by_category[cat] = by_category.get(cat, 0) + 1
        if p.category_status == "pendente":
            pending += 1
        if p.no_valid_links:
            invalid += 1

    return {
        "institution_id": institution_id,
        "total_processes": len(processes),
        "by_access_type": by_access,
        "by_category": by_category,
        "pending_categorization": pending,
        "invalid_links": invalid,
    }
