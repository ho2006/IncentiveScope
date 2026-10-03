import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("reconcile_dune", Path(__file__).parents[1] / "scripts/reconcile_dune.py")
dune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dune)


class DuneReconciliationCheck(unittest.TestCase):
    def test_only_complete_unique_bound_exports_can_agree_and_synthetic_never_validates(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            daily_path, retention_path, provenance_path, local_path, results_path, daily_sql, retention_sql = (
                directory / name for name in ("daily.csv", "retention.csv", "provenance.json", "local.csv",
                                             "results.json", "daily.sql", "retention.sql"))
            daily = [{"day": day, **dict.fromkeys(dune.DAILY_FIELDS, 0), **dict.fromkeys(dune.AUDIT_FIELDS, 0),
                      "rows": 3, "accounts": 2, "increase": 2, "decrease": 1, "position_rows": 3, "execution_rows": 3}
                     for day in ("2024-01-01", "2024-01-02")]
            retention = [{"metric": name, "numerator": 1, "denominator": 2, "rate": "0.5", "strict_unknown_events": 0}
                         for name in dune.METRICS]

            def csv_file(path, fields, rows):
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(rows)

            def inputs(daily_rows=None, retention_rows=None, provenance_changes=None):
                csv_file(daily_path, ("day", *dune.DAILY_FIELDS, *dune.AUDIT_FIELDS), daily if daily_rows is None else daily_rows)
                csv_file(retention_path, ("metric", "numerator", "denominator", "rate", "strict_unknown_events"),
                         retention if retention_rows is None else retention_rows)
                provenance = {"schema_version": 1, "is_synthetic": True,
                              "coverage_start": "2024-01-01T00:00:00Z", "coverage_end": "2024-01-03T00:00:00Z",
                              "campaign_start": "2023-11-15T00:00:01Z", "campaign_end": "2024-03-27T00:00:00Z"}
                for name, path, sql in (("daily_audit", daily_path, daily_sql), ("retention", retention_path, retention_sql)):
                    provenance[name] = {"query_id": 1, "execution_id": "synthetic-test-only", "complete": True,
                                        "executed_at": "2026-10-03T00:00:00Z", "csv_sha256": dune.digest(path),
                                        "sql_sha256": dune.digest(sql)}
                if provenance_changes:
                    provenance_changes(provenance)
                provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
                return dune.reconcile(daily_path, retention_path, provenance_path, local_path,
                                      results_path, daily_sql, retention_sql)

            daily_sql.write_text("SELECT 'synthetic audit';\n", encoding="utf-8")
            retention_sql.write_text("SELECT 'synthetic retention';\n", encoding="utf-8")
            csv_file(local_path, ("day", *dune.DAILY_FIELDS), daily)
            results_path.write_text(json.dumps({"dataset": {"is_synthetic": True,
                "coverage_start": "2024-01-01T00:00:00Z", "coverage_end": "2024-01-03T00:00:00Z"},
                "campaign": {"start": "2023-11-15T00:00:01Z", "end": "2024-03-27T00:00:00Z"},
                "summary": {"cohort_size": 2, **{name: {"n": 1, "N": 2} for name in dune.METRICS}}}), encoding="utf-8")
            receipt = inputs()
            self.assertEqual(receipt["comparison_status"], "agreement")
            self.assertFalse(receipt["validated"])
            self.assertTrue(receipt["is_synthetic"])
            self.assertEqual(receipt["expected_days"], 2)

            mismatched = [{**row, "numerator": 0, "rate": "0"} if row["metric"] == "r30" else row for row in retention]
            self.assertEqual(inputs(retention_rows=mismatched)["comparison_status"], "differences")
            self.assertEqual(inputs(daily_rows=daily[:1])["issues"][0]["reason"], "date_coverage_mismatch")
            broken_join = [{**daily[0], "duplicate_execution_events": 1}, daily[1]]
            self.assertEqual(inputs(daily_rows=broken_join)["comparison_status"], "invalid_or_incomplete")
            strict_unknown = [{**row, "numerator": "NULL", "rate": "", "strict_unknown_events": 1}
                              if row["metric"] == "strict_r30" else {**row, "strict_unknown_events": 1} for row in retention]
            strict_receipt = inputs(retention_rows=strict_unknown)
            self.assertEqual(strict_receipt["metrics"]["strict_r30"]["status"], "withheld")
            self.assertEqual(strict_receipt["opening_retention_status"], "agreement")
            self.assertFalse(strict_receipt["validated"])
            inconsistent_unknown = [{**row, "strict_unknown_events": 0} if row["metric"] == "r30" else row
                                    for row in strict_unknown]
            inconsistent_receipt = inputs(retention_rows=inconsistent_unknown)
            self.assertEqual(inconsistent_receipt["opening_retention_status"], "invalid_or_incomplete")
            self.assertFalse(inconsistent_receipt["opening_retention_validated"])
            self.assertIn("inconsistent_strict_unknown_events", {issue["reason"] for issue in inconsistent_receipt["issues"]})
            invalid_strict_exports = (
                [{**row, "numerator": 1, "rate": "0.5"} if row["metric"] == "strict_r30" else row for row in strict_unknown],
                [{**row, "denominator": 3} if row["metric"] == "strict_r30" else row for row in strict_unknown],
                [{**row, "rate": "0.6"} if row["metric"] == "strict_r30" else row for row in retention],
            )
            for rows in invalid_strict_exports:
                with self.subTest(strict_export=rows):
                    self.assertEqual(inputs(retention_rows=rows)["opening_retention_status"], "invalid_or_incomplete")
            incomplete = inputs(provenance_changes=lambda value: value["daily_audit"].update(complete=False, sql_sha256="0" * 64))
            self.assertEqual({issue["reason"] for issue in incomplete["issues"]}, {"incomplete_export", "checksum_mismatch"})
            for label, rows in (("duplicate", daily + daily[:1]), ("null", [{**daily[0], "accounts": ""}, daily[1]])):
                with self.subTest(label=label), self.assertRaises(ValueError):
                    inputs(daily_rows=rows)
            with self.assertRaisesRegex(ValueError, "duplicate metric"):
                inputs(retention_rows=retention + retention[:1])
