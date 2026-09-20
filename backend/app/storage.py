"""
Object storage abstraction.

TWO BACKENDS, selected by config.MINIO_ENDPOINT:

  DEMO MODE (MINIO_ENDPOINT unset):
    Writes to local disk under LOCAL_MEDIA_DIR (./data/media).
    Returns a path the static file server exposes at /media/<filename>.
    No external service required — fully demonstrated without MinIO.

  LIVE MODE (MINIO_ENDPOINT set):
    Uses the official minio Python client to upload to the configured
    S3-compatible bucket. Returns a presigned GET URL so any consumer
    can fetch the object directly.

    The Media database row stores:
      storage_key  — object key in the bucket (uuid + extension)
      media_url    — presigned URL (valid PRESIGN_EXPIRY_HOURS)
    Binary content is never stored in the database — only in MinIO.

§2 upgrade: real MinIO client wired behind the existing MINIO_ENDPOINT
config flag. Function signature save_media() unchanged — callers (api/media.py)
do not change.
"""
import io
import logging
import os
import uuid
from datetime import timedelta

from .core import config

log = logging.getLogger("indra.storage")

LOCAL_MEDIA_DIR = os.getenv("LOCAL_MEDIA_DIR", "./data/media")
PRESIGN_EXPIRY_HOURS = int(os.getenv("MINIO_PRESIGN_HOURS", "24"))

# ---- MinIO client (lazy init, None in Demo Mode) -------------------------
_minio_client = None
_minio_init_failed = False


def _get_minio():
    global _minio_client, _minio_init_failed
    if not config.MINIO_ENDPOINT or _minio_init_failed:
        return None
    if _minio_client is not None:
        return _minio_client
    try:
        from minio import Minio
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        _minio_client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY or None,
            secret_key=config.MINIO_SECRET_KEY or None,
            secure=secure,
        )
        # Ensure bucket exists
        if not _minio_client.bucket_exists(config.MINIO_BUCKET):
            _minio_client.make_bucket(config.MINIO_BUCKET)
            log.info("MinIO: created bucket '%s'.", config.MINIO_BUCKET)
        log.info("MinIO client connected to %s, bucket=%s", config.MINIO_ENDPOINT, config.MINIO_BUCKET)
        return _minio_client
    except Exception as exc:
        log.error("MinIO init failed (%s) — falling back to local disk.", exc)
        _minio_init_failed = True
        return None


def save_media(file_bytes: bytes, original_filename: str, content_type: str) -> str:
    """Save binary media content and return a URL to retrieve it.

    LIVE MODE: uploads to MinIO, returns a presigned URL.
    DEMO MODE: writes to local disk, returns /media/<filename> path.
    """
    ext = os.path.splitext(original_filename)[1][:10] or ""
    safe_name = f"{uuid.uuid4().hex}{ext}"

    client = _get_minio()
    if client is not None:
        try:
            client.put_object(
                config.MINIO_BUCKET,
                safe_name,
                io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
            )
            url = client.presigned_get_object(
                config.MINIO_BUCKET,
                safe_name,
                expires=timedelta(hours=PRESIGN_EXPIRY_HOURS),
            )
            log.info("MinIO upload: %s → %s (%d bytes)", safe_name, config.MINIO_BUCKET, len(file_bytes))
            return url
        except Exception as exc:
            log.error("MinIO upload failed (%s) — falling back to local disk.", exc)

    # --- Local disk fallback (Demo Mode or MinIO failure) ------------------
    os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)
    dest_path = os.path.join(LOCAL_MEDIA_DIR, safe_name)
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    return f"/media/{safe_name}"

