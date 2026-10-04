"""Opening-only samples built at explicit UTC cutoffs from frozen events."""

import hashlib
import json
import math
from datetime import timedelta, timezone
from pathlib import Path

import duckdb

from .analyze import validate
from .common import instant, iso

FEATURE_NAMES = tuple(
    f"{name}_{days}d"
    for days in (7, 30, 60)
    for name in ("opening_count", "active_days", "opening_size_usd", "opening_fee_usd")
) + (
    "days_since_first_observed_opening", "days_since_last_opening",
    "pre_campaign_opening", "market_count_30d", "top_market_share_30d",
)
FEATURES = FEATURE_NAMES
LOG_FEATURES = tuple(name for name in FEATURE_NAMES
                     if name not in {"pre_campaign_opening", "top_market_share_30d"})


def _anchors(config: dict) -> tuple:
    start, end = instant(config["campaign_start"]), instant(config["campaign_end"])
    if start >= end:
        raise ValueError("Campaign start must precede end")
    train = [instant(value) for value in config["train_as_of"]]
    validation, test = instant(config["validation_as_of"]), instant(config["test_as_of"])
    cutoffs = train + [validation, test]
    if not train or any(value != value.replace(hour=0, minute=0, second=0, microsecond=0)
                        for value in cutoffs):
        raise ValueError("Nonempty training cutoffs at midnight UTC are required")
    if cutoffs != sorted(set(cutoffs)) or cutoffs[0] <= start or test != end:
        raise ValueError("Cutoffs must increase from campaign start through test_as_of == campaign_end")
    if train[-1] + timedelta(days=30) > validation or validation + timedelta(days=30) > test:
        raise ValueError("Training and validation labels must mature before the next split cutoff")
    anchors = [(value, "train") for value in train] + [(validation, "validation"), (test, "test")]
    return start, end, anchors


