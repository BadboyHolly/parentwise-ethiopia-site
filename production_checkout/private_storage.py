"""Private, version-pinned object storage for the five production PDF parts.

This module is deliberately not connected to production order intake yet. The
R2 adapter is constructed only from server-side environment configuration;
staging injects an in-memory mock and never reads the configured bucket.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Mapping, Protocol
from urllib.parse import urlsplit


PARTS = frozenset({1, 2, 3, 4, 5})
DEFAULT_MAX_OBJECT_BYTES = 25 * 1024 * 1024
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ManifestError(ValueError):
    """The configured product manifest is incomplete or unsafe."""


class StorageUnavailable(Exception):
    """A private object could not be safely retrieved."""


@dataclass(frozen=True)
class ProductFile:
    part: int
    key: str
    version_id: str
    sha256: str


class ProductManifest:
    """Validated immutable mapping for exactly five pinned product versions."""

    def __init__(self, files: list[ProductFile] | tuple[ProductFile, ...]):
        if (len(files) != 5 or any(type(f.part) is not int for f in files) or
                {f.part for f in files} != PARTS):
            raise ManifestError("Manifest must contain exactly parts 1 through 5")
        seen: set[str] = set()
        for item in files:
            if (not isinstance(item.key, str) or not item.key or
                item.key.startswith("/") or "\\" in item.key or
                any(segment in {"", ".", ".."} for segment in item.key.split("/"))):
                raise ManifestError("Manifest contains an unsafe object key")
            if (not isinstance(item.version_id, str) or not item.version_id or
                    item.version_id.lower() == "null" or item.version_id.strip() != item.version_id):
                raise ManifestError("Manifest requires an exact object version")
            if not isinstance(item.sha256, str) or not _SHA256.fullmatch(item.sha256):
                raise ManifestError("Manifest requires a lowercase SHA-256 checksum")
            if item.key in seen:
                raise ManifestError("Each product part must have a distinct object key")
            seen.add(item.key)
        self._files = {item.part: item for item in files}

    def get(self, part: int) -> ProductFile:
        if part not in PARTS:
            raise KeyError(part)
        return self._files[part]

    @classmethod
    def from_json(cls, raw: str) -> "ProductManifest":
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError
            expected = {"part", "key", "version_id", "sha256"}
            if any(not isinstance(row, dict) or set(row) != expected or
                   type(row["part"]) is not int or
                   not all(isinstance(row[name], str)
                           for name in ("key", "version_id", "sha256"))
                   for row in data):
                raise ValueError
            files = [ProductFile(
                part=row["part"], key=row["key"],
                version_id=row["version_id"], sha256=row["sha256"],
            ) for row in data]
            return cls(files)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ManifestError("Product PDF manifest is invalid") from exc


@dataclass(frozen=True)
class R2Settings:
    endpoint_url: str
    bucket: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    max_object_bytes: int = DEFAULT_MAX_OBJECT_BYTES

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "R2Settings":
        env = os.environ if environ is None else environ
        endpoint = env.get("R2_ENDPOINT_URL", "").strip()
        bucket = env.get("R2_BUCKET", "").strip()
        access = env.get("R2_ACCESS_KEY_ID", "")
        secret = env.get("R2_SECRET_ACCESS_KEY", "")
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").lower()
        try:
            has_custom_port = parsed.port is not None
        except ValueError:
            has_custom_port = True
        if (parsed.scheme != "https" or
            not re.fullmatch(r"[a-f0-9]{32}\.r2\.cloudflarestorage\.com", host) or
            has_custom_port or parsed.username or parsed.password or
            parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise RuntimeError("R2_ENDPOINT_URL must be an HTTPS Cloudflare account endpoint")
        if not bucket or not access or not secret:
            raise RuntimeError("R2 bucket and server-side credentials are required")
        try:
            maximum = int(env.get("R2_MAX_OBJECT_BYTES", str(DEFAULT_MAX_OBJECT_BYTES)))
        except ValueError as exc:
            raise RuntimeError("R2_MAX_OBJECT_BYTES must be an integer") from exc
        if maximum < 1 or maximum > 250 * 1024 * 1024:
            raise RuntimeError("R2_MAX_OBJECT_BYTES is outside the allowed range")
        return cls(endpoint, bucket, access, secret, maximum)


class VersionedObjectStore(Protocol):
    def read_version(self, *, bucket: str, key: str, version_id: str,
                     max_bytes: int) -> bytes: ...


class R2PrivateObjectStore:
    """S3-compatible Cloudflare R2 reader; never generates signed URLs."""

    def __init__(self, client, settings: R2Settings):
        self._client = client
        self._settings = settings

    @property
    def max_object_bytes(self) -> int:
        return self._settings.max_object_bytes

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "R2PrivateObjectStore":
        settings = R2Settings.from_environment(environ)
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("Install the production checkout requirements for R2 support") from exc
        client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name="auto",
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            config=Config(connect_timeout=3, read_timeout=15,
                          retries={"max_attempts": 2, "mode": "standard"}),
        )
        return cls(client, settings)

    def read_version(self, *, bucket: str, key: str, version_id: str,
                     max_bytes: int) -> bytes:
        if bucket != self._settings.bucket:
            raise StorageUnavailable("Object unavailable")
        body = None
        try:
            result = self._client.get_object(
                Bucket=self._settings.bucket, Key=key, VersionId=version_id,
            )
            returned_version = result.get("VersionId")
            if returned_version != version_id:
                raise StorageUnavailable("Object unavailable")
            body = result["Body"]
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = body.read(min(64 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise StorageUnavailable("Object unavailable")
                chunks.append(chunk)
            return b"".join(chunks)
        except StorageUnavailable:
            raise
        except Exception as exc:
            # Do not expose provider errors, bucket keys, or credentials to clients.
            raise StorageUnavailable("Object unavailable") from exc
        finally:
            if body is not None:
                try:
                    body.close()
                except Exception:
                    pass


class MockObjectStore:
    """Small in-memory versioned object store for tests and isolated staging only."""

    def __init__(self, objects: Mapping[tuple[str, str, str], bytes]):
        self._objects = dict(objects)
        self.reads: list[tuple[str, str, str]] = []

    def read_version(self, *, bucket: str, key: str, version_id: str,
                     max_bytes: int) -> bytes:
        self.reads.append((bucket, key, version_id))
        value = self._objects.get((bucket, key, version_id))
        if value is None or len(value) > max_bytes:
            raise StorageUnavailable("Object unavailable")
        return value


def fetch_verified_part(store: VersionedObjectStore, *, bucket: str,
                        manifest: ProductManifest, part: int,
                        max_bytes: int | None = None) -> tuple[ProductFile, bytes]:
    if max_bytes is None:
        max_bytes = getattr(store, "max_object_bytes", DEFAULT_MAX_OBJECT_BYTES)
    if max_bytes < 1 or max_bytes > 250 * 1024 * 1024:
        raise StorageUnavailable("Object unavailable")
    item = manifest.get(part)
    try:
        content = store.read_version(bucket=bucket, key=item.key,
                                     version_id=item.version_id, max_bytes=max_bytes)
    except StorageUnavailable:
        raise
    except Exception as exc:
        raise StorageUnavailable("Object unavailable") from exc
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise StorageUnavailable("Object unavailable")
    if hashlib.sha256(content).hexdigest() != item.sha256:
        raise StorageUnavailable("Object unavailable")
    return item, content
