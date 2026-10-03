"""Validate normalized events, calculate fixed-cohort metrics, export evidence."""

import csv
import hashlib
import json
import math
import re
from datetime import timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

from .common import FIELDS, instant, iso, write_json

ACTIONS = {"increase", "decrease", "liquidation", "adl", "swap", "collateral", "claim", "cancel"}
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")


def proportion(n: int, denominator: int) -> dict:
    return {"n": n, "N": denominator, "rate": n / denominator if denominator else None}


def validate(path: Path, manifest: dict, chain_id: int) -> dict:
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema version")
    if manifest.get("complete") is not True:
        raise ValueError("Incomplete extraction: partial data cannot produce retention results")
    if type(manifest.get("is_synthetic")) is not bool:
        raise ValueError("Manifest must explicitly declare is_synthetic")
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest.get("sha256"):
        raise ValueError("CSV checksum does not match its manifest")
    begin, end = instant(manifest["coverage_start"]), instant(manifest["coverage_end"])
    if begin >= end:
        raise ValueError("Invalid coverage interval")
    # ponytail: event keys stay in RAM; use a DuckDB uniqueness query if extracts exceed memory.
    seen, accounts, count, increases, known_orders, known_fees = set(), set(), 0, 0, 0, 0
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or set(FIELDS) - set(reader.fieldnames):
            raise ValueError("CSV is missing required normalized fields")
        for row in reader:
            count += 1
            if None in row or any(row[key] is None for key in FIELDS):
                raise ValueError(f"Malformed CSV row {count}")
            try:
                if int(row["chain_id"]) != chain_id or int(row["log_index"]) < 0:
                    raise ValueError("Unexpected chain or log index")
                if not ADDRESS.fullmatch(row["account"]) or not HASH.fullmatch(row["tx_hash"]):
                    raise ValueError("Invalid account or transaction hash")
                if row["account"].lower() == "0x" + "0" * 40:
                    raise ValueError("Zero account is not a participant")
                if not HASH.fullmatch(row["order_key"]) or not ADDRESS.fullmatch(row["market"]):
                    raise ValueError("Invalid order key or market")
                if row["action"] not in ACTIONS or row["success"] not in {"true", "false"}:
                    raise ValueError("Unknown action or success value")
                size = Decimal(row["size_delta_usd"])
                fee = Decimal(row["position_fee_usd"]) if row["position_fee_usd"] else None
                if not size.is_finite() or size < 0 or not math.isfinite(float(size)) or (fee is not None and (not fee.is_finite() or fee < 0)):
                    raise ValueError("Amounts must be finite and nonnegative")
                time = instant(row["timestamp"])
                if not begin <= time < end:
                    raise ValueError("Event falls outside declared coverage")
                created = instant(row["order_created_at"]) if row["order_created_at"] else None
                if created and created > time:
                    raise ValueError("Order creation cannot follow execution")
            except (ValueError, InvalidOperation) as error:
                raise ValueError(f"Invalid row {count}: {error}") from error
            key = (chain_id, row["tx_hash"].lower(), int(row["log_index"]))
            if key in seen:
                raise ValueError(f"Duplicate execution event at row {count}")
            seen.add(key)
            accounts.add(row["account"].lower())
            if row["success"] == "true" and row["action"] == "increase" and size > 0:
                increases += 1
                known_orders += created is not None
                known_fees += fee is not None
    if count != manifest.get("row_count"):
        raise ValueError("Manifest row count differs from CSV")
    return {"row_count": count, "unique_accounts": len(accounts),
            "qualifying_increases": increases, "known_order_creations": known_orders,
            "known_position_fees": known_fees,
            "order_created_coverage": known_orders / increases if increases else None,
            "position_fee_coverage": known_fees / increases if increases else None, "notes": []}


