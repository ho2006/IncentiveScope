"""Reconcile the public tables, metric JSON and independently counted receipt."""

import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublishedSnapshotCheck(unittest.TestCase):
    def test_real_snapshot_denominators_and_withheld_claims_reconcile(self):
        output = ROOT / "reports/gmx-stip"
        result = json.loads((output / "results.json").read_text(encoding="utf-8"))
        receipt = json.loads((ROOT / "data/evidence/history-quality/audit.json").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "data/evidence/history-manifest.json").read_text(encoding="utf-8"))
        dune = json.loads((ROOT / "data/evidence/dune/execution-status.json").read_text(encoding="utf-8"))
        self.assertFalse(result["dataset"]["is_synthetic"])
        self.assertEqual(result["dataset"]["sha256"], receipt["csv_sha256"])
        self.assertEqual(result["dataset"]["sha256"], manifest["sha256"])
        self.assertIsNone(result["summary"]["voluntary30"])
        self.assertIsNone(result["cost"])
        self.assertEqual(result["cross_source"]["status"], dune["status"])
        if dune["status"] == "not_executed":
            self.assertIsNone(result["cross_source"]["query_id"])
            self.assertIsNone(result["cross_source"]["execution_id"])
            self.assertNotIn("validated", result["cross_source"])
        self.assertEqual(result["measurement_windows"]["r30"], {
            "start": "2024-04-19T00:00:00Z", "end_exclusive": "2024-04-26T00:00:00Z"})
        with (output / "wallet_cohorts.csv").open(encoding="utf-8", newline="") as stream:
            wallets = list(csv.DictReader(stream))
        size = len(wallets)
        self.assertEqual(size, result["summary"]["cohort_size"])
        self.assertEqual(size, receipt["summary"]["cohort_size"])
        self.assertEqual(sum(row["size"] for row in result["cohorts"]), size)
        for field, value in result["summary"].items():
            if not isinstance(value, dict):
                continue
            n = sum(row[field] == "True" for row in wallets)
            self.assertEqual((n, size), (value["n"], value["N"]))
            self.assertEqual((n, size), (receipt["summary"][field]["n"], receipt["summary"][field]["N"]))
            self.assertEqual(value["rate"], n / size)
        self.assertTrue(all(row["voluntary30"] == "" for row in wallets))
        self.assertEqual(len(list((output / "figures").glob("*.svg"))), 5)
        page = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn("HISTORICAL DESCRIPTIVE RESEARCH", page)
        self.assertIn(result["reward_allocations"]["total_amount_arb"], page)
        self.assertIn(result["cross_source"]["message"], page)
        self.assertNotIn("$FINDINGS$", page)
