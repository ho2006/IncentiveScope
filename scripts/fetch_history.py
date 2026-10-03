"""Fetch seven-day partitions, then publish one validated historical snapshot."""

import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from incentivescope.analyze import validate
from incentivescope.common import FIELDS, instant, iso, write_json
from incentivescope.fetch import NORMALIZATION_VERSION, fetch


def partitions(config):
    start, end = instant(config["coverage_start"]), instant(config["coverage_end"])
    if start >= end:
        raise ValueError("Invalid history coverage")
    while start < end:
        stop = min(start + timedelta(days=7), end)
        yield {**config, "coverage_start": iso(start), "coverage_end": iso(stop)}
        start = stop


def acquire(config, directory):
    path = directory / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (manifest.get("complete") is True
                and manifest.get("normalization_version") == NORMALIZATION_VERSION
                and manifest["coverage_start"] == config["coverage_start"]
                and manifest["coverage_end"] == config["coverage_end"]
                and manifest["source_url"] == config["endpoint"]):
            validate(directory / "trades.csv", manifest, int(config["chain_id"]))
            return manifest
    manifest = fetch(config, directory)
    validate(directory / "trades.csv", manifest, int(config["chain_id"]))
    return manifest


def merge(parts, output, config):
    if not parts:
        raise ValueError("History partitions are empty")
    cursor = instant(config["coverage_start"])
    count = 0
    temporary = output / "trades.csv.tmp"
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for directory, manifest in parts:
                if instant(manifest["coverage_start"]) != cursor:
                    raise ValueError("History partitions contain a gap or overlap")
                if (manifest["source_url"] != config["endpoint"]
                        or manifest["is_synthetic"] != config["is_synthetic"]
                        or manifest.get("normalization_version") != NORMALIZATION_VERSION):
                    raise ValueError("History partition provenance or normalization differs from the request")
                validate(directory / "trades.csv", manifest, int(config["chain_id"]))
                cursor = instant(manifest["coverage_end"])
                with (directory / "trades.csv").open(encoding="utf-8", newline="") as source:
                    writer.writerows(csv.DictReader(source))
                count += manifest["row_count"]
        if cursor != instant(config["coverage_end"]):
            raise ValueError("History partitions do not cover the requested end")
        manifest = {**parts[0][1], "coverage_start": config["coverage_start"],
                    "coverage_end": config["coverage_end"], "row_count": count,
                    "sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
                    "execution_pages": sum(item[1]["execution_pages"] for item in parts),
                    "extracted_at": iso(datetime.now(timezone.utc)),
                    "partitions": [{"path": directory.name, "sha256": item["sha256"],
                                    "coverage_start": item["coverage_start"], "coverage_end": item["coverage_end"],
                                    "row_count": item["row_count"]} for directory, item in parts]}
        # Validate cross-partition event uniqueness before replacing a usable snapshot.
        validate(temporary, manifest, int(config["chain_id"]))
        temporary.replace(output / "trades.csv")
        write_json(output / "manifest.json", manifest)
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/gmx-stip.json"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/gmx-stip"))
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=3)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    jobs = [(part, args.output / "partitions" / part["coverage_start"][:10]) for part in partitions(config)]
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        manifests = list(executor.map(lambda job: acquire(*job), jobs))
    result = merge([(job[1], manifest) for job, manifest in zip(jobs, manifests)], args.output, config)
    print(f"Complete history: {result['row_count']:,} rows, {len(jobs)} partitions, SHA-256 {result['sha256']}")


if __name__ == "__main__":
    main()
