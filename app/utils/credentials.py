"""
Credentials Management - Gerenciamento de credenciais

Sistema de credenciais com PostgreSQL/ParadeDB como fonte autoritativa e arquivo local como fallback.

Ordem de prioridade:
1. PostgreSQL (autoritativo) - SystemConfiguration table
2. Arquivo local credenciais.json (fallback/cache)
3. Credenciais vazias (última opção)

Fluxo de salvamento:
1. Salvar no PostgreSQL (tabela system_configuration)
2. Sincronizar para arquivo local (cache)

MIGRAÇÃO: Este módulo foi migrado de MongoDB para PostgreSQL/ParadeDB (Sprint 2.2).
"""

import datetime
import json
import logging
from typing import Dict

from app.database.session import get_session
from app.database.models.system_configuration import SystemConfiguration
from app.utils.file_utils import get_credentials_file_path

logger = logging.getLogger(__name__)


def load_credentials_from_database() -> Dict:
    """
    Carrega credenciais do PostgreSQL (fonte autoritativa).

    SystemConfiguration usa key/value (JSONB). Chaves: url_sistema, credenciais_acesso.
    """
    try:
        with get_session() as session:
            url_config = session.query(SystemConfiguration).filter_by(key="url_sistema").first()
            site_url = ""
            if url_config and isinstance(url_config.value, dict):
                site_url = url_config.value.get("url", "")
            elif url_config and isinstance(url_config.value, str):
                site_url = url_config.value

            cred_config = session.query(SystemConfiguration).filter_by(
                key="credenciais_acesso"
            ).first()
            if cred_config and isinstance(cred_config.value, dict):
                return {
                    "site_url": site_url,
                    "email": cred_config.value.get("email", ""),
                    "senha": cred_config.value.get("senha", ""),
                    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "postgresql",
                }
    except Exception as e:
        logger.exception("Erro ao carregar credenciais do PostgreSQL: %s", e)
    return {}


def load_credentials_from_file() -> Dict:
    """
    Carrega credenciais do arquivo JSON local (fallback).

    Returns:
        Dict com credenciais ou dict vazio se erro
    """
    try:
        credentials_path = get_credentials_file_path()
        if credentials_path.exists():
            with open(credentials_path, "r", encoding="utf-8") as f:
                credentials = json.load(f)
                # Verificar se os campos obrigatórios existem
                required_fields = ["site_url", "email", "senha"]
                if all(field in credentials for field in required_fields):
                    credentials["source"] = "local_file"
                    return credentials
    except Exception as e:
        logger.exception("Erro ao carregar credenciais do arquivo: %s", e)
    return {}


def sync_credentials_to_file(credentials: Dict) -> bool:
    """
    Sincroniza credenciais do PostgreSQL para arquivo local (cache).

    Args:
        credentials: Dict com credenciais

    Returns:
        True se sincronizado com sucesso, False caso contrário
    """
    try:
        credentials_path = get_credentials_file_path()
        credentials_path.parent.mkdir(parents=True, exist_ok=True)

        # Remover campo source antes de salvar
        clean_credentials = {k: v for k, v in credentials.items() if k != "source"}
        clean_credentials["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(credentials_path, "w", encoding="utf-8") as f:
            json.dump(clean_credentials, f, ensure_ascii=False, indent=2)
        logger.info("Credenciais sincronizadas para arquivo local")
        return True
    except Exception as e:
        logger.exception("Erro ao sincronizar credenciais para arquivo: %s", e)
        return False


def create_empty_credentials() -> Dict:
    """
    Cria dict de credenciais vazias.

    Returns:
        Dict com campos vazios
    """
    return {
        "site_url": "",
        "email": "",
        "senha": "",
        "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "empty"
    }


def load_credentials() -> Dict:
    """
    Carrega credenciais com PostgreSQL como fonte autoritativa.

    Ordem de prioridade:
    1. PostgreSQL (autoritativo)
    2. Arquivo local (fallback)
    3. Credenciais vazias (última opção)

    Returns:
        Dict com credenciais
    """
    # 1. Tentar carregar do PostgreSQL (fonte autoritativa)
    db_credentials = load_credentials_from_database()
    if db_credentials and all(
        db_credentials.get(field, "").strip() for field in ["site_url", "email", "senha"]
    ):
        logger.info("Credenciais carregadas do PostgreSQL (fonte autoritativa)")
        sync_credentials_to_file(db_credentials)
        return db_credentials

    # 2. Fallback: tentar carregar do arquivo local
    file_credentials = load_credentials_from_file()
    if file_credentials and all(
        file_credentials.get(field, "").strip() for field in ["site_url", "email", "senha"]
    ):
        logger.info("Credenciais carregadas do arquivo local (fallback)")
        return file_credentials

    logger.warning("Nenhuma credencial válida encontrada - retornando credenciais vazias")
    return create_empty_credentials()


def save_credentials(credentials: Dict) -> bool:
    """
    Salva credenciais no PostgreSQL (autoritativo) e sincroniza para arquivo local.

    Args:
        credentials: Dict com credenciais (site_url, email, senha)

    Returns:
        True se salvo com sucesso, False caso contrário
    """
    try:
        with get_session() as session:
            site_url = credentials.get("site_url", "")
            url_config = session.query(SystemConfiguration).filter_by(key="url_sistema").first()
            if url_config:
                url_config.value = {"url": site_url}
            else:
                session.add(
                    SystemConfiguration(
                        key="url_sistema",
                        value={"url": site_url},
                        description="URL do sistema SEI",
                        updated_by="credentials",
                    )
                )

            cred_value = {
                "email": credentials.get("email", ""),
                "senha": credentials.get("senha", ""),
            }
            cred_config = session.query(SystemConfiguration).filter_by(
                key="credenciais_acesso"
            ).first()
            if cred_config:
                cred_config.value = cred_value
            else:
                session.add(
                    SystemConfiguration(
                        key="credenciais_acesso",
                        value=cred_value,
                        description="Credenciais de acesso SEI",
                        updated_by="credentials",
                    )
                )

        sync_credentials_to_file(credentials)
        logger.info("Credenciais salvas no PostgreSQL e sincronizadas para arquivo local")
        return True
    except Exception as e:
        logger.exception("Erro ao salvar credenciais: %s", e)
        return False


def credentials_are_complete() -> bool:
    """
    Verifica se as credenciais estão completas e válidas.

    Returns:
        True se todas as credenciais estão preenchidas, False caso contrário
    """
    credentials = load_credentials()
    required_fields = ["site_url", "email", "senha"]

    # Verificar se todos os campos existem e não estão vazios
    complete = all(credentials.get(field, "").strip() for field in required_fields)
    if not complete:
        logger.debug(
            "Credenciais incompletas (fonte: %s)",
            credentials.get("source", "unknown"),
        )
    return complete


def get_sei_url() -> str:
    """
    Retorna a URL do sistema SEI.

    Returns:
        URL do SEI ou string vazia se não configurado
    """
    credentials = load_credentials()
    return credentials.get("site_url", "")
