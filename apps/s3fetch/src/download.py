"""Mirror an S3 prefix into a local case directory.

Idempotent: a per-case `manifest.json` records each object's ETag. On a
re-run, objects whose ETag matches the manifest and whose local file is
still present are skipped. Everything else is (re-)downloaded.

Manifest layout (JSON, written to data/case/s3/<id>/manifest.json):

{
  "id": "5124226",
  "bucket": "my-bucket",
  "prefix": "case/5124226/",
  "last_pulled_at": "2026-05-22T15:32:11+00:00",
  "counts": {
    "new_downloads": 12,
    "skipped_already_present": 3,
    "total_objects": 15
  },
  "objects": [
    {
      "key": "case/5124226/discovery/exhibit-a.pdf",
      "downloaded_path": "docs/discovery/exhibit-a.pdf",
      "size": 184321,
      "etag": "\"d41d8cd98f00b204e9800998ecf8427e\"",
      "last_modified": "2026-05-21T19:04:00+00:00",
      "sha256": "...",
      "downloaded_at": "2026-05-22T15:32:11+00:00"
    }
  ]
}
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from rich.console import Console


console = Console()


@dataclass(frozen=True)
class S3Target:
    """Resolved (bucket, prefix, id) — everything the puller needs."""

    bucket: str
    prefix: str
    id: str

    @property
    def case_dir(self) -> Path:
        return Path("data/case/s3") / self.id


def case_dir(id_: str) -> Path:
    return Path("data/case/s3") / id_


def parse_uri(uri: str) -> tuple[str, str]:
    """Split `s3://bucket/some/prefix/` into ('bucket', 'some/prefix/').

    Trailing slash is preserved on the prefix; an empty path means "whole
    bucket". Raises ValueError on a non-s3 URI.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Not an s3:// URI: {uri!r}")
    prefix = parsed.path.lstrip("/")
    return parsed.netloc, prefix


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s or "default"


def derive_id(bucket: str, prefix: str) -> str:
    """Build a stable directory id from the prefix's last segment, or bucket."""
    last = prefix.rstrip("/").rsplit("/", 1)[-1] if prefix else ""
    return _slug(last or bucket)


def resolve_target(
    *,
    uri: Optional[str],
    bucket: Optional[str],
    prefix: Optional[str],
    id_: Optional[str],
) -> S3Target:
    """Reconcile the three input forms into one canonical target.

    Accepts either `uri=s3://bucket/prefix` OR explicit `bucket`+`prefix`.
    `id_` overrides the derived directory name when given.
    """
    if uri:
        if bucket or prefix:
            raise ValueError("Pass --uri OR --bucket/--prefix, not both.")
        bucket, prefix = parse_uri(uri)
    if not bucket:
        raise ValueError(
            "S3 source required. Set LAWAGENT_S3_URI, or pass --uri / --bucket."
        )
    prefix = prefix or ""
    return S3Target(bucket=bucket, prefix=prefix, id=id_ or derive_id(bucket, prefix))


def _iter_objects(s3, bucket: str, prefix: str) -> Iterator[dict]:
    """Paginated list_objects_v2 — yield every object dict under the prefix."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            # Folder placeholders show up as zero-byte keys ending in "/".
            if obj["Key"].endswith("/") and obj.get("Size", 0) == 0:
                continue
            yield obj


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _previous_by_key(prev: dict) -> dict[str, dict]:
    return {o["key"]: o for o in prev.get("objects", []) if "key" in o}


def _local_relpath(key: str, prefix: str) -> Path:
    """Map an S3 key to its path under `docs/` (drop the leading prefix)."""
    rel = key[len(prefix):] if prefix and key.startswith(prefix) else key
    return Path("docs") / rel.lstrip("/")


def pull(target: S3Target) -> dict:
    """Mirror everything under `target.prefix` into `data/case/s3/<id>/docs/`.

    Returns the freshly written manifest dict.
    """
    base = target.case_dir
    docs_dir = base / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = base / "manifest.json"

    s3 = boto3.client("s3")
    prev = _load_manifest(manifest_path)
    prev_by_key = _previous_by_key(prev)

    new_objects: list[dict] = []
    new_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        for obj in _iter_objects(s3, target.bucket, target.prefix):
            key = obj["Key"]
            etag = obj["ETag"]
            rel = _local_relpath(key, target.prefix)
            local = base / rel
            prior = prev_by_key.get(key)
            if prior and prior.get("etag") == etag and local.exists():
                new_objects.append(prior)
                skipped_count += 1
                continue

            local.parent.mkdir(parents=True, exist_ok=True)
            console.print(f"  ↓ s3://{target.bucket}/{key}")
            s3.download_file(target.bucket, key, str(local))
            new_objects.append({
                "key": key,
                "downloaded_path": str(rel),
                "size": obj.get("Size"),
                "etag": etag,
                "last_modified": obj["LastModified"].isoformat(timespec="seconds"),
                "sha256": _sha256(local),
                "downloaded_at": now,
            })
            new_count += 1
    except ClientError as exc:
        # Surface the AWS error code cleanly — boto3 default repr is noisy.
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"S3 {code}: {msg}") from exc

    manifest = {
        "id": target.id,
        "bucket": target.bucket,
        "prefix": target.prefix,
        "last_pulled_at": now,
        "counts": {
            "new_downloads": new_count,
            "skipped_already_present": skipped_count,
            "total_objects": len(new_objects),
        },
        "objects": new_objects,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
