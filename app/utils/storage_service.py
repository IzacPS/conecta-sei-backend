"""
Storage Service - Firebase Storage bucket for document persistence.

All documents (PDFs extracted from SEI) are stored in a Firebase Storage
bucket, organised by institution and process:

    {institution_id}/{process_number}/{document_number}.pdf

THREAD-SAFETY:
- Firebase Admin SDK is thread-safe by design
- Bucket singleton initialised once (double-checked locking)
- Each worker thread can upload/download concurrently

Configuration (environment variables):
- FIREBASE_CREDENTIALS    : Conteúdo do JSON da service account (inline, minificado em uma linha)
- FIREBASE_STORAGE_BUCKET : Bucket name (e.g. "conectasei-documents")

Architecture:
```
ProcessExtractor (ThreadPool 5 workers)
   ├─ Worker 1 → DocumentDownloader → upload_document()
   ├─ Worker 2 → DocumentDownloader → upload_document()
   └─ ...
                                          ↓
                         Firebase Storage bucket (thread-safe)
```
"""

import os
import logging
import threading
from datetime import timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Singleton state ──────────────────────────────────────────────────
_firebase_initialized = False
_storage_bucket = None
_init_lock = threading.Lock()

# Default signed-URL lifetime (1 hour)
_DEFAULT_URL_EXPIRATION = timedelta(hours=1)


# ── Initialisation ───────────────────────────────────────────────────

