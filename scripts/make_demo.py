"""Build deterministic synthetic boundary examples, never empirical findings."""

import csv
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from incentivescope.common import FIELDS, instant, iso, write_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    config = json.loads((ROOT / "configs/demo.json").read_text(encoding="utf-8"))
    end = instant(config["end"])
    events = [
        (1, "2023-10-10T12:00:00Z", "increase", "10000", None),
        (2, "2023-10-15T12:00:00Z", "increase", "5000", None),
        (1, "2023-11-16T12:00:00Z", "increase", "10000", None),
        (2, "2023-12-01T12:00:00Z", "increase", "5000", None),
        (3, "2024-01-03T12:00:00Z", "increase", "1200", None),
        (4, "2024-02-07T12:00:00Z", "increase", "2000", None),
        (5, "2024-03-20T12:00:00Z", "collateral", "0", None),
        (6, "2024-03-25T12:00:00Z", "increase", "500", None),
        (7, "2024-03-20T13:00:00Z", "cancel", "100", None),
        (8, config["start"], "increase", "700", None),
        (9, "2023-11-20T12:00:00Z", "liquidation", "400", None),
        (1, iso(end + timedelta(hours=1)), "increase", "800", None),
        (2, iso(end + timedelta(days=2)), "increase", "900", None),
        (1, iso(end + timedelta(days=23, hours=1)), "increase", "200", None),
        (1, iso(end + timedelta(days=24, hours=1)), "increase", "300", None),
        (2, iso(end + timedelta(days=25)), "liquidation", "400", None),
        (3, iso(end + timedelta(days=23)), "decrease", "500", None),
        (4, iso(end + timedelta(days=24)), "increase", "200", iso(end - timedelta(days=1))),
        (6, iso(end + timedelta(days=30)), "increase", "200", None),
        (7, iso(end + timedelta(days=23)), "increase", "300", None),
        (8, iso(end + timedelta(days=29, hours=23)), "increase", "200", None),
        (1, iso(end + timedelta(days=53)), "increase", "200", None),
        (6, iso(end + timedelta(days=59)), "increase", "300", None),
    ]
    destination = ROOT / "data/sample"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "trades.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for index, (account, timestamp, action, size, created) in enumerate(events):
            tx = "0x" + hashlib.sha256(f"synthetic-event-{index}".encode()).hexdigest()
            order = "0x" + hashlib.sha256(f"synthetic-order-{index}".encode()).hexdigest()
            row = dict(zip(FIELDS, ("42161", tx, "1", f"0x{account:040x}", order, "0x" + "1" * 40,
                       timestamp, action, "true", size, "1.25" if action in {"increase", "decrease"} else "",
                       created or iso(instant(timestamp) - timedelta(minutes=5)))))
            writer.writerow(row)
    write_json(destination / "manifest.json", {
        "schema_version": 1, "label": "Deterministic synthetic boundary examples",
        "is_synthetic": True, "source_url": "https://github.com/ho2006/IncentiveScope",
        "coverage_start": "2023-09-20T00:00:00Z", "coverage_end": "2024-05-29T00:00:00Z",
        "complete": True, "history_complete": False, "row_count": len(events),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "notes": ["All accounts, orders and amounts are synthetic. These are software checks, not GMX observations.",
                  "The constructed universe includes non-returners, late entry, closing-only return, liquidation and an old limit order."]})


if __name__ == "__main__":
    main()
