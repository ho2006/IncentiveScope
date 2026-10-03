"""Independent stdlib quality profile and fixed-cohort recount of the frozen CSV."""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from pathlib import Path


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def audit(input_dir, config, output_dir, results_path):
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    path = input_dir / "trades.csv"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == manifest["sha256"]
    start, end = map(timestamp, (config["start"], config["end"]))
    anchor = end.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor += timedelta(days=end != anchor)
    coverage_start, coverage_end = map(timestamp, (manifest["coverage_start"], manifest["coverage_end"]))
    keys, accounts, cohort, first_trade = set(), set(), set(), {}
    returns = {name: set() for name in ("r30", "cumulative30", "open_or_decrease30", "strict_r30", "r60")}
    sustained_days = defaultdict(set)
    counts, actions, missing_by_action, missing_creation_by_action, zero_by_action = (Counter() for _ in range(5))
    daily = defaultdict(lambda: {"counts": Counter(), "accounts": set()})
    for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
        counts["rows"] += 1
        key = (row["chain_id"], row["tx_hash"].lower(), int(row["log_index"]))
        counts["duplicate_keys"] += key in keys
        keys.add(key)
        account, action, time = row["account"].lower(), row["action"], timestamp(row["timestamp"])
        accounts.add(account)
        actions[action] += 1
        size = Decimal(row["size_delta_usd"])
        fee_missing, created_missing = not row["position_fee_usd"], not row["order_created_at"]
        created = None if created_missing else timestamp(row["order_created_at"])
        counts["fee_missing"] += fee_missing
        counts["created_missing"] += created_missing
        counts["zero_size"] += size == 0
        counts["unsuccessful"] += row["success"] != "true"
        counts["out_of_coverage"] += not coverage_start <= time < coverage_end
        counts["created_after_execution"] += bool(created and created > time)
        missing_by_action[action] += fee_missing
        missing_creation_by_action[action] += created_missing
        zero_by_action[action] += size == 0
        day = daily[time.date().isoformat()]
        day["accounts"].add(account)
        for name, increment in (("rows", 1), (action, 1), ("fee_missing", fee_missing),
                                ("created_missing", created_missing), ("zero_size", size == 0)):
            day["counts"][name] += increment
        increase = row["success"] == "true" and action == "increase" and size > 0
        open_or_decrease = row["success"] == "true" and action in {"increase", "decrease"} and size > 0
        if open_or_decrease:
            first_trade[account] = min(time, first_trade.get(account, time))
        if increase:
            counts["increases"] += 1
            counts["increase_fee_missing"] += fee_missing
            counts["increase_created_missing"] += created_missing
            if start <= time < end:
                cohort.add(account)
            if anchor <= time < anchor + timedelta(days=30):
                returns["cumulative30"].add(account)
            if anchor + timedelta(days=23) <= time < anchor + timedelta(days=30):
                returns["r30"].add(account)
                sustained_days[account].add(time.date())
                if created and created >= end:
                    returns["strict_r30"].add(account)
                if not created:
                    counts["r30_missing_creation_events"] += 1
            if anchor + timedelta(days=53) <= time < anchor + timedelta(days=60):
                returns["r60"].add(account)
        if open_or_decrease and anchor + timedelta(days=23) <= time < anchor + timedelta(days=30):
            returns["open_or_decrease30"].add(account)
    assert counts["rows"] == manifest["row_count"]
    for name in ("duplicate_keys", "out_of_coverage", "created_after_execution"):
        assert counts[name] == 0, name
    assert all(daily[(coverage_start + timedelta(days=index)).date().isoformat()]["counts"]["rows"]
               for index in range((coverage_end - coverage_start).days))
    cursor = coverage_start
    for part in manifest["partitions"]:
        assert timestamp(part["coverage_start"]) == cursor
        cursor = timestamp(part["coverage_end"])
    assert cursor == coverage_end
    summary = {"cohort_size": len(cohort)}
    for name, observed in returns.items():
        summary[name] = {"n": len(cohort & observed), "N": len(cohort)}
    summary["sustained30"] = {"n": sum(len(sustained_days[account]) >= 2 for account in cohort), "N": len(cohort)}
    summary["voluntary30"] = (summary["open_or_decrease30"] if manifest.get("decrease_classification_verified") is True else None)
    history_groups = {}
    for label, group in (("first_observed_in_campaign", {account for account in cohort if first_trade[account] >= start}),
                         ("observed_existing", {account for account in cohort if first_trade[account] < start})):
        history_groups[label] = {"N": len(group), "r30_n": len(group & returns["r30"])}
    comparisons = {}
    if results_path.exists():
        expected = json.loads(results_path.read_text(encoding="utf-8"))["summary"]
        assert summary["cohort_size"] == expected["cohort_size"]
        for name, result in summary.items():
            if name == "cohort_size":
                continue
            if result is None:
                comparisons[name] = expected.get(name) is None
                assert comparisons[name], (name, expected.get(name))
            elif expected.get(name) is not None:
                comparisons[name] = result == {key: expected[name][key] for key in ("n", "N")}
                assert comparisons[name], (name, result, expected[name])
    anomaly = {"order_types": Counter(), "accounts": Counter(), "daily": defaultdict(Counter)}
    for cache in (input_dir / "partitions" / "2023-09-27" / "raw").glob("*.json"):
        payload = json.loads(cache.read_text(encoding="utf-8"))
        for row in payload["data"]["tradeActions"]:
            if row.get("eventName") != "OrderExecuted":
                continue
            kind, account = str(row["orderType"]), row["account"].lower()
            day = datetime.fromtimestamp(row["timestamp"], timezone.utc).date().isoformat()
            anomaly["order_types"][kind] += 1
            anomaly["accounts"][account] += 1
            anomaly["daily"][day][kind] += 1
    anomaly_sizes = []
    with (input_dir / "partitions" / "2023-09-27" / "trades.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["action"] == "increase":
                anomaly_sizes.append(Decimal(row["size_delta_usd"]))
    anomaly_sizes.sort()
    anomaly_rows = sum(anomaly["accounts"].values())
    top_1_percent_count = ceil(len(anomaly["accounts"]) * 0.01)
    output_dir.mkdir(parents=True, exist_ok=True)
    columns = ["day", "rows", "accounts", "increase", "decrease", "liquidation", "collateral",
               "fee_missing", "created_missing", "zero_size"]
    with (output_dir / "daily.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for day, profile in sorted(daily.items()):
            writer.writerow({"day": day, "accounts": len(profile["accounts"]),
                             **{key: profile["counts"][key] for key in columns[1:] if key != "accounts"}})
    receipt = {"csv_sha256": digest, "coverage_start": manifest["coverage_start"],
               "coverage_end": manifest["coverage_end"], "partition_count": len(manifest["partitions"]),
               "daily_count": len(daily), "unique_accounts": len(accounts), "counts": dict(counts),
               "actions": dict(actions), "missing_fee_by_action": dict(missing_by_action),
               "missing_creation_by_action": dict(missing_creation_by_action),
               "zero_size_by_action": dict(zero_by_action), "summary": summary, "history_groups": history_groups,
               "analyzer_comparisons": comparisons,
               "anomalous_partition": {"start": "2023-09-27", "end": "2023-10-04",
                   "order_types": dict(anomaly["order_types"]), "unique_accounts": len(anomaly["accounts"]),
                   "row_count": anomaly_rows, "single_event_accounts": sum(value == 1 for value in anomaly["accounts"].values()),
                   "two_event_accounts": sum(value == 2 for value in anomaly["accounts"].values()),
                   "top_one_percent_accounts": top_1_percent_count,
                   "top_one_percent_events": sum(value for _, value in anomaly["accounts"].most_common(top_1_percent_count)),
                   "later_campaign_cohort_accounts": len(cohort & anomaly["accounts"].keys()),
                   "positive_increase_count": len(anomaly_sizes),
                   "increase_size_usd_floor_percentiles": {
                       str(quantile): str(anomaly_sizes[int((len(anomaly_sizes) - 1) * quantile)]) for quantile in (0.1, 0.5, 0.9)},
                   "top_accounts_by_event_count": anomaly["accounts"].most_common(10),
                   "daily_order_types": dict(anomaly["daily"])}}
    (output_dir / "audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/gmx-stip"))
    parser.add_argument("--config", type=Path, default=Path("configs/gmx-stip.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evidence/history-quality"))
    parser.add_argument("--results", type=Path, default=Path("reports/gmx-stip/results.json"))
    args = parser.parse_args()
    audit(args.input, json.loads(args.config.read_text(encoding="utf-8")), args.output, args.results)
