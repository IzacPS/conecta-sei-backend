"""
Encryption utilities for sensitive data (credentials).

Uses Fernet symmetric encryption from cryptography library.

IMPORTANT: In production, the encryption key should be stored securely:
- Environment variable
- Secret management service (AWS Secrets Manager, Azure Key Vault, etc.)
- NOT hardcoded in the code

For now, we use a key derived from a passphrase for development.
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# IMPORTANTE: Em produção, use variável de ambiente ou serviço de secrets
ENCRYPTION_KEY_PASSPHRASE = os.getenv(
    "CONECTASEI_ENCRYPTION_KEY",
    os.getenv("AUTOMASEI_ENCRYPTION_KEY", "conectasei-v2-default-key-CHANGE-IN-PRODUCTION"),
)

# Salt fixo para derivacao de chave (em producao, use salt unico por instalacao)
SALT = b"conectasei_v2_salt_2024"


def get_encryption_key() -> bytes:
    """
    Deriva chave de encriptação a partir de passphrase.

    Returns:
        Chave Fernet de 32 bytes
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(ENCRYPTION_KEY_PASSPHRASE.encode()))
    return key


def encrypt_password(password: str) -> str:
    """
    Encripta senha usando Fernet.

    Args:
        password: Senha em texto plano

    Returns:
        Senha encriptada (base64)
    """
    if not password:
        return ""

    fernet = Fernet(get_encryption_key())
    encrypted = fernet.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Decripta senha usando Fernet.

    Args:
        encrypted_password: Senha encriptada (base64)

    Returns:
        Senha em texto plano
    """
    if not encrypted_password:
        return ""

    try:
        fernet = Fernet(get_encryption_key())
        decrypted = fernet.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception:
        # Se falhar a decriptação, retorna string vazia
        return ""


def encrypt_credentials(credentials: dict) -> dict:
    """
    Encripta credenciais (apenas senha).

    Args:
        credentials: Dict com email e senha

    Returns:
        Dict com email em texto plano e senha encriptada
    """
    if not credentials:
        return {}

    return {
        "email": credentials.get("email", ""),
        "senha": encrypt_password(credentials.get("senha", ""))
    }


def encrypt_value(value: str) -> str:
    """Encrypt a single string value."""
    return encrypt_password(value)


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a single string value."""
    return decrypt_password(encrypted_value)


def decrypt_credentials(encrypted_credentials: dict) -> dict:
    """
    Decripta credenciais (apenas senha).

    Args:
        encrypted_credentials: Dict com email e senha encriptada

    Returns:
        Dict com email e senha em texto plano
    """
    if not encrypted_credentials:
        return {}

    return {
        "email": encrypted_credentials.get("email", ""),
        "senha": decrypt_password(encrypted_credentials.get("senha", ""))
    }
