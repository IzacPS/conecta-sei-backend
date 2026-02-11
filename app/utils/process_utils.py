"""
Process Utilities - Validações e helpers de processos

Funções utilitárias para manipulação e validação de dados de processos.

Funções:
- create_process_entry(): Cria estrutura inicial de processo
- validate_process_status(): Valida se processo tem campos obrigatórios
- should_process_documents(): Determina se deve extrair documentos
- check_access_type(): Verifica tipo de acesso ao processo
- notify_process_update(): Notifica atualização de processo (log)
"""

import datetime
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def create_process_entry(process_number: str) -> Dict:
    """
    Cria estrutura inicial de um processo.

    Args:
        process_number: Número do processo

    Returns:
        Dict com estrutura vazia de processo
    """
    return {
        "links": {},
        "melhor_link_atual": None,
        "categoria": None,
        "status_categoria": "pendente",
        "tipo_acesso_atual": None,
        "documentos": {},
        "unidade": None,
        "sem_link_validos": True,
        "ultima_verificacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ultima_atualizacao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def validate_process_status(process_data: Dict) -> bool:
    """
    Valida se processo tem todos os campos obrigatórios.

    Args:
        process_data: Dados do processo

    Returns:
        True se válido, False caso contrário
    """
    required_fields = [
        "links",
        "categoria",
        "status_categoria",
        "tipo_acesso_atual",
        "documentos",
        "unidade",
    ]

    return all(field in process_data for field in required_fields)


def should_process_documents(process_data: Dict) -> bool:
    """
    Determina se deve processar documentos do processo.

    Lógica (replicada do legado utils.py:93-115):
    - Se sem_link_validos: NÃO processar
    - Se tipo_acesso_atual == "integral": sempre processar
    - Se tipo_acesso_atual == "parcial":
        - Se status_categoria == "pendente": NÃO processar
        - Se categoria == "restrito": processar
        - Caso contrário: NÃO processar

    Args:
        process_data: Dados do processo

    Returns:
        True se deve processar documentos, False caso contrário
    """
    if not process_data:
        return False

    if process_data.get("sem_link_validos", False):
        return False

    access_type = process_data.get("tipo_acesso_atual", "")

    if access_type == "integral":
        return True

    if access_type == "parcial":
        status = process_data.get("status_categoria", "")

        category = process_data.get("categoria", "")

        if status == "pendente":
            return False

        return category in ["restrito"]

    return False


def check_access_type(process_data: Dict) -> str:
    """
    Verifica o tipo de acesso ao processo baseado nos links.

    Args:
        process_data: Dados do processo

    Returns:
        "integral" se tem acesso integral, "parcial" caso contrário
    """
    links = process_data.get("links", {})
    return (
        "integral"
        if any(link.get("tipo_acesso") == "integral" for link in links.values())
        else "parcial"
    )


def notify_process_update(message: str, process_id: str) -> None:
    """
    Notifica atualização de processo via log.

    Args:
        message: Mensagem de atualização
        process_id: ID do processo
    """
    logger.info("[PROCESSO %s] %s", process_id, message)
