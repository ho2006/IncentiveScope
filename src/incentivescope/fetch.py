"""Fetch indexed GMX executions with stable keyset pagination and raw caches."""

import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .common import FIELDS, instant, iso, write_json

ENDPOINT = "https://gmx.squids.live/gmx-synthetics-arbitrum:prod/api/graphql"
CREATIONS = """query Creations($keys: [String!]!, $after: String!, $limit: Int!) {
  tradeActions(where: {orderKey_in: $keys, eventName_eq: "OrderCreated", id_gt: $after},
               orderBy: id_ASC, limit: $limit) { id orderKey account timestamp }
}"""


def graphql(query: str, variables: dict, endpoint: str = ENDPOINT) -> dict:
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or parsed.netloc != "gmx.squids.live" or parsed.username or parsed.password:
        raise ValueError("Only the public HTTPS GMX Subsquid endpoint is supported")
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = Request(endpoint, body, {"Content-Type": "application/json", "User-Agent": "IncentiveScope/0.1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if payload.get("errors"):
                raise ValueError("GraphQL errors: " + json.dumps(payload["errors"]))
            if not isinstance(payload.get("data", {}).get("tradeActions"), list):
                raise ValueError("Missing tradeActions response; schema may have changed")
            return payload
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable retry state")


def page(query: str, variables: dict, cache_dir: Path, endpoint: str) -> list:
    fingerprint = hashlib.sha256(json.dumps([endpoint, query, variables], sort_keys=True).encode()).hexdigest()
    cached = cache_dir / f"{fingerprint}.json"
    if cached.exists():
        payload = json.loads(cached.read_text(encoding="utf-8"))
    else:
        payload = graphql(query, variables, endpoint)
        write_json(cached, payload)
    rows = payload.get("data", {}).get("tradeActions")
    if not isinstance(rows, list) or payload.get("errors"):
        raise ValueError("Invalid cached GraphQL response")
    identifiers = [row["id"] for row in rows]
    if identifiers != sorted(set(identifiers)) or (identifiers and identifiers[0] <= variables["after"]):
        raise ValueError("Pagination is not strictly increasing; refusing a truncated or duplicate page")
    return rows


def usd(raw: str | None) -> str:
    if raw is None:
        raise ValueError("Execution has no sizeDeltaUsd")
    with localcontext() as context:
        context.prec = 100
        number = Decimal(raw)
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            raise ValueError("Expected nonnegative raw GMX USD integer")
        return format(number / Decimal(10 ** 30), "f")


def normalize(row: dict, creations: dict, start: int, end: int) -> dict:
    if row["eventName"] != "OrderExecuted" or not start <= row["timestamp"] < end:
        raise ValueError("Unexpected event or timestamp from upstream")
    kind = row["orderType"]
    if kind not in {2, 3, 4, 5, 6, 7}:
        raise ValueError("Unrecognized perpetual order type")
    tx_hash, separator, index = row["id"].rpartition(":")
    if not separator or tx_hash.lower() != row["transactionHash"].lower() or not index.isdigit():
        raise ValueError("Cannot derive execution log index from TradeAction id")
    created = creations.get(row["orderKey"])
    if created and created["account"].lower() != row["account"].lower():
        raise ValueError("Order account does not match execution account")
    size = usd(row["sizeDeltaUsd"])
    action = "increase" if kind in {2, 3} else "decrease" if kind in {4, 5, 6} else "liquidation"
    if Decimal(size) == 0 and kind != 7:
        action = "collateral"
    return dict(zip(FIELDS, (
        "42161", row["transactionHash"].lower(), index, row["account"].lower(),
        row["orderKey"].lower(), (row["marketAddress"] or "").lower(),
        iso(datetime.fromtimestamp(row["timestamp"], timezone.utc)), action, "true", size, "",
        iso(datetime.fromtimestamp(created["timestamp"], timezone.utc)) if created else "",
    )))


def fetch(config: dict, output_dir: Path, max_pages: int | None = None) -> dict:
    if int(config["chain_id"]) != 42161:
        raise ValueError("This adapter supports GMX V2 on Arbitrum One only")
    begin, end = instant(config["coverage_start"]), instant(config["coverage_end"])
    if begin >= end or begin.microsecond or end.microsecond:
        raise ValueError("Extraction coverage must be ordered, with whole-second bounds")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive")
    endpoint = config.get("endpoint", ENDPOINT)
    limit = int(config.get("page_size", 500))
    if not 1 <= limit <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "raw"
    cache_dir.mkdir(exist_ok=True)
    query = Path(__file__).with_name("gmx-trades.graphql").read_text(encoding="utf-8")
    variables = {"start": int(begin.timestamp()), "end": int(end.timestamp()), "after": "", "limit": limit}
    target = output_dir / "trades.csv"
    temporary = target.with_suffix(".csv.tmp")
    count, pages, complete = 0, 0, False
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        while max_pages is None or pages < max_pages:
            rows = page(query, variables, cache_dir, endpoint)
            if not rows:
                complete = True
                break
            pages += 1
            keys = sorted({row["orderKey"] for row in rows})
            creation_vars = {"keys": keys, "after": "", "limit": limit}
            creations = {}
            while True:
                created_rows = page(CREATIONS, creation_vars, cache_dir, endpoint)
                if not created_rows:
                    break
                for item in created_rows:
                    if item["orderKey"] in creations:
                        raise ValueError("More than one OrderCreated for an order key")
                    creations[item["orderKey"]] = item
                creation_vars["after"] = created_rows[-1]["id"]
            for row in rows:
                writer.writerow(normalize(row, creations, variables["start"], variables["end"]))
                count += 1
            variables["after"] = rows[-1]["id"]
            print(f"Fetched execution page {pages}: {count} rows", flush=True)
    temporary.replace(target)
    manifest = {"schema_version": 1, "label": "GMX V2 indexed perpetual execution events",
                "is_synthetic": False, "source_url": endpoint,
                "coverage_start": iso(begin), "coverage_end": iso(end), "complete": complete,
                "row_count": count, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "history_complete": False, "execution_pages": pages,
                "extracted_at": iso(datetime.now(timezone.utc)),
                "notes": ["Indexed data, not an independent replay of historical deployed contracts.",
                          "Order types 2–7 only; type 7 is excluded from voluntary participation (liquidation/ADL).",
                          "USD sizeDeltaUsd is scaled by 10^30. Token-denominated fee fields are not converted.",
                          "Missing OrderCreated records remain unknown, never treated as post-campaign creations.",
                          "Raw response caches are immutable snapshots for this request; use a new directory to refresh."]}
    write_json(output_dir / "manifest.json", manifest)
    return manifest
