"""Case-file management endpoints.

The web UI uses these to let the user list, upload, download, and delete
the documents under their case prefix in S3. Bytes never flow through
this service: uploads and downloads are done with presigned URLs the
browser uses to talk to S3 directly.

The bucket and prefix come from `LAWAGENT_S3_URI` (same env var that the
`apps/s3fetch` CLI reads), so a single `s3://bucket/case/<id>/` config
drives both the CLI puller and the web UI.

Browser uploads use a presigned PUT to S3, so the bucket's CORS policy
must allow PUT, GET, and DELETE from the web origin. Example policy on
the bucket:

    [{"AllowedOrigins": ["http://localhost:3000"],
      "AllowedMethods": ["GET", "PUT", "DELETE"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"]}]
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from settings import get_settings


router = APIRouter(prefix="/files", tags=["files"])


PRESIGN_EXPIRES_SECONDS = 15 * 60


class FileItem(BaseModel):
    key: str
    name: str
    size: int
    last_modified: str


class FileListResponse(BaseModel):
    bucket: str
    prefix: str
    items: list[FileItem]


class PresignUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    content_type: str = Field(default="application/octet-stream", max_length=200)


class PresignUploadResponse(BaseModel):
    url: str
    key: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class PresignDownloadResponse(BaseModel):
    url: str
    expires_in: int


def _resolve_target() -> tuple[str, str]:
    """Return (bucket, prefix) from LAWAGENT_S3_URI, or 502 if unset."""
    uri = get_settings().s3_uri
    if not uri:
        raise HTTPException(
            status_code=503,
            detail="File storage is not configured. Set LAWAGENT_S3_URI.",
        )
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise HTTPException(
            status_code=500,
            detail=f"LAWAGENT_S3_URI is not a valid s3:// URI: {uri!r}",
        )
    prefix = parsed.path.lstrip("/")
    return parsed.netloc, prefix


def _sanitize_filename(filename: str) -> str:
    """Strip path separators and leading dots from a client-supplied name."""
    name = filename.replace("\\", "/").split("/")[-1].strip()
    name = name.lstrip(".")
    if not name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    return name


def _s3():
    return boto3.client("s3", config=Config(signature_version="s3v4"))


@router.get("", response_model=FileListResponse)
def list_files() -> FileListResponse:
    """List every object in the bucket.

    The configured prefix only governs where new uploads land; the listing
    spans the whole bucket so the UI can see everything stored there.
    Folder placeholder keys (zero-byte, trailing slash) are skipped.
    """
    bucket, prefix = _resolve_target()
    s3 = _s3()
    items: list[FileItem] = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                size = int(obj.get("Size", 0))
                if key.endswith("/") and size == 0:
                    continue
                items.append(
                    FileItem(
                        key=key,
                        name=key,
                        size=size,
                        last_modified=obj["LastModified"].isoformat(),
                    )
                )
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 list failed: {exc}") from exc

    items.sort(key=lambda f: f.last_modified, reverse=True)
    return FileListResponse(bucket=bucket, prefix=prefix, items=items)


@router.post("/presign-upload", response_model=PresignUploadResponse)
def presign_upload(req: PresignUploadRequest) -> PresignUploadResponse:
    """Return a presigned PUT URL the browser uses to upload directly to S3."""
    bucket, prefix = _resolve_target()
    name = _sanitize_filename(req.filename)
    key = f"{prefix}{name}" if prefix else name

    try:
        url = _s3().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": req.content_type,
            },
            ExpiresIn=PRESIGN_EXPIRES_SECONDS,
            HttpMethod="PUT",
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not presign upload: {exc}"
        ) from exc

    return PresignUploadResponse(
        url=url,
        key=key,
        headers={"Content-Type": req.content_type},
        expires_in=PRESIGN_EXPIRES_SECONDS,
    )


@router.get("/presign-download", response_model=PresignDownloadResponse)
def presign_download(key: str = Query(..., min_length=1)) -> PresignDownloadResponse:
    """Return a presigned GET URL for any object in the bucket."""
    bucket, _ = _resolve_target()
    try:
        url = _s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=PRESIGN_EXPIRES_SECONDS,
            HttpMethod="GET",
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not presign download: {exc}"
        ) from exc
    return PresignDownloadResponse(url=url, expires_in=PRESIGN_EXPIRES_SECONDS)


@router.delete("")
def delete_file(key: str = Query(..., min_length=1)) -> dict[str, str]:
    """Delete one object from the bucket."""
    bucket, _ = _resolve_target()
    try:
        _s3().delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 delete failed: {exc}") from exc
    return {"status": "deleted", "key": key}
