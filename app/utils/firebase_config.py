"""
Firebase Admin credentials loading.

FIREBASE_CREDENTIALS = conteúdo do JSON da service account (inline, minificado em uma linha).
Assim o arquivo .json não precisa existir no projeto e não fica exposto.
"""

import json
import os
from typing import Optional

logger = None


def _log():
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    return logger


def get_firebase_credentials():
    """
    Retorna credentials.Certificate a partir da variável FIREBASE_CREDENTIALS.

    FIREBASE_CREDENTIALS deve conter o conteúdo do JSON da service account
    (minificado em uma linha), não o caminho do arquivo.

    Returns:
        credentials.Certificate ou None se não configurado/inválido.
    """
    try:
        from firebase_admin import credentials
    except ImportError:
        _log().warning("firebase-admin not installed")
        return None

    json_str = os.getenv("FIREBASE_CREDENTIALS", "").strip()
    if not json_str:
        return None

    try:
        data = json.loads(json_str)
        return credentials.Certificate(data)
    except json.JSONDecodeError as e:
        _log().error(f"FIREBASE_CREDENTIALS: JSON inválido — {e}")
        return None
