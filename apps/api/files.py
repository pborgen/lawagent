"""Project-scoped case-file management.

Every operation here is bound to one project the caller owns. The
project's S3 namespace is:

    s3://<bucket>/projects/<project_id>/<user-chosen subfolder>/<filename>

The bucket comes from `LAWAGENT_S3_URI` (only the netloc is used — any
path component on that URI is ignored, since per-project prefixing
replaces it). Bytes never flow through this service: uploads and
downloads happen directly between the browser and S3 via presigned URLs.

Browser uploads use a presigned PUT to S3, so the bucket's CORS policy
must allow PUT, GET, and DELETE from the web origin. Example policy on
the bucket:

    [{"AllowedOrigins": ["http://localhost:3000"],
      "AllowedMethods": ["GET", "PUT", "DELETE"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"]}]
"""
from __future__ import annotations

import uuid
from typing import Annotated, Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.users import CurrentDbUser
from convert import ConversionError, pdf_to_docx
from db import Project, get_db_session
from settings import get_settings


router = APIRouter(prefix="/files", tags=["files"])


PRESIGN_EXPIRES_SECONDS = 15 * 60

# Cap synchronous conversions so a huge upload can't tie up the request
# (App Runner request timeout) or the worker. Large-doc async is a follow-up.
CONVERT_MAX_BYTES = 50 * 1024 * 1024

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


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
    project_id: uuid.UUID
    filename: str = Field(..., min_length=1, max_length=512)
    content_type: str = Field(default="application/octet-stream", max_length=200)
    # Destination subfolder *inside* the project, e.g. "discovery/" or
    # "drafts/". Empty/omitted = upload to the project root.
    subfolder: Optional[str] = Field(default=None, max_length=1024)


class PresignUploadResponse(BaseModel):
    url: str
    key: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class PresignDownloadResponse(BaseModel):
    url: str
    expires_in: int


class ConvertRequest(BaseModel):
    project_id: uuid.UUID
    # Full S3 key of the source PDF, as returned by `list_files`.
    key: str = Field(..., min_length=1)


class ConvertResponse(BaseModel):
    # The new .docx object's full S3 key and project-relative name.
    key: str
    name: str
    # False when the source PDF had no text layer (scanned image): the
    # .docx will contain page images, not editable text. The UI warns.
    scanned: bool


def _resolve_bucket() -> str:
    """Return the S3 bucket from LAWAGENT_S3_URI, or 503 if unset."""
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
    return parsed.netloc


def _project_prefix(project_id: uuid.UUID) -> str:
    """The single source of truth for "where does a project's data live"."""
    return f"projects/{project_id}/"


def _sanitize_filename(filename: str) -> str:
    """Strip path separators and leading dots from a client-supplied name."""
    name = filename.replace("\\", "/").split("/")[-1].strip()
    name = name.lstrip(".")
    if not name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    return name