def init_firebase_storage() -> bool:
    """
    Initialise Firebase Admin SDK + Storage bucket (thread-safe).

    Returns True on success, False otherwise.
    """
    global _firebase_initialized, _storage_bucket

    # Double-checked locking
    if _firebase_initialized:
        return True

    with _init_lock:
        if _firebase_initialized:
            return True

        try:
            import firebase_admin
            from firebase_admin import storage

            from app.utils.firebase_config import get_firebase_credentials

            cred = get_firebase_credentials()
            if cred is None:
                logger.warning(
                    "Firebase credentials not configured "
                    "(set FIREBASE_CREDENTIALS with the JSON content inline)"
                )
                return False

            bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
            if not bucket_name:
                logger.warning(
                    "Firebase bucket not configured "
                    "(set FIREBASE_STORAGE_BUCKET env var)"
                )
                return False

            # Only initialise the default app once
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {
                    "storageBucket": bucket_name,
                })

            _storage_bucket = storage.bucket()
            _firebase_initialized = True
            logger.info(f"Firebase Storage initialised (bucket={bucket_name})")
            return True

        except ImportError:
            logger.error(
                "firebase-admin not installed.  "
                "Run: pip install firebase-admin"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialise Firebase Storage: {e}")
            return False


def _ensure_bucket():
    """Return the bucket reference, initialising lazily if needed."""
    if not _firebase_initialized:
        if not init_firebase_storage():
            raise RuntimeError("Firebase Storage is not available")
    return _storage_bucket


# ── Blob path helper ─────────────────────────────────────────────────

def _blob_path(
    institution_id: str | int,
    process_number: str,
    document_number: str,
) -> str:
    """Build the canonical blob path inside the bucket."""
    return f"{institution_id}/{process_number}/{document_number}.pdf"


# ── Upload ───────────────────────────────────────────────────────────

def upload_document(
    local_file_path: str,
    process_number: str,
    document_number: str,
    institution_id: str | int = "legacy",
) -> tuple[bool, Optional[str]]:
    """
    Upload a local PDF to Firebase Storage.

    Args:
        local_file_path: Absolute path to the local file.
        process_number:  SEI process number.
        document_number: SEI document number.
        institution_id:  Institution PK (or "legacy").

    Returns:
        (success, blob_path)
        - success:   True when the file was uploaded.
        - blob_path: The path inside the bucket (e.g.
          "42/12345678901234567/99887766.pdf") so it can be
          stored in the Document model.  None on failure.
    """
    try:
        bucket = _ensure_bucket()
    except RuntimeError:
        logger.error("Firebase Storage not available — upload skipped")
        return False, None

    local = Path(local_file_path)
    if not local.exists():
        logger.error(f"Local file not found: {local_file_path}")
        return False, None

    path = _blob_path(institution_id, process_number, document_number)

    try:
        blob = bucket.blob(path)
        blob.upload_from_filename(str(local), content_type="application/pdf")
        logger.info(f"Uploaded to bucket: {path}")
        return True, path
    except Exception as e:
        logger.error(f"Upload failed ({path}): {e}")
        return False, None


# ── Download URL (signed) ───────────────────────────────────────────

def get_download_url(
    storage_path: str,
    expiration: timedelta | None = None,
) -> Optional[str]:
    """
    Generate a temporary signed download URL for a blob.

    Args:
        storage_path: The blob path inside the bucket
                      (as returned by ``upload_document``).
        expiration:   Lifetime of the URL.  Defaults to 1 hour.

    Returns:
        A signed HTTPS URL, or None on error.
    """
    try:
        bucket = _ensure_bucket()
    except RuntimeError:
        return None

    exp = expiration or _DEFAULT_URL_EXPIRATION

    try:
        blob = bucket.blob(storage_path)
        if not blob.exists():
            logger.warning(f"Blob not found: {storage_path}")
            return None

        url = blob.generate_signed_url(expiration=exp)
        return url
    except Exception as e:
        logger.error(f"Failed to generate signed URL ({storage_path}): {e}")
        return None


def get_download_url_by_parts(
    process_number: str,
    document_number: str,
    institution_id: str | int = "legacy",
    expiration: timedelta | None = None,
) -> Optional[str]:
    """
    Convenience wrapper — build the blob path from its components,
    then return a signed URL.
    """
    path = _blob_path(institution_id, process_number, document_number)
    return get_download_url(path, expiration)


# ── Delete ───────────────────────────────────────────────────────────

def delete_document(
    storage_path: str,
) -> bool:
    """
    Delete a document from Firebase Storage by its blob path.

    Returns True if deleted, False otherwise.
    """
    try:
        bucket = _ensure_bucket()
    except RuntimeError:
        return False

    try:
        blob = bucket.blob(storage_path)
        if blob.exists():
            blob.delete()
            logger.info(f"Deleted from bucket: {storage_path}")
            return True
        else:
            logger.warning(f"Blob not found for deletion: {storage_path}")
            return False
    except Exception as e:
        logger.error(f"Delete failed ({storage_path}): {e}")
        return False


def delete_document_by_parts(
    process_number: str,
    document_number: str,
    institution_id: str | int = "legacy",
) -> bool:
    """Convenience wrapper — delete by individual path components."""
    path = _blob_path(institution_id, process_number, document_number)
    return delete_document(path)


# ── Check existence ──────────────────────────────────────────────────

def document_exists(storage_path: str) -> bool:
    """Return True if the blob exists in the bucket."""
    try:
        bucket = _ensure_bucket()
        return bucket.blob(storage_path).exists()
    except Exception:
        return False


# ── Legacy aliases (backward-compat) ─────────────────────────────────
# These keep the old call-sites working until they are migrated.

def upload_document_to_storage(
    local_file_path: str,
    process_number: str,
    document_number: str,
    institution_id: str = "legacy",
) -> tuple[bool, Optional[str]]:
    """Legacy alias for ``upload_document``."""
    return upload_document(
        local_file_path, process_number, document_number, institution_id,
    )


def delete_document_from_storage(
    process_number: str,
    document_number: str,
    institution_id: str = "legacy",
) -> bool:
    """Legacy alias for ``delete_document_by_parts``."""
    return delete_document_by_parts(
        process_number, document_number, institution_id,
    )


def get_document_url(
    process_number: str,
    document_number: str,
    institution_id: str = "legacy",
) -> Optional[str]:
    """Legacy alias for ``get_download_url_by_parts``."""
    return get_download_url_by_parts(
        process_number, document_number, institution_id,
    )
