import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from incentivescope.analyze import analyze
from incentivescope.common import FIELDS, instant
from incentivescope.fetch import fee_usd, normalize, page, usd
from incentivescope.report import render

ROOT = Path(__file__).resolve().parents[1]


class PipelineCheck(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.config = json.loads((ROOT / "configs/demo.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "data/sample/manifest.json").read_text(encoding="utf-8"))
        self.input = ROOT / "data/sample/trades.csv"

    def run_analysis(self, rows=None, **manifest_changes):
        if rows is not None:
            self.input = self.output / "input.csv"
            with self.input.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            self.manifest["sha256"] = hashlib.sha256(self.input.read_bytes()).hexdigest()
            self.manifest["row_count"] = len(rows)
        self.manifest.update(manifest_changes)
        manifest_path = self.output / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return analyze(self.config, self.input, manifest_path, self.output / "report")

    def rows(self):
        with self.input.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_fixed_denominator_windows_liquidation_and_old_orders(self):
        result = self.run_analysis()
        summary = result["summary"]
        self.assertEqual(summary["cohort_size"], 6)
        self.assertEqual(summary["r30"], {"n": 3, "N": 6, "rate": 0.5})
        self.assertEqual(summary["cumulative30"]["n"], 4)
        self.assertEqual(summary["sustained30"]["n"], 1)
        self.assertEqual(summary["voluntary30"]["n"], 4)
        self.assertEqual(summary["strict_r30"]["n"], 2)
        self.assertEqual(summary["r60"]["n"], 2)
        self.assertEqual(result["segments"][1]["size"], 5)
        self.assertEqual(result["segments"][1]["r30_n"], 2)
        self.assertEqual(sum(row["size"] for row in result["cohorts"]), 6)

    def test_integrity_partial_coverage_and_duplicates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.run_analysis(complete=False)
        self.manifest["complete"] = True
        with self.assertRaisesRegex(ValueError, "30 full"):
            self.run_analysis(coverage_end="2024-04-27T00:00:00Z")
        self.manifest["coverage_end"] = "2024-05-29T00:00:00Z"
        rows = self.rows()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_analysis(rows + [rows[0]])

    def test_bad_money_timestamps_and_hash_are_rejected(self):
        rows = self.rows()
        rows[0]["size_delta_usd"] = "NaN"
        with self.assertRaisesRegex(ValueError, "finite"):
            self.run_analysis(rows)
        rows[0]["size_delta_usd"] = "10"
        rows[0]["order_created_at"] = "2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "creation"):
            self.run_analysis(rows)
        with self.assertRaisesRegex(ValueError, "timezone"):
            instant("2024-03-29T00:00:00")

    def test_unknown_creation_withholds_strict_not_general(self):
        rows = self.rows()
        rows[13]["order_created_at"] = ""
        result = self.run_analysis(rows)
        self.assertIsNone(result["summary"]["strict_r30"])
        self.assertEqual(result["summary"]["r30"]["n"], 3)

    def test_no_cohort_and_shorter_60_day_coverage(self):
        rows = [row for row in self.rows() if instant(row["timestamp"]) < instant("2024-04-29T00:00:00Z")]
        result = self.run_analysis(rows, coverage_end="2024-04-29T00:00:00Z")
        self.assertEqual(result["summary"]["r30"]["n"], 3)
        self.assertIsNone(result["summary"]["r60"])

    def test_zero_cohort_reports_na(self):
        self.config["start"] = "2024-03-27T00:00:00Z"
        result = self.run_analysis()
        self.assertEqual(result["summary"]["cohort_size"], 0)
        self.assertIsNone(result["summary"]["r30"]["rate"])

    def test_empty_complete_extract_is_a_zero_not_missing(self):
        result = self.run_analysis([])
        self.assertEqual(result["summary"]["cohort_size"], 0)
        self.assertIsNone(result["summary"]["r30"]["rate"])

    def test_nonmidnight_and_offset_end_uses_next_complete_utc_day(self):
        self.config["end"] = "2024-03-29T20:00:00+08:00"
        result = self.run_analysis()
        self.assertEqual(result["campaign"]["post_anchor"], "2024-03-30T00:00:00Z")
        # Moving the anchor one day admits the return at the original day-30 boundary.
        self.assertEqual(result["summary"]["r30"]["n"], 4)

    def test_missing_fee_does_not_become_zero(self):
        rows = self.rows()
        rows[13]["position_fee_usd"] = ""
        result = self.run_analysis(rows)
        self.assertIsNone(result["activity"]["post"]["position_fee_usd"])
        self.assertIsNone(result["activity"]["fee_ratio"])

    def test_report_is_portable_and_escapes_untrusted_text(self):
        result = self.run_analysis()
        result["campaign"]["name"] = '</script><script>alert("bad")</script>'
        render(result, self.output / "report")
        page_text = (self.output / "report/index.html").read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC DEMONSTRATION", page_text)
        self.assertNotIn('<script>alert("bad")', page_text)
        self.assertIn("\\u003c/script>", page_text)
        self.assertNotIn("$R60$", page_text)
        self.assertEqual(len(list((self.output / "report/figures").glob("*.svg"))), 5)

    def test_real_unverified_boundaries_are_blocked(self):
        self.config["is_synthetic"] = False
        self.config["boundary_status"] = "provisional"
        with self.assertRaisesRegex(ValueError, "boundaries"):
            self.run_analysis(is_synthetic=False)

    def test_unknown_adl_classification_withholds_voluntary_only(self):
        self.config.update(is_synthetic=False, boundary_status="verified")
        result = self.run_analysis(is_synthetic=False)
        self.assertIsNone(result["summary"]["voluntary30"])
        self.assertEqual(result["summary"]["open_or_decrease30"]["n"], 4)
        self.assertEqual(result["summary"]["r30"]["n"], 3)
        with (self.output / "report/wallet_cohorts.csv").open(newline="") as stream:
            self.assertTrue(all(row["voluntary30"] == "" for row in csv.DictReader(stream)))

    def test_gmx_scale_attribution_and_page_cursor(self):
        self.assertEqual(usd("1000000000000000000000000000001"), "1.000000000000000000000000000001")
        tx = "0x" + "1" * 64
        row = {"id": tx + ":19", "eventName": "OrderExecuted", "orderKey": "0x" + "2" * 64,
               "orderType": 2, "account": "0x" + "3" * 40, "marketAddress": "0x" + "4" * 40,
               "sizeDeltaUsd": "1000000000000000000000000000000", "timestamp": 10, "transactionHash": tx}
        normalized = normalize(row, {}, 0, 20)
        self.assertEqual(normalized["account"], row["account"])
        self.assertEqual(normalized["size_delta_usd"], "1")
        self.assertEqual(normalized["order_created_at"], "")
        bad = {"data": {"tradeActions": [{"id": "same"}]}}
        with patch("incentivescope.fetch.graphql", return_value=bad):
            with self.assertRaisesRegex(ValueError, "Pagination"):
                page("q", {"after": "same"}, self.output, "https://gmx.squids.live")

    def test_fee_uses_token_adjusted_price_and_subtracts_discount_once(self):
        fields = {"positionFeeAmount": "50579168", "traderDiscountAmount": "2528958",
                  "collateralTokenPriceMin": "1000112610000000000000000"}
        self.assertEqual(fee_usd(fields), "48.0556209341481")
        self.assertEqual(fee_usd({**fields, "traderDiscountAmount": None}), "")
        with self.assertRaisesRegex(ValueError, "Discount"):
            fee_usd({**fields, "traderDiscountAmount": "50579169"})


if __name__ == "__main__":
    unittest.main()
