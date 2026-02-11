"""
Database Session Management

Manages SQLAlchemy sessions for PostgreSQL/ParadeDB.

- Async engine + AsyncSession for request handlers (FastAPI async).
- Sync engine + Session for Alembic migrations and background tasks that run in threads.

Usage (async - request handlers):
    from app.database.session import get_db
    async with get_db() as session:  # or Depends(get_db)
        result = await session.execute(select(Institution).where(...))

Usage (sync - migrations, bg tasks in thread):
    from app.database.session import get_session
    with get_session() as session:
        result = session.query(Institution).all()
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from typing import AsyncGenerator, Generator
import os
import logging

logging.getLogger("sqlalchemy.engine")

# Database URL - sync (psycopg2) for Alembic and sync background tasks
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://automasei:automasei_dev_password@localhost:5432/automasei",
)

# Async URL - asyncpg for request handlers
def _make_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)

ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", _make_async_url(DATABASE_URL))

# ── Sync engine (Alembic, background tasks in thread) ──
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# ── Async engine (request handlers) ──
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Sync context manager for background tasks and migrations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async FastAPI dependency: yields AsyncSession."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def init_db() -> None:
    """Create tables (use Alembic in production)."""
    Base.metadata.create_all(bind=engine)
