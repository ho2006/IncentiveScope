"""Compare a clean CPU reproduction with the published analytical artifacts.

Candidate layout: core/results.json and core/wallet_*.csv; ml/ contains the
complete output of `incentivescope ml`. No ML dependency is needed to verify.
"""

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare_json(reference, candidate, tolerance=0):
    """Return every changed path, separating disclosed floating-point drift."""
    differences, drift = [], []

    def visit(left, right, path):
        if type(left) is not type(right):
            differences.append({"path": path, "reference": left, "candidate": right})
        elif isinstance(left, dict):
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right:
                    differences.append({"path": f"{path}.{key}", "missing_from":
                                        "reference" if key not in left else "candidate"})
                else:
                    visit(left[key], right[key], f"{path}.{key}")
        elif isinstance(left, list):
            if len(left) != len(right):
                differences.append({"path": path, "reference_length": len(left),
                                    "candidate_length": len(right)})
            for index, (a, b) in enumerate(zip(left, right)):
                visit(a, b, f"{path}[{index}]")
        elif left != right:
            item = {"path": path, "reference": left, "candidate": right}
            if isinstance(left, float) and tolerance and math.isclose(
                    left, right, rel_tol=tolerance, abs_tol=tolerance):
                drift.append(item)
            else:
                differences.append(item)

    visit(reference, candidate, "$")
    return differences, drift


def compare_csv(reference, candidate, tolerance=0, numeric_fields=()):
    """Stream exact CSV field comparisons; compression metadata is incidental."""
    opened = lambda path: (gzip.open if path.suffix == ".gz" else Path.open)(
        path, "rt" if path.suffix == ".gz" else "r", encoding="utf-8", newline="")
    differences, drift, rows = [], [], 0
    difference_count = drift_count = 0
    with opened(reference) as left, opened(candidate) as right:
        a, b = csv.DictReader(left), csv.DictReader(right)
        if a.fieldnames != b.fieldnames:
            return {"rows": 0, "difference_count": 1, "differences": [{
                "row": "header", "reference": a.fieldnames, "candidate": b.fieldnames}],
                "accepted_float_drift_count": 0, "accepted_float_drift": []}
        for number, (row_a, row_b) in enumerate(zip_longest(a, b), start=1):
            rows = number
            if row_a is None or row_b is None:
                item = {"row": number, "missing_from": "reference" if row_a is None else "candidate"}
                difference_count += 1
                if len(differences) < 20:
                    differences.append(item)
                continue
            if set(row_a) != set(row_b):
                difference_count += 1
                if len(differences) < 20:
                    differences.append({"row": number, "error": "CSV row has extra columns"})
            for field in a.fieldnames:
                if row_a[field] == row_b[field]:
                    continue
                item = {"row": number, "field": field, "reference": row_a[field], "candidate": row_b[field]}
                close = False
                if tolerance and field in numeric_fields:
                    try:
                        close = math.isclose(float(row_a[field]), float(row_b[field]),
                                             rel_tol=tolerance, abs_tol=tolerance)
                    except (TypeError, ValueError):
                        pass
                if close:
                    drift_count += 1
                    if len(drift) < 20:
                        drift.append(item)
                else:
                    difference_count += 1
                    if len(differences) < 20:
                        differences.append(item)
    return {"rows": rows, "difference_count": difference_count, "differences": differences,
            "accepted_float_drift_count": drift_count, "accepted_float_drift": drift}


