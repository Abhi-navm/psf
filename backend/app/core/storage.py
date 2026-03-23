"""
Cloud storage utilities for uploading videos to Cloudflare R2 (S3-compatible).
Replaces tmpfiles.org as the intermediary for RunPod video delivery.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def _get_s3_client():
    """Get or create a singleton S3 client for Cloudflare R2."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=BotoConfig(
                retries={"max_attempts": 3, "mode": "adaptive"},
                signature_version="s3v4",
            ),
            region_name="auto",
        )
    return _s3_client


def upload_to_r2(file_path: str, prefix: str = "videos") -> str:
    """
    Upload a file to Cloudflare R2 and return a presigned download URL.
    
    Args:
        file_path: Local path to the file.
        prefix: S3 key prefix (folder).
    
    Returns:
        Presigned URL valid for 1 hour.
    """
    client = _get_s3_client()
    file_name = Path(file_path).name
    key = f"{prefix}/{uuid.uuid4().hex[:8]}_{file_name}"
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    logger.info(f"Uploading {file_size_mb:.1f}MB to R2: {key}")
    
    client.upload_file(
        file_path,
        settings.r2_bucket_name,
        key,
        ExtraArgs={"ContentType": "video/mp4"},
    )

    # Generate presigned URL (1 hour expiry — RunPod downloads within minutes)
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=3600,
    )

    logger.info(f"Uploaded {file_size_mb:.1f}MB -> R2 key={key}")
    return url


def delete_from_r2(key: str) -> None:
    """Delete a file from R2 after RunPod has downloaded it."""
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
        logger.info(f"Deleted R2 key: {key}")
    except Exception as e:
        logger.warning(f"Failed to delete R2 key {key}: {e}")


def upload_video_for_runpod(file_path: str) -> str:
    """
    Upload a video file for RunPod to consume.
    
    Uses R2 if credentials are configured, falls back to tmpfiles.org.
    """
    if settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key:
        return upload_to_r2(file_path, prefix="runpod-staging")
    
    # Fallback: tmpfiles.org (rate-limited, not suitable for 50+ parallel)
    return _upload_to_tmpfiles(file_path)


def _upload_to_tmpfiles(file_path: str) -> str:
    """Legacy fallback: upload to tmpfiles.org."""
    import httpx

    logger.warning("Using tmpfiles.org fallback — configure R2 for production workloads")
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    with httpx.Client(timeout=600, follow_redirects=True) as client:
        with open(file_path, "rb") as f:
            resp = client.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (os.path.basename(file_path), f, "video/mp4")},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(f"tmpfiles.org upload failed: {data}")
        page_url = data["data"]["url"]
        dl_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        logger.info(f"Uploaded {file_size_mb:.1f}MB -> {dl_url}")
        return dl_url
