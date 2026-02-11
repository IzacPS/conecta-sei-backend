"""
Pytest global configuration for AutomaSEI v2.0.

Este conftest foi projetado para:
- Testar a API FastAPI de forma isolada
- Usar banco de dados real de TESTE
- Manter compatibilidade total com o legacy
- Permitir extensão futura (processes, extraction, documents)
"""

from dotenv import load_dotenv
import os
import pytest

# Carregar .env.test primeiro; fallback para DB de dev se teste não estiver rodando
load_dotenv(".env.test")
os.environ.setdefault("AUTH_DEV_MODE", "true")
if not os.getenv("DATABASE_URL"):
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://automasei:automasei_dev_password@localhost:5432/automasei",
    )

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import app.database.session as db_session_module
from app.database.session import Base
import app.database.models  # noqa: F401 - registra todos os modelos no Base.metadata
from app.api.main import app

# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def test_db_engine():
    """
    Cria um engine de banco de TESTE e substitui o engine global
    usado por get_session().
    """
    database_url = os.getenv("DATABASE_URL")
    assert database_url, "DATABASE_URL não configurado para testes"

    engine = create_engine(database_url)

    # Criar tabelas
    Base.metadata.create_all(bind=engine)

    # 🔁 Substituir engine e SessionLocal globais
    db_session_module.engine = engine
    db_session_module.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False
    )

    yield engine

    # Limpeza após o teste
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ============================================================================
# FASTAPI CLIENT
# ============================================================================

@pytest.fixture(scope="function")
def test_client(test_db_engine):
    """
    Cria TestClient FastAPI usando o banco de teste.

    Nenhum override de Depends é necessário,
    pois a aplicação usa get_session() diretamente.
    """
    client = TestClient(app)
    yield client


# ============================================================================
# BASE DATA FIXTURES (INSTITUTIONS)
# ============================================================================

@pytest.fixture
def sample_institution_data():
    """
    Payload válido para criação de instituição (schema InstitutionCreate).
    """
    return {
        "name": "Instituição Teste",
        "sei_url": "https://sei.teste.gov.br",
        "extra_metadata": {},
    }


# ============================================================================
# FUTURE EXTENSIONS (placeholders)
# ============================================================================

@pytest.fixture
def legacy_process_payload():
    """
    Placeholder para payload legacy de processo.

    ⚠️ NÃO usar agora.
    Será utilizado em:
    POST /institutions/{id}/processes/extract
    """
    return {
        "numero_processo": "12345.000001/2024-00",
        "links": {},
        "documentos": {},
        "tipo_acesso_atual": "integral",
        "status_categoria": "categorizado",
        "categoria": "restrito",
        "sem_link_validos": False,
    }


@pytest.fixture
def legacy_documents_payload():
    """
    Placeholder para documentos legacy.

    ⚠️ NÃO usar agora.
    """
    return {
        "12345678": {
            "tipo": "Despacho",
            "data": "15/01/2024",
            "status": "nao_baixado",
            "signatario": "Autoridade Competente"
        }
    }
