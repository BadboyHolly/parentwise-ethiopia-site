"""Unit tests for immutable-release private storage; no network or credentials."""
import hashlib
import io
import json
import unittest

from production_checkout.private_storage import (
    ManifestError, MockObjectStore, ObjectAlreadyExists, ProductFile, ProductManifest,
    R2ImmutablePublisher, R2PrivateObjectStore, R2Settings, StorageUnavailable,
    fetch_verified_part, release_key,
)


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        self.release = "approved-2026-10-19-a1b2c3"
        self.blobs = {i: f"%PDF-1.4\nQA DUMMY PART {i}\n%%EOF".encode() for i in range(1, 6)}
        files = [ProductFile(i, release_key(self.release, i),
                             hashlib.sha256(blob).hexdigest())
                 for i, blob in self.blobs.items()]
        self.manifest = ProductManifest(self.release, files)
        self.bucket = "private-test-bucket"
        self.store = MockObjectStore({
            (self.bucket, release_key(self.release, i)): blob
            for i, blob in self.blobs.items()
        })

    def test_exactly_five_release_keys_are_read_and_verified(self):
        for part in range(1, 6):
            item, content = fetch_verified_part(self.store, bucket=self.bucket,
                                                manifest=self.manifest, part=part)
            self.assertEqual(item.key, f"releases/{self.release}/part-{part}.pdf")
            self.assertEqual(content, self.blobs[part])
        self.assertEqual(len(self.store.reads), 5)

    def test_release_keys_are_unique_and_manifest_rejects_extra_missing_or_changed_key(self):
        self.assertNotEqual(release_key("approved-1", 1), release_key("approved-2", 1))
        with self.assertRaises(ManifestError):
            ProductManifest(self.release, [self.manifest.get(i) for i in range(1, 5)])
        wrong = [self.manifest.get(i) for i in range(1, 5)] + [
            ProductFile(5, "releases/other/part-5.pdf", hashlib.sha256(b"x").hexdigest())]
        with self.assertRaises(ManifestError):
            ProductManifest(self.release, wrong)
        with self.assertRaises(ManifestError):
            release_key("../bad", 1)

    def test_manifest_json_and_invalid_part(self):
        raw = json.dumps({"release_id": self.release, "files": [
            self.manifest.get(i).__dict__ for i in range(1, 6)]})
        self.assertEqual(ProductManifest.from_json(raw).get(5), self.manifest.get(5))
        with self.assertRaises(ManifestError):
            ProductManifest.from_json("[]")
        with self.assertRaises(KeyError):
            self.manifest.get(6)

    def test_r2_adapter_uses_only_supported_unversioned_get_object_and_closes_stream(self):
        blob = self.blobs[1]
        class Client:
            def __init__(inner):
                inner.kwargs = None
                inner.body = io.BytesIO(blob)
            def get_object(inner, **kwargs):
                inner.kwargs = kwargs
                return {"Body": inner.body}
        client = Client()
        settings = R2Settings("https://" + "a" * 32 + ".r2.cloudflarestorage.com",
                              self.bucket, "synthetic-access", "synthetic-secret")
        adapter = R2PrivateObjectStore(client, settings)
        value = adapter.read_object(bucket=self.bucket, key=release_key(self.release, 1),
                                    max_bytes=1024)
        self.assertEqual(value, blob)
        self.assertEqual(client.kwargs, {"Bucket": self.bucket,
                                         "Key": release_key(self.release, 1)})
        self.assertTrue(client.body.closed)
        self.assertNotIn("synthetic-secret", repr(settings))

    def test_r2_adapter_suppresses_provider_errors_and_missing_body(self):
        settings = R2Settings("https://" + "a" * 32 + ".r2.cloudflarestorage.com",
                              self.bucket, "synthetic-access", "synthetic-secret")
        class Failed:
            def get_object(self, **kwargs):
                raise RuntimeError("secret provider detail")
        with self.assertRaises(StorageUnavailable) as caught:
            R2PrivateObjectStore(Failed(), settings).read_object(
                bucket=self.bucket, key=release_key(self.release, 1), max_bytes=1024)
        self.assertEqual(str(caught.exception), "Object unavailable")
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(self.store, bucket=self.bucket, manifest=self.manifest, part=1,
                                max_bytes=2)

    def test_missing_or_changed_object_fails_integrity_check(self):
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(MockObjectStore({}), bucket=self.bucket,
                                manifest=self.manifest, part=1)
        corrupt = MockObjectStore({(self.bucket, release_key(self.release, 1)): b"changed"})
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(corrupt, bucket=self.bucket, manifest=self.manifest, part=1)

    def test_publisher_uses_atomic_create_only_condition_and_rejects_existing_key(self):
        content = self.blobs[1]
        class Client:
            def __init__(inner):
                inner.kwargs = None
                inner.exists = False
            def put_object(inner, **kwargs):
                inner.kwargs = kwargs
                if inner.exists:
                    raise type("ProviderError", (Exception,), {"response":{
                        "ResponseMetadata":{"HTTPStatusCode":412},
                        "Error":{"Code":"PreconditionFailed"}}})()
                inner.exists = True
        client = Client()
        publisher = R2ImmutablePublisher(client, self.bucket)
        key = publisher.publish(release_id=self.release, part=1, content=content,
                                expected_sha256=hashlib.sha256(content).hexdigest())
        self.assertEqual(key, release_key(self.release, 1))
        self.assertEqual(client.kwargs["IfNoneMatch"], "*")
        self.assertEqual(client.kwargs["ContentType"], "application/pdf")
        with self.assertRaises(ObjectAlreadyExists):
            publisher.publish(release_id=self.release, part=1, content=content,
                              expected_sha256=hashlib.sha256(content).hexdigest())
        self.assertTrue(client.exists)

    def test_publisher_rejects_unexpected_file_changes_before_write(self):
        client = type("Client", (), {"put_object": lambda *a, **kw: self.fail("must not write")})()
        publisher = R2ImmutablePublisher(client, self.bucket)
        with self.assertRaises(ManifestError):
            publisher.publish(release_id=self.release, part=1, content=b"changed",
                              expected_sha256=hashlib.sha256(self.blobs[1]).hexdigest())

    def test_mock_backup_restore_revalidates_all_five_checksums(self):
        backup_bucket = "independent-private-backup"
        backup = MockObjectStore({
            (backup_bucket, self.manifest.get(part).key): self.blobs[part]
            for part in range(1, 6)
        })
        restored_bucket = "isolated-restore"
        restored = MockObjectStore({
            (restored_bucket, self.manifest.get(part).key): self.blobs[part]
            for part in range(1, 6)
        })
        # The rehearsal restores only from the independent backup and checks
        # each result against the separately retained release manifest.
        for part in range(1, 6):
            _, backed_up = fetch_verified_part(
                backup, bucket=backup_bucket, manifest=self.manifest, part=part)
            restored._objects[(restored_bucket, self.manifest.get(part).key)] = backed_up
        for part in range(1, 6):
            _, restored_bytes = fetch_verified_part(
                restored, bucket=restored_bucket, manifest=self.manifest, part=part)
            self.assertEqual(restored_bytes, self.blobs[part])
        restored._objects[(restored_bucket, self.manifest.get(3).key)] = b"altered backup"
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(restored, bucket=restored_bucket,
                                manifest=self.manifest, part=3)

    def test_r2_configuration_requires_https_account_endpoint_and_credentials(self):
        base = {
            "R2_ENDPOINT_URL": "https://" + "a" * 32 + ".r2.cloudflarestorage.com",
            "R2_BUCKET": "private-files", "R2_ACCESS_KEY_ID": "synthetic-access",
            "R2_SECRET_ACCESS_KEY": "synthetic-secret",
        }
        self.assertEqual(R2Settings.from_environment(base).bucket, "private-files")
        for endpoint in ("http://account.r2.cloudflarestorage.com",
                         "https://user:pass@account.r2.cloudflarestorage.com",
                         "https://example.com",
                         "https://" + "a" * 32 + ".r2.cloudflarestorage.com:444"):
            with self.assertRaises(RuntimeError):
                R2Settings.from_environment(dict(base, R2_ENDPOINT_URL=endpoint))
        with self.assertRaises(RuntimeError):
            R2Settings.from_environment(dict(base, R2_SECRET_ACCESS_KEY=""))


if __name__ == "__main__":
    unittest.main()
