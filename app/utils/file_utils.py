"""
File Utilities - Gerenciamento de arquivos e diretórios

Funções para:
- Diretórios de dados da aplicação
- Backups
- Limpeza de arquivos antigos
- Paths de configuração
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_app_data_dir() -> Path:
    """
    Retorna o diretório de dados da aplicação.

    Returns:
        Path para %LOCALAPPDATA%/SEI_UNO_TRADE
    """
    base_dir = Path(os.getenv("LOCALAPPDATA")) / "SEI_UNO_TRADE"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_backup_dir() -> Path:
    """
    Retorna o diretório de backups.

    Returns:
        Path para %LOCALAPPDATA%/SEI_UNO_TRADE/backups
    """
    backup_dir = get_app_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_temp_download_dir() -> Path:
    """
    Retorna o diretório de downloads temporários.

    Returns:
        Path para %LOCALAPPDATA%/SEI_UNO_TRADE/temp_downloads
    """
    temp_dir = get_app_data_dir() / "temp_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def get_credentials_file_path() -> Path:
    """
    Retorna o path do arquivo de credenciais.

    Returns:
        Path para %LOCALAPPDATA%/SEI_UNO_TRADE/credenciais.json
    """
    return get_app_data_dir() / "credenciais.json"


def cleanup_old_backups(phase_name: str, keep_count: int = 5) -> None:
    """
    Remove backups antigos, mantendo apenas os N mais recentes.

    Args:
        phase_name: Nome da fase (ex: "stage1", "stage2")
        keep_count: Número de backups a manter (padrão: 5)
    """
    backup_dir = get_backup_dir()
    phase_backups = sorted(
        [f for f in backup_dir.glob(f"processos_atuais_{phase_name}_*.json")],
        reverse=True,
    )

    for old_backup in phase_backups[keep_count:]:
        try:
            old_backup.unlink()
            logger.info("Backup antigo removido: %s", old_backup.name)
        except Exception as e:
            logger.warning("Erro ao remover backup antigo %s: %s", old_backup, e)


def ensure_directory_exists(path: Path) -> bool:
    """
    Garante que um diretório existe, criando se necessário.

    Args:
        path: Path do diretório

    Returns:
        True se diretório existe ou foi criado, False se erro
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.warning("Erro ao criar diretório %s: %s", path, e)
        return False


def get_file_size(file_path: Path) -> Optional[int]:
    """
    Retorna o tamanho de um arquivo em bytes.

    Args:
        file_path: Path do arquivo

    Returns:
        Tamanho em bytes, ou None se erro
    """
    try:
        return file_path.stat().st_size
    except Exception as e:
        logger.warning("Erro ao obter tamanho do arquivo %s: %s", file_path, e)
        return None


def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho de arquivo para leitura humana.

    Args:
        size_bytes: Tamanho em bytes

    Returns:
        String formatada (ex: "1.5 MB", "320 KB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
