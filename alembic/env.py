"""
Alembic Environment Configuration

This file configures Alembic to work with our SQLAlchemy models and PostgreSQL database.
"""

from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context
import sys
import os

# Load .env from project root so DATABASE_URL is set (same as API)
try:
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(__file__))
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

# Add parent directory to path to import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import our SQLAlchemy models - importing the package triggers all model registrations
from app.database.session import Base
import app.database.models  # noqa: F401 - registers all models with Base

# This is the Alembic Config object
config = context.config

# Prefer DATABASE_URL from environment (same as the API) so migrations run on the same DB
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def get_url():
    """Migration URL: env DATABASE_URL overrides alembic.ini."""
    return os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    from sqlalchemy import create_engine
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