def verify(reference_root, candidate_root, input_path, *, core_float_tolerance=0):
    reference_root, candidate_root, input_path = map(Path, (reference_root, candidate_root, input_path))
    reference_core = reference_root / "reports/gmx-stip"
    reference_ml, candidate_ml = reference_core / "ml", candidate_root / "ml"
    reference = {"core": read_json(reference_core / "results.json"),
                 "ml": read_json(reference_ml / "results.json")}
    candidate = {"core": read_json(candidate_root / "core/results.json"),
                 "ml": read_json(candidate_ml / "results.json")}
    checks = []

    def record(name, detail, left_path=None, right_path=None):
        detail.update(name=name, passed=detail["difference_count"] == 0)
        if left_path is not None:
            detail.update(reference_sha256=digest(left_path), candidate_sha256=digest(right_path))
        checks.append(detail)

    def json_check(name, left, right, tolerance=0):
        differences, drift = compare_json(left, right, tolerance)
        record(name, {"difference_count": len(differences), "differences": differences[:20],
                      "accepted_float_drift_count": len(drift), "accepted_float_drift": drift[:20]})

    json_check("core_all_analytical_fields", reference["core"], candidate["core"], core_float_tolerance)
    # These fields describe execution, not the learned parameters or analytical results.
    excluded = {"executed_at", "code_commit", "tracked_worktree_dirty", "platform"}
    def analytical_ml(result):
        return {**{key: value for key, value in result.items() if key not in {"provenance", "artifacts"}},
                "provenance": {key: value for key, value in result["provenance"].items() if key not in excluded}}

    json_check("ml_all_analytical_fields_and_environment", analytical_ml(reference["ml"]),
               analytical_ml(candidate["ml"]))
    json_check("preprocessing", read_json(reference_ml / "preprocessing.json"),
               read_json(candidate_ml / "preprocessing.json"))
    for filename, tolerance, numeric in (
            ("wallet_cohorts.csv", core_float_tolerance, ("campaign_volume_usd",)),
            ("wallet_daily.csv", core_float_tolerance, ("position_fee_usd",))):
        left, right = reference_core / filename, candidate_root / "core" / filename
        record(filename, compare_csv(left, right, tolerance, numeric), left, right)
    for filename in ("features.csv.gz", "predictions.csv.gz", "training_curve.csv"):
        left, right = reference_ml / filename, candidate_ml / filename
        record(filename, compare_csv(left, right), left, right)
    for seed in reference["ml"]["mlp_seed_results"]:
        filename = seed["checkpoint"]
        left, right = reference_ml / filename, candidate_ml / filename
        record(filename, {"difference_count": int(digest(left) != digest(right)), "differences": []}, left, right)
    input_sha = digest(input_path)
    input_hashes = {"downloaded_input": input_sha,
                    "published_core": reference["core"]["dataset"]["sha256"],
                    "regenerated_core": candidate["core"]["dataset"]["sha256"],
                    "published_ml": reference["ml"]["provenance"]["input_sha256"],
                    "regenerated_ml": candidate["ml"]["provenance"]["input_sha256"]}
    record("input_checksum", {"difference_count": int(len(set(input_hashes.values())) != 1),
                              "differences": [], "hashes": input_hashes})
    record("clean_tested_worktree", {"difference_count": int(
        candidate["ml"]["provenance"]["tracked_worktree_dirty"] is not False), "differences": []})
    return {
        "schema_version": 1, "passed": all(check["passed"] for check in checks),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input_sha256": input_sha, "tested_commit": candidate["ml"]["provenance"]["code_commit"],
        "reference_model_commit": reference["ml"]["provenance"]["code_commit"],
        "reference_root": str(reference_root.resolve()), "candidate_root": str(candidate_root.resolve()),
        "scope": "Full frozen-input CPU analytical replay; rendered prose/figures are not byte comparisons. "
                 "This checks reproducibility, not independent full-chain completeness or causal identification.",
        "comparison_policy": {
            "core_float_tolerance": core_float_tolerance,
            "tolerance_rule": "math.isclose with equal relative and absolute tolerances; core JSON floats and "
                              "campaign_volume_usd/position_fee_usd CSV fields only",
            "ml": "Exact analytical JSON, preprocessing, CSV fields and checkpoint bytes",
            "excluded_ml_fields": [f"provenance.{key}" for key in sorted(excluded)] + ["artifacts"],
            "excluded_artifacts_reason": "Hashes of data/weights are checked directly; figures and rendered reports are presentation outputs.",
            "maximum_difference_examples_per_check": 20,
        },
        "reference_environment": reference["ml"]["provenance"],
        "tested_environment": candidate["ml"]["provenance"],
        "verifier": {"sha256": digest(Path(__file__)), "python": platform.python_version(),
                     "platform": platform.platform()},
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-float-tolerance", type=float, default=0,
                        help="Disclosed core-only rounding tolerance; default requires exact values")
    args = parser.parse_args()
    if not math.isfinite(args.core_float_tolerance) or args.core_float_tolerance < 0:
        parser.error("--core-float-tolerance must be finite and nonnegative")
    try:
        receipt = verify(args.reference_root, args.candidate_root, args.input,
                         core_float_tolerance=args.core_float_tolerance)
    except (OSError, KeyError, ValueError, csv.Error) as error:
        receipt = {"schema_version": 1, "passed": False, "error": f"{type(error).__name__}: {error}"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8", newline="\n")
    print(f"Reproduction {'passed' if receipt['passed'] else 'FAILED'}: {args.output}")
    raise SystemExit(0 if receipt["passed"] else 1)


if __name__ == "__main__":
    main()
