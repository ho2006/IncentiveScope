"""Validate recorded Dune exports against the frozen GMX case; never execute SQL."""

import argparse
import csv
import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from incentivescope.common import instant, iso, write_json

ROOT = Path(__file__).resolve().parents[1]
DAILY_FIELDS = ("rows", "accounts", "increase", "decrease", "liquidation", "collateral", "zero_size")
AUDIT_FIELDS = (
    "position_rows", "duplicate_position_events", "execution_rows", "duplicate_execution_events",
    "position_join_extra_rows", "execution_join_extra_rows", "unmatched_position_rows", "unmatched_execution_rows",
    "out_of_scope_execution_rows", "unclassified_execution_rows", "unexpected_order_type_rows",
    "invalid_account_rows", "missing_size_rows", "negative_size_rows", "missing_order_type_rows",
    "adl_rows", "unknown_secondary_type_rows", "created_missing", "creation_nonunique",
    "creation_account_mismatch", "creation_after_execution",
)
REJECT_NONZERO = (
    "duplicate_position_events", "duplicate_execution_events", "position_join_extra_rows", "execution_join_extra_rows", "unmatched_position_rows",
    "unmatched_execution_rows", "unclassified_execution_rows", "unexpected_order_type_rows",
    "invalid_account_rows", "missing_size_rows", "negative_size_rows", "missing_order_type_rows",
)
METRICS = ("r30", "cumulative30", "sustained30", "strict_r30", "r60")
STRICT_ONLY_ISSUES = {"strict_creation_unknown", "local_metric_unavailable"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError(f"{name}: expected a nonnegative integer, got {value!r}")
    return int(value)


def read_csv(path, fields, key):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = [field.strip().casefold() for field in reader.fieldnames or []]
        reader.fieldnames = header
        if len(set(header)) != len(header) or not set(fields) <= set(header):
            raise ValueError(f"{path.name}: missing or duplicate columns")
        rows = {}
        for row in reader:
            if None in row or any(row[field] is None for field in fields):
                raise ValueError(f"{path.name}: malformed CSV row")
            grain = row[key].strip().casefold()
            if not grain or grain in rows:
                raise ValueError(f"{path.name}: missing or duplicate {key} grain {grain!r}")
            rows[grain] = row
        return rows


def reconcile(daily_path, retention_path, provenance_path, local_daily_path, results_path,
              daily_sql_path, retention_sql_path):
    results = json.loads(results_path.read_text(encoding="utf-8-sig"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8-sig"))
    issues, differences = [], []
    if not isinstance(provenance, dict) or not isinstance(results, dict):
        raise ValueError("Results and provenance must be JSON objects")
    if provenance.get("schema_version") != 1 or not isinstance(provenance.get("is_synthetic"), bool):
        raise ValueError("Provenance requires schema_version=1 and explicit is_synthetic")
    boundaries = {"coverage_start": results["dataset"]["coverage_start"],
                  "coverage_end": results["dataset"]["coverage_end"],
                  "campaign_start": results["campaign"]["start"], "campaign_end": results["campaign"]["end"]}
    for name, value in boundaries.items():
        if not isinstance(provenance.get(name), str) or instant(provenance[name]) != instant(value):
            issues.append({"reason": "provenance_boundary_mismatch", "field": name})
    sources = {}
    for name, csv_path, sql_path in (("daily_audit", daily_path, daily_sql_path),
                                      ("retention", retention_path, retention_sql_path)):
        source = provenance.get(name, {})
        if not isinstance(source, dict):
            raise ValueError(f"{name}: source provenance must be an object")
        query_id = source.get("query_id")
        execution_id = source.get("execution_id")
        if type(query_id) is not int or query_id <= 0 or not isinstance(execution_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", execution_id):
            raise ValueError(f"{name}: explicit query_id and execution_id required")
        if not isinstance(source.get("executed_at"), str):
            raise ValueError(f"{name}: timezone-qualified executed_at required")
        executed_at = iso(instant(source["executed_at"]))
        if source.get("complete") is not True:
            issues.append({"reason": "incomplete_export", "source": name})
        for field, path in (("csv_sha256", csv_path), ("sql_sha256", sql_path)):
            if source.get(field) != digest(path):
                issues.append({"reason": "checksum_mismatch", "source": name, "field": field})
        sources[name] = {"query_url": f"https://dune.com/queries/{query_id}",
                         "execution_id": source["execution_id"], "executed_at": executed_at,
                         "complete": source.get("complete") is True,
                         "csv_sha256": digest(csv_path), "sql_sha256": digest(sql_path)}

    local_daily = read_csv(local_daily_path, ("day", *DAILY_FIELDS), "day")
    daily = read_csv(daily_path, ("day", *DAILY_FIELDS, *AUDIT_FIELDS), "day")
    start, end = map(instant, (boundaries["coverage_start"], boundaries["coverage_end"]))
    if any((time.hour, time.minute, time.second, time.microsecond) != (0, 0, 0, 0) for time in (start, end)) or end <= start:
        raise ValueError("Daily reconciliation requires ordered full UTC dates")
    expected_days = {(start + timedelta(days=index)).date().isoformat() for index in range((end - start).days)}
    for label, rows in (("local", local_daily), ("dune", daily)):
        for day in rows:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or date.fromisoformat(day).isoformat() != day:
                raise ValueError(f"{label}: invalid UTC date {day!r}")
        if set(rows) != expected_days:
            issues.append({"reason": "date_coverage_mismatch", "source": label,
                           "missing_days": sorted(expected_days - set(rows)),
                           "unexpected_days": sorted(set(rows) - expected_days)})
    audit_totals = dict.fromkeys(AUDIT_FIELDS, 0)
    for day, row in daily.items():
        counts = {field: integer(row[field], f"{day}/{field}") for field in (*DAILY_FIELDS, *AUDIT_FIELDS)}
        if counts["accounts"] > counts["rows"] or sum(counts[field] for field in ("increase", "decrease", "liquidation", "collateral")) != counts["rows"] or counts["zero_size"] > counts["rows"]:
            issues.append({"reason": "invalid_daily_counts", "day": day})
        if counts["position_rows"] != counts["rows"] or counts["execution_rows"] != counts["rows"] + counts["out_of_scope_execution_rows"]:
            issues.append({"reason": "invalid_source_grain", "day": day})
        for field in AUDIT_FIELDS:
            audit_totals[field] += counts[field]
        for field in REJECT_NONZERO:
            if counts[field]:
                issues.append({"reason": "source_quality_failure", "day": day, "field": field, "count": counts[field]})
        if day in local_daily:
            for field in DAILY_FIELDS:
                expected = integer(local_daily[day][field], f"local/{day}/{field}")
                if counts[field] != expected:
                    differences.append({"scope": "daily", "day": day, "field": field,
                                        "dune": counts[field], "gmx": expected})

    retention = read_csv(retention_path, ("metric", "numerator", "denominator", "rate", "strict_unknown_events"), "metric")
    if set(retention) != set(METRICS):
        issues.append({"reason": "metric_coverage_mismatch", "missing": sorted(set(METRICS) - set(retention)),
                       "unexpected": sorted(set(retention) - set(METRICS))})
    metrics = {}
    unknown_counts = set()
    denominators = set()
    for metric in METRICS:
        if metric not in retention:
            continue
        row = retention[metric]
        denominator = integer(row["denominator"], f"{metric}/denominator")
        denominators.add(denominator)
        unknown = integer(row["strict_unknown_events"], f"{metric}/strict_unknown_events")
        unknown_counts.add(unknown)
        expected = results["summary"].get(metric)
        if denominator != results["summary"]["cohort_size"]:
            differences.append({"scope": "retention", "metric": metric, "field": "N",
                                "dune": denominator, "gmx": results["summary"]["cohort_size"]})
        if metric == "strict_r30" and unknown:
            if any(value.strip().casefold() not in {"", "null"} for value in (row["numerator"], row["rate"])):
                issues.append({"reason": "strict_metric_not_withheld", "scope": "retention_export", "unknown_events": unknown})
            issues.append({"reason": "strict_creation_unknown", "metric": metric, "unknown_events": unknown})
            metrics[metric] = {"status": "withheld", "N": denominator}
            continue
        numerator = integer(row["numerator"], f"{metric}/numerator")
        try:
            rate = Decimal(row["rate"])
        except InvalidOperation as error:
            raise ValueError(f"{metric}: invalid or missing rate") from error
        if numerator > denominator or not rate.is_finite() or not 0 <= rate <= 1 or denominator == 0 or abs(rate - Decimal(numerator) / Decimal(denominator)) > Decimal("1e-12"):
            issues.append({"reason": "invalid_retention_counts_or_rate", "metric": metric})
        if expected is None:
            issues.append({"reason": "local_metric_unavailable", "metric": metric})
            metrics[metric] = {"status": "withheld", "n": numerator, "N": denominator}
        else:
            agrees = (numerator, denominator) == (expected["n"], expected["N"])
            metrics[metric] = {"status": "agreement" if agrees else "difference", "n": numerator, "N": denominator}
            if not agrees:
                differences.append({"scope": "retention", "metric": metric,
                                    "dune": {"n": numerator, "N": denominator},
                                    "gmx": {"n": expected["n"], "N": expected["N"]}})
    if len(unknown_counts) != 1:
        issues.append({"reason": "inconsistent_strict_unknown_events", "scope": "retention_export"})
    if len(denominators) != 1:
        issues.append({"reason": "inconsistent_denominators", "scope": "retention_export"})
    synthetic = provenance["is_synthetic"] or results["dataset"].get("is_synthetic") is not False
    status = "invalid_or_incomplete" if issues else "differences" if differences else "agreement"
    opening_status = ("invalid_or_incomplete" if any(not (issue.get("metric") == "strict_r30" and issue["reason"] in STRICT_ONLY_ISSUES) for issue in issues)
                      else "differences" if any(item.get("metric") != "strict_r30" for item in differences)
                      else "agreement" if all(metrics.get(metric, {}).get("status") == "agreement" for metric in METRICS if metric != "strict_r30")
                      else "incomplete")
    return {"schema_version": 1, "is_synthetic": synthetic, "comparison_status": status,
            "validated": status == "agreement" and not synthetic,
            "opening_retention_status": opening_status,
            "opening_retention_validated": opening_status == "agreement" and not synthetic,
            "opening_retention_metrics": [metric for metric in METRICS if metric != "strict_r30"],
            "validation_scope": "Recorded exports, daily counts and five fixed-cohort retention definitions only",
            "provenance_verification": "Supplied export receipt; query execution is not independently authenticated by this script",
            "boundaries": boundaries, "dune_sources": sources,
            "local_daily_sha256": digest(local_daily_path), "local_results_sha256": digest(results_path),
            "local_dataset_sha256": results["dataset"].get("sha256"), "expected_days": len(expected_days),
            "exported_days": len(daily), "audit_totals": audit_totals, "metrics": metrics,
            "issues": issues, "differences": differences,
            "notes": ["Synthetic inputs can exercise the validator but cannot validate a real Dune execution.",
                      "Fees, ADL-adjusted voluntary retention, reward payments and recipient attribution are outside this comparison.",
                      "Daily creation diagnostics and unknown_secondary_type_rows are disclosed; strict R30 requires zero unknown creation events in its own window."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily", type=Path, required=True)
    parser.add_argument("--retention", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-daily", type=Path, default=ROOT / "data/evidence/history-quality/daily.csv")
    parser.add_argument("--results", type=Path, default=ROOT / "reports/gmx-stip/results.json")
    parser.add_argument("--daily-sql", type=Path, default=ROOT / "sql/dune_gmx_stip_daily_audit.sql")
    parser.add_argument("--retention-sql", type=Path, default=ROOT / "sql/dune_gmx_stip_retention.sql")
    args = parser.parse_args()
    try:
        receipt = reconcile(args.daily, args.retention, args.provenance, args.local_daily, args.results,
                            args.daily_sql, args.retention_sql)
    except (OSError, ValueError, KeyError, TypeError) as error:
        receipt = {"schema_version": 1, "validated": False, "comparison_status": "invalid_input",
                   "issues": [{"reason": str(error)}]}
    write_json(args.output, receipt)
    print(f"Dune reconciliation: {receipt['comparison_status']}; validated={receipt['validated']}")
    return 0 if receipt.get("validated") else 2


if __name__ == "__main__":
    raise SystemExit(main())
