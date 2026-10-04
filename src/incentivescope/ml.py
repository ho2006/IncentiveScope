"""Run the optional, event-time retention experiment from one frozen input."""

import csv
import gzip
import hashlib
import importlib.metadata
import io
import json
import platform
import subprocess
from statistics import median
from datetime import datetime, timezone
from pathlib import Path

from .common import write_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(config, input_path, manifest_path, output_dir, device="cpu"):
    # Core SQL analysis stays usable without installing the ML extra.
    try:
        from .ml_data import build_samples
        from .ml_models import run_models
        from .ml_report import render_ml
    except ModuleNotFoundError as error:
        raise ValueError("Install the optional ML environment: pip install -e '.[ml]'") from error

    data = build_samples(config, input_path, manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    print("ML input validated; time-cutoff sample counts:", flush=True)
    for row in data["split_summary"]:
        print(f"  {row['split']} {row['as_of']}: {row['positive']:,}/{row['n']:,}", flush=True)
    features_path = output_dir / "features.csv.gz"
    with features_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["account", "as_of", "split", "label", *data["feature_names"]])
                writer.writeheader()
                writer.writerows(data["rows"])
    models = run_models(data, output_dir, device=device)
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    versions = {}
    for package in ("incentivescope", "duckdb", "torch", "numpy", "scikit-learn", "matplotlib"):
        versions[package] = importlib.metadata.version(package)
    result = {key: value for key, value in data.items() if key != "rows"}
    result.update(models)
    result["feature_shift"] = []
    for split in data["split_summary"]:
        rows = [row for row in data["rows"] if row["as_of"] == split["as_of"]]
        inactive = [row for row in rows if row["opening_count_30d"] == 0]
        result["feature_shift"].append({
            "as_of": split["as_of"], "split": split["split"], "n": len(rows),
            "no_opening_30d": len(inactive), "returns_among_inactive": sum(row["label"] for row in inactive),
            "median_days_since_last_opening": median(row["days_since_last_opening"] for row in rows),
            "median_opening_count_30d": median(row["opening_count_30d"] for row in rows),
        })
    result["schema_version"] = 1
    result["status"] = "completed"
    result["experiment_name"] = config.get("name", "Opening-return event-time experiment")
    result["provenance"] = {
        "executed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input_sha256": digest(input_path), "manifest_sha256": digest(manifest_path),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "config": config, "code_commit": commit, "tracked_worktree_dirty": dirty,
        "source_sha256": {path.name: digest(path) for path in sorted(Path(__file__).parent.glob("ml*.py"))},
        "python": platform.python_version(), "platform": platform.platform(),
        "versions": versions, "device": device,
        "reproduction_scope": "Same frozen input, code, CPU environment and seeds; cross-platform or CPU/GPU bitwise equivalence is not promised.",
    }
    result["artifacts"] = [{"file": str(path.relative_to(output_dir)).replace("\\", "/"),
                            "bytes": path.stat().st_size, "sha256": digest(path)}
                           for path in sorted(output_dir.rglob("*")) if path.is_file()
                           and path.name not in {"results.json", "artifact-manifest.json", "index.html", "research.md"}
                           and "figures" not in path.parts]
    write_json(output_dir / "results.json", result)
    render_ml(result, output_dir)
    write_json(output_dir / "artifact-manifest.json", {
        "schema_version": 1, "complete": True,
        "files": [{"file": str(path.relative_to(output_dir)).replace("\\", "/"),
                   "bytes": path.stat().st_size, "sha256": digest(path)}
                  for path in sorted(output_dir.rglob("*")) if path.is_file()
                  and path.name != "artifact-manifest.json"],
    })
    print(f"Completed ML research: {output_dir / 'index.html'}", flush=True)
    return result