def _sanitize_subfolder(subfolder: str) -> str:
    """Normalize a client-supplied subfolder *relative to the project root*.

    - Strips leading slashes (so the caller can't escape upward).
    - Rejects `..` segments so a crafted value can't break out of the
      project prefix.
    - Guarantees a trailing slash for non-empty values.
    """
    cleaned = subfolder.replace("\\", "/").lstrip("/").strip()
    if not cleaned:
        return ""
    parts = [seg for seg in cleaned.split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise HTTPException(
            status_code=400, detail="Subfolder may not contain '..' segments."
        )
    return "/".join(parts) + "/"


def _owned_project(
    session: Session, project_id: uuid.UUID, owner_sub: str
) -> Project:
    """Look up a project the caller owns, or raise 404."""
    project = session.get(Project, project_id)
    if project is None or project.owner_sub != owner_sub:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _require_key_in_project(key: str, project_id: uuid.UUID) -> None:
    """Reject any key that doesn't live under this project's prefix.

    Without this check, a caller who owns project A could presign a
    download/delete for keys under project B by passing project_id=A and
    key=projects/B/... — ownership is on the project, but the key the
    client supplies bypasses that boundary.
    """
    prefix = _project_prefix(project_id)
    if not key.startswith(prefix):
        raise HTTPException(status_code=403, detail="Key is outside this project.")


def _s3():
    return boto3.client("s3", config=Config(signature_version="s3v4"))


# Every route below is gated by `CurrentDbUser` — that dep verifies the
# Cognito JWT, upserts the user row, and gives us a `.cognito_sub` to
# match against `Project.owner_sub`.


@router.get("", response_model=FileListResponse)
def list_files(
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
    project_id: uuid.UUID = Query(...),
) -> FileListResponse:
    """List every object under this project's prefix.

    Folder placeholder keys (zero-byte, trailing slash) are skipped.
    """
    _owned_project(session, project_id, user.cognito_sub)
    bucket = _resolve_bucket()
    prefix = _project_prefix(project_id)
    s3 = _s3()
    items: list[FileItem] = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                size = int(obj.get("Size", 0))
                if key.endswith("/") and size == 0:
                    continue
                items.append(
                    FileItem(
                        key=key,
                        # Show the key *relative to the project* in the UI;
                        # the full S3 key stays available as `key` for
                        # download/delete round-trips.
                        name=key[len(prefix):] if key.startswith(prefix) else key,
                        size=size,
                        last_modified=obj["LastModified"].isoformat(),
                    )
                )
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 list failed: {exc}") from exc

    items.sort(key=lambda f: f.last_modified, reverse=True)
    return FileListResponse(bucket=bucket, prefix=prefix, items=items)


@router.post("/presign-upload", response_model=PresignUploadResponse)
def presign_upload(
    req: PresignUploadRequest,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> PresignUploadResponse:
    """Presigned PUT URL for one upload into this project."""
    _owned_project(session, req.project_id, user.cognito_sub)
    bucket = _resolve_bucket()
    name = _sanitize_filename(req.filename)
    sub = _sanitize_subfolder(req.subfolder) if req.subfolder is not None else ""
    key = f"{_project_prefix(req.project_id)}{sub}{name}"

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
def presign_download(
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
    project_id: uuid.UUID = Query(...),
    key: str = Query(..., min_length=1),
) -> PresignDownloadResponse:
    """Presigned GET URL for one object in this project."""
    _owned_project(session, project_id, user.cognito_sub)
    _require_key_in_project(key, project_id)
    bucket = _resolve_bucket()
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


@router.post("/convert", response_model=ConvertResponse)
def convert_to_docx(
    req: ConvertRequest,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConvertResponse:
    """Convert a project PDF to an editable Word (.docx).

    Unlike the rest of this service, the bytes flow *through* the API:
    we fetch the PDF from S3, convert it in-process with pdf2docx, and
    write the .docx back next to the source key (same folder, `.docx`
    extension). The new object then shows up in `list_files` and is
    downloaded via the normal presigned-download path.
    """
    _owned_project(session, req.project_id, user.cognito_sub)
    _require_key_in_project(req.key, req.project_id)
    if not req.key.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be converted.")

    bucket = _resolve_bucket()
    s3 = _s3()

    # Size guard before we pull bytes into memory.
    try:
        head = s3.head_object(Bucket=bucket, Key=req.key)
    except ClientError as exc:
        raise HTTPException(status_code=404, detail="Source file not found.") from exc
    if int(head.get("ContentLength", 0)) > CONVERT_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="PDF is too large to convert (limit 50 MB).",
        )

    try:
        obj = s3.get_object(Bucket=bucket, Key=req.key)
        pdf_bytes = obj["Body"].read()
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 read failed: {exc}") from exc

    try:
        docx_bytes, had_text = pdf_to_docx(pdf_bytes)
    except ConversionError as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not convert this PDF: {exc}"
        ) from exc

    dest_key = req.key[: -len(".pdf")] + ".docx"
    try:
        s3.put_object(
            Bucket=bucket,
            Key=dest_key,
            Body=docx_bytes,
            ContentType=DOCX_CONTENT_TYPE,
        )
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 write failed: {exc}") from exc

    prefix = _project_prefix(req.project_id)
    return ConvertResponse(
        key=dest_key,
        name=dest_key[len(prefix):] if dest_key.startswith(prefix) else dest_key,
        scanned=not had_text,
    )


@router.delete("")
def delete_file(
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
    project_id: uuid.UUID = Query(...),
    key: str = Query(..., min_length=1),
) -> dict[str, str]:
    """Delete one object from this project."""
    _owned_project(session, project_id, user.cognito_sub)
    _require_key_in_project(key, project_id)
    bucket = _resolve_bucket()
    try:
        _s3().delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=f"S3 delete failed: {exc}") from exc
    return {"status": "deleted", "key": key}
