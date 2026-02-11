"""
Legacy Utils - Backward Compatibility Wrappers

IMPORTANTE: Este arquivo mantém compatibilidade com código legado (ui_*.py, get_*.py, main.py).

MIGRAÇÃO: As funções aqui são apenas WRAPPERS que delegam para o novo pacote utils/.
Código novo deve importar diretamente de utils/ ao invés deste arquivo.

Exemplo:
    # LEGADO (ainda funciona):
    from utils import load_credentials

    # NOVO (preferido):
    from utils.credentials import load_credentials

Este arquivo será REMOVIDO no Sprint 6.2 junto com o código legado.
"""

# Importar todas as funções do novo pacote utils
from utils.file_utils import (
    get_app_data_dir,
    get_backup_dir,
    cleanup_old_backups,
    get_credentials_file_path,
)

from utils.credentials import (
    load_credentials,
    save_credentials,
    credentials_are_complete,
    get_sei_url,
)

from utils.database import (
    load_process_data,
    save_process_data,
)

from utils.process_utils import (
    create_process_entry,
    validate_process_status,
    should_process_documents,
    check_access_type,
    notify_process_update,
)

from utils.playwright_utils import (
    login_to_sei,
)

# Exportar tudo para manter compatibilidade
__all__ = [
    # File utils
    "get_app_data_dir",
    "get_backup_dir",
    "cleanup_old_backups",
    "get_credentials_file_path",
    # Credentials
    "load_credentials",
    "save_credentials",
    "credentials_are_complete",
    "get_sei_url",
    # Database (MongoDB legacy)
    "load_process_data",
    "save_process_data",
    # Process utils
    "create_process_entry",
    "validate_process_status",
    "should_process_documents",
    "check_access_type",
    "notify_process_update",
    # Playwright
    "login_to_sei",
]
