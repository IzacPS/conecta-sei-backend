"""
Auth Router - User registration and profile management.

Endpoints:
- POST /auth/register - Register new user (Firebase token -> local DB)
- GET  /auth/me       - Get current user profile
- PUT  /auth/me       - Update profile
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserInfo, get_current_user
from app.database.models.user import User
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class UserProfileResponse(BaseModel):
    id: int
    firebase_uid: str
    email: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = None


class RegisterResponse(BaseModel):
    message: str
    user: UserProfileResponse


# ── Endpoints ──

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register/sync user from Firebase to local DB."""
    result = await db.execute(select(User).where(User.firebase_uid == current_user.uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=500, detail="User sync failed")

    logger.info(f"User registered/synced: {current_user.email}")
    return RegisterResponse(
        message="User registered successfully",
        user=UserProfileResponse.model_validate(user),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's profile."""
    result = await db.execute(select(User).where(User.firebase_uid == current_user.uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileResponse.model_validate(user)


@router.put("/me", response_model=UserProfileResponse)
async def update_profile(
    update_data: UserProfileUpdate,
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile."""
    result = await db.execute(select(User).where(User.firebase_uid == current_user.uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user, key, value)

    await db.flush()
    logger.info(f"User profile updated: {current_user.email}")
    return UserProfileResponse.model_validate(user)