def build_samples(config: dict, input_path: Path, manifest_path: Path) -> dict:
    """Return raw numeric features and labels; preprocessing belongs to training."""
    start, end, anchors = _anchors(config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    synthetic, boundary = manifest.get("is_synthetic"), config.get("boundary_status")
    if synthetic != config.get("is_synthetic"):
        raise ValueError("Config and data disagree about synthetic provenance")
    if boundary not in {"verified", "synthetic"} or (not synthetic and boundary != "verified"):
        raise ValueError("ML samples require verified campaign boundaries or synthetic data")
    coverage_start, coverage_end = instant(manifest["coverage_start"]), instant(manifest["coverage_end"])
    if coverage_start > min(start, anchors[0][0] - timedelta(days=60)):
        raise ValueError("Coverage must include the campaign and all 60-day feature windows")
    if coverage_end < anchors[-1][0] + timedelta(days=30):
        raise ValueError("Complete coverage of every 30-day label window is required")
    quality = validate(input_path, manifest, int(config["chain_id"]))
    with duckdb.connect() as db:
        db.execute("SET TimeZone='UTC'")
        db.execute("SET threads=1")
        db.execute("CREATE TABLE raw AS SELECT * FROM read_csv(?, all_varchar=true)", [str(input_path)])
        db.execute("""CREATE TABLE openings AS SELECT lower(account) AS account,
            lower(market) AS market, timestamp::TIMESTAMPTZ::TIMESTAMP AS timestamp,
            size_delta_usd::DOUBLE AS size_usd, position_fee_usd::DOUBLE AS fee_usd
            FROM raw WHERE success = 'true' AND action = 'increase' AND size_delta_usd::DOUBLE > 0""")
        db.execute("CREATE TABLE anchors (as_of TIMESTAMP, split VARCHAR, label_start TIMESTAMP, label_end TIMESTAMP)")
        db.executemany("INSERT INTO anchors VALUES (?, ?, ?, ?)", [
            (time.replace(tzinfo=None), split,
             (time + timedelta(days=23)).replace(tzinfo=None),
             (time + timedelta(days=30)).replace(tzinfo=None)) for time, split in anchors])
        db.execute("""CREATE TABLE cohort AS SELECT p.*, t.account FROM anchors p JOIN openings t
            ON t.timestamp >= ? AND t.timestamp < p.as_of GROUP BY ALL""", [start.replace(tzinfo=None)])
        # Missing fees after a cutoff cannot affect its features or eligibility.
        missing = db.execute("""SELECT count(*) FROM cohort c JOIN openings t USING(account)
            WHERE t.timestamp < c.as_of AND t.fee_usd IS NULL""").fetchone()[0]
        if missing:
            raise ValueError("Eligible pre-cutoff opening events have missing position fees")
        window_columns = []
        for days in (7, 30, 60):
            within = f"t.timestamp >= c.as_of - INTERVAL '{days} days'"
            window_columns.extend((
                f"count(*) FILTER (WHERE {within}) AS opening_count_{days}d",
                f"count(DISTINCT t.timestamp::DATE) FILTER (WHERE {within}) AS active_days_{days}d",
                f"coalesce(sum(t.size_usd) FILTER (WHERE {within}), 0) AS opening_size_usd_{days}d",
                f"coalesce(sum(t.fee_usd) FILTER (WHERE {within}), 0) AS opening_fee_usd_{days}d",
            ))
        db.execute(f"""CREATE TABLE features AS SELECT c.*, {', '.join(window_columns)},
            epoch(c.as_of - min(t.timestamp)) / 86400 AS days_since_first_observed_opening,
            epoch(c.as_of - max(t.timestamp)) / 86400 AS days_since_last_opening,
            (min(t.timestamp) < ?)::INTEGER AS pre_campaign_opening
            FROM cohort c JOIN openings t ON t.account = c.account AND t.timestamp < c.as_of
            GROUP BY c.as_of, c.split, c.label_start, c.label_end, c.account""", [start.replace(tzinfo=None)])
        db.execute("""CREATE TABLE market_features AS WITH sizes AS (
            SELECT c.as_of, c.account, t.market, sum(t.size_usd) AS volume
            FROM cohort c JOIN openings t ON t.account = c.account
              AND t.timestamp >= c.as_of - INTERVAL '30 days' AND t.timestamp < c.as_of
            GROUP BY c.as_of, c.account, t.market)
            SELECT as_of, account, count(*) AS market_count_30d,
                max(volume) / sum(volume) AS top_market_share_30d
            FROM sizes GROUP BY as_of, account""")
        selected = ", ".join(f"f.{name}" for name in FEATURE_NAMES[:-2])
        cursor = db.execute(f"""SELECT f.account, f.as_of, f.split,
            EXISTS (SELECT 1 FROM openings t WHERE t.account = f.account
                AND t.timestamp >= f.label_start AND t.timestamp < f.label_end)::INTEGER AS label,
            {selected}, coalesce(m.market_count_30d, 0) AS market_count_30d,
            coalesce(m.top_market_share_30d, 0) AS top_market_share_30d
            FROM features f LEFT JOIN market_features m USING(as_of, account)
            ORDER BY f.as_of, f.account""")
        names = [column[0] for column in cursor.description]
        rows = [dict(zip(names, values)) for values in cursor.fetchall()]
    for row in rows:
        row["as_of"] = iso(row["as_of"].replace(tzinfo=timezone.utc))
        for name in FEATURE_NAMES:
            row[name] = float(row[name])
            if not math.isfinite(row[name]) or row[name] < 0:
                raise ValueError(f"Feature {name} must be finite and nonnegative")
        if not 0 <= row["top_market_share_30d"] <= 1:
            raise ValueError("Top market share must fall in [0, 1]")
    summaries = []
    for time, split in anchors:
        selected_rows = [row for row in rows if row["as_of"] == iso(time)]
        summaries.append({"split": split, "as_of": iso(time),
                          "label_start": iso(time + timedelta(days=23)),
                          "label_end": iso(time + timedelta(days=30)),
                          "n": len(selected_rows), "positive": sum(row["label"] for row in selected_rows),
                          "unique_accounts": len({row["account"] for row in selected_rows})})
    expected_dates = set()
    by_date = {row["as_of"]: row for row in summaries}
    for expected in config.get("expected_counts", []):
        date = iso(instant(expected["as_of"]))
        if date in expected_dates or date not in by_date:
            raise ValueError("Expected counts contain duplicate or unknown cutoffs")
        expected_dates.add(date)
        if any(by_date[date][name] != expected[name] for name in ("n", "positive")):
            raise ValueError(f"Sample counts differ from the frozen reference at {date}")
    notes = list(manifest.get("notes", []))
    if manifest.get("history_complete") is not True:
        notes.append("First-observed opening age and pre-campaign activity use the extraction window, not complete protocol history.")
    notes.append("Features use successful positive-size increases strictly before each cutoff; labels use [cutoff+23 days, cutoff+30 days).")
    quality["notes"] = quality["notes"] + notes
    return {
        "schema_version": 1, "rows": rows,
        "feature_names": list(FEATURE_NAMES), "log_features": list(LOG_FEATURES),
        "feature_sql_threads": 1,
        "split_summary": summaries,
        "training_unique_accounts": len({row["account"] for row in rows if row["split"] == "train"}),
        "campaign": {"start": iso(start), "end": iso(end)},
        "dataset": {"label": manifest.get("label", "GMX indexed execution events"),
                    "is_synthetic": synthetic, "source_url": manifest["source_url"],
                    "sha256": manifest["sha256"], "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    "coverage_start": iso(coverage_start), "coverage_end": iso(coverage_end),
                    "history_complete": manifest.get("history_complete") is True,
                    "boundary_status": boundary, "row_count": manifest["row_count"], "notes": notes},
        "quality": quality,
    }
