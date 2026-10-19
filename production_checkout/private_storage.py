"""Private immutable-release object storage for five production PDF parts.

The adapter never depends on S3 bucket versioning or object VersionId support.
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
_RELEASE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ManifestError(ValueError):
    """The configured product manifest is incomplete or unsafe."""


class StorageUnavailable(Exception):
    """A private object could not be safely retrieved."""


class ObjectAlreadyExists(Exception):
    """An immutable release key already exists and cannot be overwritten."""


def release_key(release_id: str, part: int) -> str:
    if not isinstance(release_id, str) or not _RELEASE.fullmatch(release_id):
        raise ManifestError("Release identifier is invalid")
    if type(part) is not int or part not in PARTS:
        raise ManifestError("Product part is invalid")
    return f"releases/{release_id}/part-{part}.pdf"


@dataclass(frozen=True)
class ProductFile:
    part: int
    key: str
    sha256: str


class ProductManifest:
    """Validated immutable mapping for exactly five release-specific files."""

    def __init__(self, release_id: str, files: list[ProductFile] | tuple[ProductFile, ...]):
        if not isinstance(release_id, str) or not _RELEASE.fullmatch(release_id):
            raise ManifestError("Release identifier is invalid")
        if (len(files) != 5 or any(type(f.part) is not int for f in files) or
                {f.part for f in files} != PARTS):
            raise ManifestError("Manifest must contain exactly parts 1 through 5")
        for item in files:
            if item.key != release_key(release_id, item.part):
                raise ManifestError("Manifest key does not match its immutable release and part")
            if not isinstance(item.sha256, str) or not _SHA256.fullmatch(item.sha256):
                raise ManifestError("Manifest requires a lowercase SHA-256 checksum")
        self.release_id = release_id
        self._files = {item.part: item for item in files}

    def get(self, part: int) -> ProductFile:
        if part not in PARTS:
            raise KeyError(part)
        return self._files[part]

    @classmethod
    def from_json(cls, raw: str) -> "ProductManifest":
        try:
            data = json.loads(raw)
            if (not isinstance(data, dict) or set(data) != {"release_id", "files"} or
                    not isinstance(data["release_id"], str) or
                    not isinstance(data["files"], list)):
                raise ValueError
            files = data["files"]
            if any(not isinstance(row, dict) or set(row) != {"part", "key", "sha256"} or
                   type(row["part"]) is not int or
                   not isinstance(row["key"], str) or not isinstance(row["sha256"], str)
                   for row in files):
                raise ValueError
            return cls(data["release_id"], [
                ProductFile(row["part"], row["key"], row["sha256"]) for row in files
            ])
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
        access, secret = env.get("R2_ACCESS_KEY_ID", ""), env.get("R2_SECRET_ACCESS_KEY", "")
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


class ObjectStore(Protocol):
    def read_object(self, *, bucket: str, key: str, max_bytes: int) -> bytes: ...


class R2PrivateObjectStore:
    """S3-compatible Cloudflare R2 reader; never generates signed URLs."""

    def __init__(self, client, settings: R2Settings):
        self._client, self._settings = client, settings

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
            "s3", endpoint_url=settings.endpoint_url, region_name="auto",
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            config=Config(connect_timeout=3, read_timeout=15,
                          retries={"max_attempts": 2, "mode": "standard"}),
        )
        return cls(client, settings)

    def read_object(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        if bucket != self._settings.bucket or not key.startswith("releases/"):
            raise StorageUnavailable("Object unavailable")
        body = None
        try:
            result = self._client.get_object(Bucket=self._settings.bucket, Key=key)
            body = result["Body"]
            chunks, total = [], 0
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
            raise StorageUnavailable("Object unavailable") from exc
        finally:
            if body is not None:
                try:
                    body.close()
                except Exception:
                    pass


class R2ImmutablePublisher:
    """Create-only publisher. Credentials must belong to a separate publishing identity."""

    def __init__(self, client, bucket: str, max_object_bytes: int = DEFAULT_MAX_OBJECT_BYTES):
        self._client, self._bucket, self._max_bytes = client, bucket, max_object_bytes

    def publish(self, *, release_id: str, part: int, content: bytes,
                expected_sha256: str) -> str:
        key = release_key(release_id, part)
        if (not isinstance(content, bytes) or len(content) > self._max_bytes or
                not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256) or
                hashlib.sha256(content).hexdigest() != expected_sha256):
            raise ManifestError("Publishing content does not match its approved checksum or size")
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=content, ContentType="application/pdf",
                CacheControl="private, no-store", IfNoneMatch="*",
            )
        except Exception as exc:
            response = getattr(exc, "response", {})
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = response.get("Error", {}).get("Code")
            if status == 412 or code in {"PreconditionFailed", "412"}:
                raise ObjectAlreadyExists("Immutable release object already exists") from None
            raise StorageUnavailable("Object could not be published") from None
        return key


class MockObjectStore:
    """In-memory release store for tests and isolated staging only."""

    def __init__(self, objects: Mapping[tuple[str, str], bytes]):
        self._objects = dict(objects)
        self.reads: list[tuple[str, str]] = []

    def read_object(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        self.reads.append((bucket, key))
        value = self._objects.get((bucket, key))
        if value is None or len(value) > max_bytes:
            raise StorageUnavailable("Object unavailable")
        return value


def fetch_verified_part(store: ObjectStore, *, bucket: str,
                        manifest: ProductManifest, part: int,
                        max_bytes: int | None = None) -> tuple[ProductFile, bytes]:
    if max_bytes is None:
        max_bytes = getattr(store, "max_object_bytes", DEFAULT_MAX_OBJECT_BYTES)
    if max_bytes < 1 or max_bytes > 250 * 1024 * 1024:
        raise StorageUnavailable("Object unavailable")
    item = manifest.get(part)
    try:
        content = store.read_object(bucket=bucket, key=item.key, max_bytes=max_bytes)
    except StorageUnavailable:
        raise
    except Exception as exc:
        raise StorageUnavailable("Object unavailable") from exc
    if not isinstance(content, bytes) or len(content) > max_bytes:
        raise StorageUnavailable("Object unavailable")
    if hashlib.sha256(content).hexdigest() != item.sha256:
        raise StorageUnavailable("Object unavailable")
    return item, content
