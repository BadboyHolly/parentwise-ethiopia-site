"""Unit tests for private versioned storage using in-memory mock objects only."""
import hashlib
import json
import unittest

from production_checkout.private_storage import (
    ManifestError, MockObjectStore, ProductFile, ProductManifest, R2Settings,
    StorageUnavailable, fetch_verified_part,
)


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        self.blobs = {i: f"%PDF-1.4\\nQA DUMMY PART {i}\\n%%EOF".encode() for i in range(1, 6)}
        files = [ProductFile(i, f"product/v1/part-{i}.pdf", f"version-{i}",
                             hashlib.sha256(blob).hexdigest())
                 for i, blob in self.blobs.items()]
        self.manifest = ProductManifest(files)
        self.bucket = "private-test-bucket"
        self.store = MockObjectStore({
            (self.bucket, f"product/v1/part-{i}.pdf", f"version-{i}"): blob
            for i, blob in self.blobs.items()
        })

    def test_exactly_five_files_are_read_by_pinned_version_and_checksum(self):
        for part in range(1, 6):
            item, content = fetch_verified_part(self.store, bucket=self.bucket,
                                                manifest=self.manifest, part=part)
            self.assertEqual(item.part, part)
            self.assertEqual(content, self.blobs[part])
        self.assertEqual(len(self.store.reads), 5)
        self.assertEqual(self.store.reads[0][2], "version-1")

    def test_manifest_rejects_missing_duplicate_or_unsafe_entries(self):
        with self.assertRaises(ManifestError):
            ProductManifest([self.manifest.get(i) for i in range(1, 5)])
        duplicate = [self.manifest.get(i) for i in range(1, 5)] + [
            ProductFile(5, "product/v1/part-4.pdf", "v5",
                        hashlib.sha256(b"x").hexdigest())]
        with self.assertRaises(ManifestError):
            ProductManifest(duplicate)
        unsafe = [ProductFile(i, f"../part-{i}.pdf", "v1",
                              hashlib.sha256(b"x").hexdigest()) for i in range(1, 6)]
        with self.assertRaises(ManifestError):
            ProductManifest(unsafe)

    def test_manifest_json_and_invalid_part(self):
        raw = json.dumps([self.manifest.get(i).__dict__ for i in range(1, 6)])
        self.assertEqual(ProductManifest.from_json(raw).get(5), self.manifest.get(5))
        with self.assertRaises(ManifestError):
            ProductManifest.from_json("[]")
        with self.assertRaises(KeyError):
            self.manifest.get(6)

    def test_missing_object_checksum_mismatch_and_size_limit_fail_closed(self):
        missing = MockObjectStore({})
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(missing, bucket=self.bucket, manifest=self.manifest, part=1)
        corrupt = MockObjectStore({
            (self.bucket, "product/v1/part-1.pdf", "version-1"): b"corrupted"
        })
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(corrupt, bucket=self.bucket, manifest=self.manifest, part=1)
        with self.assertRaises(StorageUnavailable):
            fetch_verified_part(self.store, bucket=self.bucket, manifest=self.manifest,
                                part=1, max_bytes=2)

    def test_r2_configuration_requires_https_account_endpoint_and_credentials(self):
        base = {
            "R2_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
            "R2_BUCKET": "private-files",
            "R2_ACCESS_KEY_ID": "synthetic-access",
            "R2_SECRET_ACCESS_KEY": "synthetic-secret",
        }
        self.assertEqual(R2Settings.from_environment(base).bucket, "private-files")
        for endpoint in ("http://account.r2.cloudflarestorage.com",
                         "https://user:pass@account.r2.cloudflarestorage.com",
                         "https://example.com"):
            invalid = dict(base, R2_ENDPOINT_URL=endpoint)
            with self.assertRaises(RuntimeError):
                R2Settings.from_environment(invalid)
        with self.assertRaises(RuntimeError):
            R2Settings.from_environment(dict(base, R2_SECRET_ACCESS_KEY=""))


if __name__ == "__main__":
    unittest.main()
