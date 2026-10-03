import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from incentivescope.common import FIELDS

spec = importlib.util.spec_from_file_location("fetch_history", Path(__file__).parents[1] / "scripts/fetch_history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class HistoryCheck(unittest.TestCase):
    def test_partition_boundaries_are_contiguous_and_keep_partial_last_week(self):
        parts = list(history.partitions({"coverage_start": "2023-09-20T00:00:00Z", "coverage_end": "2023-10-06T00:00:00Z"}))
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[-1]["coverage_end"], "2023-10-06T00:00:00Z")
        for left, right in zip(parts, parts[1:]):
            self.assertEqual(left["coverage_end"], right["coverage_start"])
        with self.assertRaisesRegex(ValueError, "coverage"):
            list(history.partitions({"coverage_start": "2024-01-02T00:00:00Z", "coverage_end": "2024-01-01T00:00:00Z"}))

    def test_merge_validates_every_partition_and_preserves_previous_snapshot_on_failure(self):
        config = {"coverage_start": "2023-09-20T00:00:00Z", "coverage_end": "2023-10-04T00:00:00Z",
                  "chain_id": 42161, "is_synthetic": False, "endpoint": "https://example.org/graphql"}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            chunks = []
            for index, partition in enumerate(history.partitions(config)):
                directory = output / f"week-{index}"
                directory.mkdir()
                row = {"chain_id": "42161", "tx_hash": "0x" + str(index + 1) * 64,
                       "log_index": "1", "account": "0x" + "a" * 40, "order_key": "0x" + "b" * 64,
                       "market": "0x" + "c" * 40, "timestamp": partition["coverage_start"],
                       "action": "increase", "success": "true", "size_delta_usd": "10",
                       "position_fee_usd": "0.01", "order_created_at": ""}
                path = directory / "trades.csv"
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerow(row)
                manifest = {**partition, "source_url": config["endpoint"], "schema_version": 1,
                            "normalization_version": history.NORMALIZATION_VERSION, "complete": True,
                            "row_count": 1, "execution_pages": 1,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                chunks.append((directory, manifest))

            merged = history.merge(chunks, output, config)
            self.assertEqual(merged["row_count"], 2)
            self.assertEqual(merged["execution_pages"], 2)
            self.assertEqual(len(merged["partitions"]), 2)
            self.assertEqual(merged["sha256"], hashlib.sha256((output / "trades.csv").read_bytes()).hexdigest())
            previous_csv = (output / "trades.csv").read_bytes()
            previous_manifest = (output / "manifest.json").read_bytes()

            cases = [("gap", {"coverage_start": "2023-09-28T00:00:00Z"}, "gap"),
                     ("incomplete", {"complete": False}, "Incomplete"),
                     ("corrupt", {"sha256": "0" * 64}, "checksum"),
                     ("wrong source", {"source_url": "https://other.example/graphql"}, "provenance")]
            for label, changes, error in cases:
                with self.subTest(label):
                    invalid = [chunks[0], (chunks[1][0], {**chunks[1][1], **changes})]
                    with self.assertRaisesRegex(ValueError, error):
                        history.merge(invalid, output, config)
                    self.assertEqual((output / "trades.csv").read_bytes(), previous_csv)
                    self.assertEqual((output / "manifest.json").read_bytes(), previous_manifest)
                    self.assertFalse((output / "trades.csv.tmp").exists())
            with self.assertRaisesRegex(ValueError, "requested end"):
                history.merge(chunks[:1], output, config)
            with self.assertRaisesRegex(ValueError, "empty"):
                history.merge([], output, config)

            # Each file is individually valid, but a reused event key must fail the whole merge.
            path = chunks[1][0] / "trades.csv"
            path.write_text(path.read_text(encoding="utf-8").replace("0x" + "2" * 64, "0x" + "1" * 64),
                            encoding="utf-8")
            chunks[1][1]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                history.merge(chunks, output, config)
            self.assertEqual((output / "trades.csv").read_bytes(), previous_csv)
            self.assertEqual(json.loads((output / "manifest.json").read_bytes()), json.loads(previous_manifest))
