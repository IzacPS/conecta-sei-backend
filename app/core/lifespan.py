from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from app.core.logging import setup_logger

logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 ConectaSEI v2.0 API iniciando...")

    # Banco
    try:
        from app.database.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com PostgreSQL estabelecida")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao banco: {e}")

    # Scheduler
    try:
        from app.core.services.scheduler_service import start_scheduler
        start_scheduler()
        logger.info("✅ APScheduler iniciado")
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar APScheduler: {e}")

    yield

    logger.info("🛑 ConectaSEI v2.0 API encerrando...")

    try:
        from app.core.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
        logger.info("✅ APScheduler encerrado")
    except Exception as e:
        logger.error(f"❌ Erro ao encerrar APScheduler: {e}")
