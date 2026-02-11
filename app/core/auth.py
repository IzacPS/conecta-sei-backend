"""
Firebase Authentication middleware for FastAPI.

Verifies Firebase JWT tokens and syncs user data with local PostgreSQL.
Uses async DB session for request handlers.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.models.user import User
from app.utils.firebase_config import get_firebase_credentials

logger = logging.getLogger(__name__)

_firebase_app: Optional[firebase_admin.App] = None


def init_firebase() -> None:
    """Initialize Firebase Admin SDK. Call once at app startup."""
    global _firebase_app
    if _firebase_app is not None:
        return

    cred = get_firebase_credentials()
    if cred is not None:
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized (credentials from env or file)")
    else:
        try:
            _firebase_app = firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default credentials")
        except Exception as e:
            logger.warning(
                f"Firebase Admin SDK not initialized: {e}. "
                "Auth endpoints will work in dev mode (no token verification)."
            )


@dataclass
class UserInfo:
    """Authenticated user information."""
    uid: str
    email: str
    name: Optional[str] = None
    role: str = "user"
    db_id: Optional[int] = None


security = HTTPBearer(auto_error=False)
DEV_MODE = os.getenv("AUTH_DEV_MODE", "false").lower() == "true"


async def _get_or_create_user(
    db: AsyncSession,
    firebase_uid: str,
    email: str,
    name: Optional[str] = None,
) -> User:
    """Get existing user or create new one from Firebase data."""
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        firebase_uid=firebase_uid,
        email=email,
        display_name=name,
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def get_current_user(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    """
    FastAPI dependency that extracts and verifies Firebase JWT token.

    In dev mode (AUTH_DEV_MODE=true), returns a mock user if no token provided.
    Optional header X-Dev-User-Email (e.g. client@conectasei.local) impersonates that user.
    """
    if DEV_MODE and cred is None:
        dev_email = (request.headers.get("X-Dev-User-Email") or "").strip()
        if dev_email:
            result = await db.execute(select(User).where(User.email == dev_email))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dev user not found: {dev_email}. Run scripts/seed-test-data.py.",
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled",
                )
            return UserInfo(
                uid=user.firebase_uid,
                email=user.email,
                name=user.display_name,
                role=user.role,
                db_id=user.id,
            )
        dev_user = await _get_or_create_user(db, "dev-uid-001", "dev@conectasei.local", "Developer")
        return UserInfo(
            uid="dev-uid-001",
            email="dev@conectasei.local",
            name="Developer",
            role=dev_user.role,
            db_id=dev_user.id,
        )

    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = cred.credentials

    if _firebase_app is None:
        init_firebase()

    if _firebase_app is not None:
        try:
            decoded = firebase_auth.verify_id_token(token)
            uid = decoded["uid"]
            email = decoded.get("email", "")
            name = decoded.get("name")
        except firebase_auth.ExpiredIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        except firebase_auth.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
            )
    else:
        if DEV_MODE:
            uid = "dev-uid-001"
            email = "dev@conectasei.local"
            name = "Developer"
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not available",
            )

    user = await _get_or_create_user(db, uid, email, name)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return UserInfo(
        uid=uid,
        email=email,
        name=name or user.display_name,
        role=user.role,
        db_id=user.id,
    )


async def get_current_admin(
    user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    """Dependency that requires admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_optional_user(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserInfo]:
    """Optional auth - returns None if no token provided."""
    if cred is None:
        return None
    try:
        return await get_current_user(request, cred, db)
    except HTTPException:
        return None