def analyze(config: dict, input_path: Path, manifest_path: Path, output_dir: Path,
            exploratory: bool = False) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    synthetic = manifest.get("is_synthetic")
    if synthetic != config.get("is_synthetic"):
        raise ValueError("Config and data disagree about synthetic provenance")
    boundary = config["boundary_status"]
    if boundary not in {"verified", "provisional", "synthetic"} or (not synthetic and boundary == "synthetic"):
        raise ValueError("Invalid boundary status for this dataset")
    if not synthetic and boundary != "verified" and not exploratory:
        raise ValueError("Campaign earning boundaries are unverified; use --exploratory for labelled exploration")
    start, end = instant(config["start"]), instant(config["end"])
    if start >= end:
        raise ValueError("Campaign start must precede end")
    midnight = end.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor = midnight + timedelta(days=end != midnight)
    coverage_start, coverage_end = instant(manifest["coverage_start"]), instant(manifest["coverage_end"])
    if coverage_start > start or coverage_end < anchor + timedelta(days=30):
        raise ValueError("Complete campaign and 30 full post-campaign days are required")
    quality = validate(input_path, manifest, int(config["chain_id"]))
    with duckdb.connect() as db:
        db.execute("SET TimeZone='UTC'")
        db.execute("CREATE TABLE raw AS SELECT * FROM read_csv(?, all_varchar=true)", [str(input_path)])
        db.execute("""CREATE TABLE trades AS SELECT
            chain_id::INTEGER AS chain_id, lower(tx_hash) AS tx_hash, log_index::INTEGER AS log_index,
            lower(account) AS account, lower(order_key) AS order_key, lower(market) AS market,
            timestamp::TIMESTAMPTZ::TIMESTAMP AS timestamp, action, success::BOOLEAN AS success,
            size_delta_usd::DOUBLE AS size_delta_usd,
            position_fee_usd::DECIMAL(38,12) AS position_fee_usd,
            order_created_at::TIMESTAMPTZ::TIMESTAMP AS order_created_at FROM raw""")
        db.execute("CREATE TABLE parameters AS SELECT ?::TIMESTAMP AS start_time, ?::TIMESTAMP AS end_time, ?::TIMESTAMP AS anchor",
                   [value.replace(tzinfo=None) for value in (start, end, anchor)])
        db.execute(Path(__file__).with_name("metrics.sql").read_text(encoding="utf-8"))
        decreases_verified = synthetic or manifest.get("decrease_classification_verified") is True
        if not decreases_verified:
            db.execute("UPDATE outcomes SET voluntary30 = NULL")
        columns = [item[0] for item in db.execute("SELECT * FROM outcomes ORDER BY account").description]
        wallets = [dict(zip(columns, row)) for row in db.fetchall()]
        for row in wallets:
            for field in ("first_trade", "first_qualifying"):
                row[field] = row[field].replace(tzinfo=timezone.utc)
        size = len(wallets)
        summary = {"cohort_size": size}
        for field in ("r30", "cumulative30", "sustained30", "open_or_decrease30", "voluntary30", "strict_r30", "r60"):
            available = not (field == "r60" and coverage_end < anchor + timedelta(days=60))
            available &= not (field == "voluntary30" and not decreases_verified)
            available &= not (field == "strict_r30" and any(row["strict_missing"] for row in wallets))
            summary[field] = proportion(sum(bool(row[field]) for row in wallets), size) if available else None
        kind_label = "new_v2" if manifest.get("history_complete") is True else "first_observed_in_campaign"
        cohorts = []
        for week in sorted({row["entry_week"] for row in wallets}):
            for kind in (kind_label, "observed_existing"):
                group = [row for row in wallets if row["entry_week"] == week and
                         (row["first_trade"] >= start) == (kind == kind_label)]
                if group:
                    n = sum(row["r30"] for row in group)
                    cohorts.append({"entry_week": str(week), "kind": kind, "size": len(group),
                                    "r30_n": n, "r30_rate": n / len(group)})
        weekly, heatmap = [], []
        week_count = min(8, (coverage_end - anchor).days // 7)
        for index in range(week_count):
            lo, hi = anchor + timedelta(days=index * 7), anchor + timedelta(days=(index + 1) * 7)
            n = db.execute("""SELECT count(DISTINCT a.account) FROM actions a JOIN cohort USING(account)
                WHERE is_increase AND timestamp >= ? AND timestamp < ?""", [lo, hi]).fetchone()[0]
            weekly.append({"week": index + 1, "start": iso(lo), "end": iso(hi), **proportion(n, size)})
        for week in sorted({row["entry_week"] for row in wallets}):
            group = [row for row in wallets if row["entry_week"] == week]
            cells = []
            for window in weekly:
                n = db.execute("""SELECT count(DISTINCT a.account) FROM actions a JOIN cohort c USING(account)
                    WHERE is_increase AND c.entry_week = ? AND timestamp >= ? AND timestamp < ?""",
                    [week, instant(window["start"]), instant(window["end"])]).fetchone()[0]
                cells.append({"week": window["week"], "n": n, "rate": n / len(group)})
            heatmap.append({"entry_week": str(week), "size": len(group), "weekly": cells})
        # Rank only on activity before the rebate ends; never select on later returns.
        ordered = sorted(wallets, key=lambda row: (-row["campaign_volume_usd"], row["account"]))
        cut = math.ceil(size * 0.01) if size else 0
        segments = []
        for label, group in (("All addresses", wallets), ("Excluding top 1% (ceil)", ordered[cut:])):
            metric = proportion(sum(row["r30"] for row in group), len(group))
            segments.append({"label": label, "size": len(group), "r30_n": metric["n"], "r30_rate": metric["rate"]})
        robustness = [{"label": name, **value} for name, value in summary.items()
                      if isinstance(value, dict) and name != "r60"]
        mature = [row for row in wallets if row["first_trade"] < midnight - timedelta(days=30)]
        activity = {"eligibleN": len(mature), "pre": None, "post": None, "activity_ratio": None, "fee_ratio": None}
        if coverage_start <= midnight - timedelta(days=30):
            db.execute("CREATE TEMP TABLE mature AS SELECT * FROM cohort WHERE first_trade < ?", [midnight - timedelta(days=30)])
            for label, lo, hi in (("pre", midnight - timedelta(days=30), midnight), ("post", anchor, anchor + timedelta(days=30))):
                days, fees, missing = db.execute("""SELECT coalesce(sum(increases > 0),0),
                    sum(position_fee_usd), coalesce(sum(missing_fees),0)
                    FROM wallet_daily JOIN mature USING(account) WHERE day >= ? AND day < ?""",
                    [lo.date(), hi.date()]).fetchone()
                divisor = 30 * len(mature)
                fee_total = float(fees or 0) if not missing else None
                activity[label] = {"active_address_days": int(days), "activity_rate": days / divisor if divisor else None,
                                   "position_fee_usd": fee_total,
                                   "fee_per_address_day": fee_total / divisor if divisor and fee_total is not None else None}
            for field, source in (("activity_ratio", "activity_rate"), ("fee_ratio", "fee_per_address_day")):
                pre, post = activity["pre"][source], activity["post"][source]
                activity[field] = post / pre if pre and post is not None else None
        if not manifest.get("history_complete"):
            quality["notes"].append("First-observed labels use this extraction window, not complete protocol history.")
        if summary["strict_r30"] is None:
            quality["notes"].append("Strict new-order return is unavailable: order creation timestamps are missing.")
        if not decreases_verified:
            quality["notes"].append("Voluntary30 is withheld: this indexer does not expose secondary order type; ADL can be a market decrease. Open-or-decrease30 and first-observed history may include ADL decreases. Opening-only retention is unaffected.")
        quality["notes"].append("Amounts are preserved in source CSV; volume ranking uses floating point, fees use 12 decimal places.")
        results = {"schema_version": 1,
                   "dataset": {"label": manifest.get("label", "GMX indexed execution events"), "is_synthetic": synthetic,
                               "source_url": manifest["source_url"], "coverage_start": iso(coverage_start),
                               "coverage_end": iso(coverage_end), "boundary_status": boundary,
                               "notes": manifest.get("notes", []) + ([config["boundary_notes"]] if config.get("boundary_notes") else []),
                               "sha256": manifest["sha256"]},
                   "campaign": {"name": config["name"], "start": iso(start), "end": iso(end),
                                "post_anchor": iso(anchor), "overlaps": config.get("overlaps", [])},
                   "measurement_windows": {field: {"start": iso(anchor + timedelta(days=lo)),
                                                   "end_exclusive": iso(anchor + timedelta(days=hi))}
                                           for field, lo, hi in (("r30", 23, 30), ("cumulative30", 0, 30),
                                                                 ("sustained30", 23, 30), ("open_or_decrease30", 23, 30),
                                                                 ("voluntary30", 23, 30), ("strict_r30", 23, 30), ("r60", 53, 60))},
                   "summary": summary, "cohorts": cohorts, "weekly": weekly, "heatmap": heatmap,
                   "segments": segments, "robustness": robustness, "activity": activity,
                   "cost": None, "quality": quality}
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, query in (("wallet_cohorts", "SELECT * FROM outcomes ORDER BY account"),
                            ("wallet_daily", "SELECT * FROM wallet_daily ORDER BY day,account")):
            cursor = db.execute(query)
            with (output_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([column[0] for column in cursor.description])
                writer.writerows(cursor.fetchall())
        write_json(output_dir / "results.json", results)
        return results
