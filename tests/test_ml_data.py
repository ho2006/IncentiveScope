"""Temporal feature boundaries and frozen-cohort checks without ML dependencies."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from incentivescope.common import FIELDS
from incentivescope.ml_data import FEATURE_NAMES, LOG_FEATURES, build_samples


class MLDataCheck(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.input = self.directory / "trades.csv"
        self.manifest_path = self.directory / "manifest.json"
        self.config = {
            "chain_id": 42161, "is_synthetic": True, "boundary_status": "synthetic",
            "campaign_start": "2023-11-01T00:00:00Z", "campaign_end": "2024-03-01T00:00:00Z",
            "train_as_of": ["2023-11-15T00:00:00Z"],
            "validation_as_of": "2024-01-01T00:00:00Z", "test_as_of": "2024-03-01T00:00:00Z",
        }
        self.manifest = {
            "schema_version": 1, "complete": True, "is_synthetic": True,
            "source_url": "https://example.org/synthetic", "history_complete": False,
            "coverage_start": "2023-09-01T00:00:00Z", "coverage_end": "2024-04-01T00:00:00Z",
        }
        self.events = []

    def event(self, time, account=1, size=100, fee=1, market=1, action="increase", success="true"):
        index = len(self.events) + 1
        self.events.append({
            "chain_id": "42161", "tx_hash": f"0x{index:064x}", "log_index": "1",
            "account": f"0x{account:040x}", "order_key": f"0x{index:064x}",
            "market": f"0x{market:040x}", "timestamp": time, "action": action,
            "success": success, "size_delta_usd": str(size),
            "position_fee_usd": "" if fee is None else str(fee), "order_created_at": time,
        })

    def build(self):
        with self.input.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.events)
        self.manifest.update(row_count=len(self.events), sha256=hashlib.sha256(self.input.read_bytes()).hexdigest())
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return build_samples(self.config, self.input, self.manifest_path)

    def test_utc_boundaries_cohort_activity_markets_and_labels(self):
        self.event("2023-10-01T00:00:00Z")
        self.event("2023-11-01T00:00:00Z", account=2)
        self.event("2023-11-08T00:00:00Z", size=300, market=2)
        self.event("2023-11-08T23:59:59Z", size=100, market=2)
        self.event("2023-11-14T23:59:59Z", size=100)
        self.event("2023-11-15T00:00:00Z", account=3)
        self.event("2023-11-14T23:00:00Z", account=4, success="false")
        self.event("2023-11-14T23:00:00Z", account=5, size=0)
        self.event("2023-11-14T23:00:00Z", account=6, action="decrease")
        self.event("2023-12-07T23:59:59Z", account=2)
        self.event("2023-12-08T00:00:00Z")  # Included label start.
        self.event("2023-12-15T00:00:00Z", account=2)  # Excluded label end.
        result = self.build()
        training = [row for row in result["rows"] if row["split"] == "train"]
        self.assertEqual([row["account"] for row in training], [f"0x{value:040x}" for value in (1, 2)])
        first, inactive = training
        self.assertEqual(first["opening_count_7d"], 3)
        self.assertEqual(first["active_days_7d"], 2)
        self.assertEqual(first["opening_size_usd_7d"], 500)
        self.assertEqual(first["opening_fee_usd_7d"], 3)
        self.assertEqual(first["market_count_30d"], 2)
        self.assertAlmostEqual(first["top_market_share_30d"], 0.8)
        self.assertEqual(first["days_since_first_observed_opening"], 45)
        self.assertAlmostEqual(first["days_since_last_opening"], 1 / 86400)
        self.assertEqual(first["pre_campaign_opening"], 1)
        self.assertEqual(first["label"], 1)
        self.assertEqual(inactive["opening_count_7d"], 0)
        self.assertEqual(inactive["opening_fee_usd_7d"], 0)
        self.assertEqual(inactive["pre_campaign_opening"], 0)
        self.assertEqual(inactive["label"], 0)
        self.assertEqual(result["split_summary"][0]["positive"], 1)
        self.assertEqual(len(FEATURE_NAMES), 17)
        self.assertEqual(len(LOG_FEATURES), 15)
        self.assertFalse({"label", "account", "as_of", "r30", "campaign_volume_usd"} & set(FEATURE_NAMES))
        self.assertTrue(any("not complete protocol history" in note for note in result["dataset"]["notes"]))

    def test_future_mutations_leave_earlier_features_and_cohort_unchanged(self):
        self.event("2023-11-02T00:00:00Z")
        self.event("2023-11-02T00:00:00Z", account=2)
        before = self.build()
        self.event("2024-03-24T00:00:00Z", account=3, fee=None)
        self.event("2024-03-25T00:00:00Z", size=999999)
        after = self.build()
        for split in ("train", "validation", "test"):
            feature_rows = lambda data: [
                {name: row[name] for name in ("account", "as_of", *FEATURE_NAMES)}
                for row in data["rows"] if row["split"] == split]
            self.assertEqual(feature_rows(before), feature_rows(after))
        self.assertEqual(after["split_summary"][-1]["n"], 2)
        self.assertEqual(after["split_summary"][-1]["positive"], 1)
        stale = next(row for row in after["rows"] if row["split"] == "test")
        self.assertEqual(stale["opening_count_60d"], 0)
        self.assertEqual(stale["market_count_30d"], 0)
        self.assertEqual(stale["top_market_share_30d"], 0)

    def test_missing_feature_fee_fails_but_irrelevant_events_do_not(self):
        self.event("2023-11-02T00:00:00Z", fee=None)
        with self.assertRaisesRegex(ValueError, "missing position fees"):
            self.build()
        self.events[0]["position_fee_usd"] = "1"
        self.event("2023-11-02T00:00:00Z", account=2, fee=None, size=0)
        self.event("2023-11-02T00:00:00Z", account=3, fee=None, action="decrease")
        self.assertEqual(self.build()["split_summary"][0]["n"], 1)

    def test_maturity_cutoff_coverage_provenance_and_reference_guards(self):
        self.event("2023-11-02T00:00:00Z")
        self.config["validation_as_of"] = "2023-12-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "mature"):
            self.build()
        self.config["validation_as_of"] = "2024-01-01T12:00:00Z"
        with self.assertRaisesRegex(ValueError, "midnight"):
            self.build()
        self.config["validation_as_of"] = "2024-02-15T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "mature"):
            self.build()
        self.config["validation_as_of"] = "2024-01-01T00:00:00Z"
        self.manifest["coverage_start"] = "2023-10-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "60-day"):
            self.build()
        self.manifest["coverage_start"] = "2023-09-01T00:00:00Z"
        self.manifest["coverage_end"] = "2024-03-30T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "label window"):
            self.build()
        self.manifest["coverage_end"] = "2024-04-01T00:00:00Z"
        self.config["expected_counts"] = [{"as_of": "2024-03-01T00:00:00Z", "n": 2, "positive": 0}]
        with self.assertRaisesRegex(ValueError, "frozen reference"):
            self.build()
        self.config.pop("expected_counts")
        self.config.update(is_synthetic=False, boundary_status="provisional")
        self.manifest["is_synthetic"] = False
        with self.assertRaisesRegex(ValueError, "verified campaign"):
            self.build()


if __name__ == "__main__":
    unittest.main()
