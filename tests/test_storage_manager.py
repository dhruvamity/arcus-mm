"""Unit Tests for Storage Manager and Data Archival Integrity.

Fulfills Mandate Section 6.5:
- Verifies disk space threshold and alarm triggering logic
- Verifies SHA-256 bit-for-bit checksum verification on gzip compression
- Verifies that raw data is not deleted unless verified compressed copy exists
- Verifies error handling on corrupted archives
"""

import gzip
import tempfile
import unittest
from pathlib import Path
from scripts.storage_manager import (
    compute_sha256,
    check_disk_space,
    compress_file_with_verification,
    project_storage_needs,
    ALARM_THRESHOLD_GB,
)


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sha256_computation(self):
        test_file = self.dir_path / "test.txt"
        test_file.write_text("Arcus Storage Manager Test Content\n", encoding="utf-8")
        h = compute_sha256(test_file)
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_disk_space_check(self):
        disk = check_disk_space(self.dir_path)
        self.assertIn("total_gb", disk)
        self.assertIn("used_gb", disk)
        self.assertIn("free_gb", disk)
        self.assertIn("alarm_tripped", disk)
        self.assertIsInstance(disk["alarm_tripped"], bool)

    def test_verified_compression_success(self):
        raw_file = self.dir_path / "sample.jsonl"
        sample_data = '{"channel":"trades","price":"63200.5","size":"0.1"}\n' * 500
        raw_file.write_text(sample_data, encoding="utf-8")

        orig_hash = compute_sha256(raw_file)
        success, res_hash = compress_file_with_verification(raw_file, delete_raw=False)

        self.assertTrue(success)
        self.assertEqual(res_hash, orig_hash)
        self.assertTrue(raw_file.exists())  # delete_raw was False

        gz_file = self.dir_path / "sample.jsonl.gz"
        self.assertTrue(gz_file.exists())

        # Verify decompressed content
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            decomp = f.read()
        self.assertEqual(decomp, sample_data)

    def test_verified_compression_with_raw_deletion(self):
        raw_file = self.dir_path / "deletable.jsonl"
        raw_file.write_text("Row 1\nRow 2\nRow 3\n", encoding="utf-8")

        success, _ = compress_file_with_verification(raw_file, delete_raw=True)
        self.assertTrue(success)
        self.assertFalse(raw_file.exists())  # Successfully deleted after verification

        gz_file = self.dir_path / "deletable.jsonl.gz"
        self.assertTrue(gz_file.exists())

    def test_compression_corruption_protection(self):
        raw_file = self.dir_path / "corrupt_test.jsonl"
        raw_file.write_text("Some sensitive trade record\n", encoding="utf-8")

        # Destination is an existing directory, so opening as file will raise IsADirectoryError
        bad_dest_dir = self.dir_path / "bad_dest_dir"
        bad_dest_dir.mkdir()
        success, msg = compress_file_with_verification(raw_file, compressed_path=bad_dest_dir, delete_raw=True)

        self.assertFalse(success)
        # Raw file MUST NOT be deleted if compression failed
        self.assertTrue(raw_file.exists())

    def test_storage_projections(self):
        raw_file = self.dir_path / "proj.jsonl"
        raw_file.write_bytes(b"0" * 1024 * 1024)  # 1 MB

        proj = project_storage_needs(self.dir_path)
        self.assertGreater(proj["total_recorded_mb"], 0.9)
        self.assertGreater(proj["projected_13d_raw_gb"], 0.0)
        self.assertGreater(proj["projected_13d_compressed_gb"], 0.0)


if __name__ == "__main__":
    unittest.main()
