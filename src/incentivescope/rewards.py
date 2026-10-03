"""Exact recipient allocations from the pinned official GMX STIP artifacts."""

import csv
import hashlib
import io
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .common import atomic_text, iso, write_json

COMMIT = "a85ea3491c19c93bb4b5a002d9b358fb769b7849"
BASE = f"https://raw.githubusercontent.com/gmx-io/gmx-synthetics/{COMMIT}"
TOKEN = "0x912ce59144191c1204e64559fe8253a0e49e6548"
EPOCHS = tuple((date(2023, 11, 15) + timedelta(weeks=i)).isoformat() for i in range(19))
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
FORUM = "https://forum.arbitrum.foundation/t/leveraging-the-stip-grants-program-to-grow-the-gmx-and-arbitrum-defi-ecosystem/23100"


def amount(raw: str) -> int:
    if not isinstance(raw, str) or not INTEGER.fullmatch(raw):
        raise ValueError("Reward amounts must be nonnegative canonical integer strings")
    return int(raw)


def units(raw: int) -> str:
    """No float or Decimal context can round away a reward base unit."""
    whole, fraction = divmod(abs(raw), 10**18)
    return f"{'-' if raw < 0 else ''}{whole}.{fraction:018d}"


def address(value: str) -> str:
    if not isinstance(value, str) or not ADDRESS.fullmatch(value) or int(value, 16) == 0:
        raise ValueError("Expected a nonzero EVM recipient address")
    return value.lower()


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def normalize_distribution(payload: dict, epoch: str) -> tuple[dict, dict | None]:
    if not isinstance(payload, dict) or epoch not in EPOCHS:
        raise ValueError("Unknown STIP distribution epoch")
    if (not isinstance(payload.get("token"), str) or payload["token"].lower() != TOKEN
            or type(payload.get("distributionTypeId")) is not int
            or payload["distributionTypeId"] != 1003
            or payload.get("id") != f"{epoch}_1003"
            or payload.get("chainId", 42161) != 42161):
        raise ValueError("Unexpected STIP token, distribution type, chain or epoch id")
    allocations = payload.get("amounts")
    if not isinstance(allocations, dict) or not allocations:
        raise ValueError("Missing recipient allocations")
    normalized = {}
    for recipient, raw in allocations.items():
        recipient = address(recipient)
        if recipient in normalized:
            raise ValueError("Duplicate recipient after address case normalization")
        normalized[recipient] = amount(raw)
    overrides = payload.get("appliedOverrides")
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise ValueError("Invalid recorded receiver overrides")
        checked = {}
        for original, receiver in overrides.items():
            original, receiver = address(original), address(receiver)
            if original in checked or receiver not in normalized:
                raise ValueError("Duplicate override source or absent override recipient")
            checked[original] = receiver
        overrides = checked
    return normalized, overrides


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "IncentiveScope/0.1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Unreachable retry state")


def cached_source(output_dir: Path, path: str, tree: dict) -> tuple[dict, dict]:
    filename = output_dir / "raw" / path.removeprefix("scripts/incentives/distributions/")
    expected = tree.get(path)
    if expected is None:
        raise ValueError(f"Missing source file in pinned tree: {path}")
    if filename.exists():
        raw = filename.read_bytes()
    else:
        raw = download(f"{BASE}/{path}")
        actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if actual != expected:
            raise ValueError(f"Git blob checksum mismatch: {path}")
        filename.parent.mkdir(parents=True, exist_ok=True)
        temporary = filename.with_suffix(".json.tmp")
        temporary.write_bytes(raw)
        temporary.replace(filename)
    actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if actual != expected:
        raise ValueError(f"Git blob checksum mismatch: {path}")
    return json.loads(raw, object_pairs_hook=unique_object), {
        "url": f"{BASE}/{path}", "git_blob_sha": actual,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def write_csv(path: Path, rows: list[dict]) -> dict:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, stream.getvalue())
    return {"file": path.name, "row_count": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fetch_rewards(output_dir: Path) -> dict:
    """Require all 19 epochs and matching batch totals before publishing a ledger."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tree_path = output_dir / "source-tree.json"
    if not tree_path.exists():
        raw = download(f"https://api.github.com/repos/gmx-io/gmx-synthetics/git/trees/{COMMIT}?recursive=1")
        atomic_text(tree_path, raw.decode("utf-8"))
    source_tree = json.loads(tree_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if source_tree.get("sha") != COMMIT or source_tree.get("truncated") is not False:
        raise ValueError("Expected a complete Git tree at the pinned source commit")
    tree = {item["path"]: item["sha"] for item in source_tree["tree"] if item["type"] == "blob"}
    records, summaries, sources, recipients = [], [], [], set()
    for epoch in EPOCHS:
        prefix = f"scripts/incentives/distributions/epoch_{epoch}/stipTradingIncentives"
        payload, source = cached_source(output_dir, prefix + "_distribution.json", tree)
        allocations, overrides = normalize_distribution(payload, epoch)
        transaction, transaction_source = cached_source(output_dir, prefix + "_transactionData.json", tree)
        total = sum(allocations.values())
        if amount(transaction.get("totalAmount")) != total:
            raise ValueError(f"Allocation sum differs from transactionData totalAmount: {epoch}")
        destinations = set(overrides.values()) if overrides is not None else set()
        for recipient, raw in sorted(allocations.items()):
            recipients.add(recipient)
            records.append({"epoch_start": epoch, "recipient": recipient, "token": TOKEN,
                            "amount_raw": str(raw), "amount_arb": units(raw),
                            "override_evidence": "unrecorded" if overrides is None else
                            "recorded_destination" if recipient in destinations else "not_in_recorded_overrides"})
        summaries.append({"epoch_start": epoch,
                          "epoch_end_exclusive": (date.fromisoformat(epoch) + timedelta(days=7)).isoformat(),
                          "recipient_count": len(allocations), "amount_raw": str(total), "amount_arb": units(total),
                          "overrides_recorded": str(overrides is not None).lower(),
                          "recorded_override_count": len(overrides) if overrides is not None else ""})
        sources.append({"epoch_start": epoch, "distribution": source, "transaction_data": transaction_source,
                        "applied_overrides": overrides})
        print(f"Validated reward epoch {epoch}: {len(allocations)} recipients, {units(total)} ARB", flush=True)
    total = sum(int(row["amount_raw"]) for row in summaries)
    outputs = [write_csv(output_dir / "recipient_rewards.csv", records),
               write_csv(output_dir / "epoch_summary.csv", summaries)]
    manifest = {
        "schema_version": 1, "label": "GMX STIP trading reward recipient allocations",
        "is_synthetic": False, "complete": True, "source_commit": COMMIT,
        "source_tree_sha256": hashlib.sha256(tree_path.read_bytes()).hexdigest(),
        "extracted_at": iso(datetime.now(timezone.utc)),
        "token": TOKEN, "token_symbol": "ARB", "decimals": 18, "chain_id": 42161, "distribution_type_id": 1003,
        "epoch_count": len(summaries), "epoch_start": EPOCHS[0],
        "last_epoch_start": EPOCHS[-1], "epoch_end_exclusive": summaries[-1]["epoch_end_exclusive"],
        "recipient_epoch_rows": len(records), "unique_recipients": len(recipients),
        "total_amount_raw": str(total), "total_amount_arb": units(total),
        "epochs_with_recorded_overrides": sum(row["overrides_recorded"] == "true" for row in summaries),
        "grain": "reward recipient address x source epoch", "payment_status": "not_verified_onchain",
        "trading_account_attribution": "not_reconstructable_from_recipient_amounts_alone",
        "forum_reconciliation": {
            "source_url": FORUM, "reported_total_arb": "4984768.84",
            "exact_minus_reported_total_arb": units(total - 498476884 * 10**16),
            "reported_last_epoch_arb": "224976.96", "reported_last_epoch_recipients": 2612,
            "exact_minus_reported_last_epoch_arb": units(int(summaries[-1]["amount_raw"]) - 22497696 * 10**16),
            "last_epoch_recipient_count_matches": summaries[-1]["recipient_count"] == 2612,
        },
        "files": outputs, "sources": sources,
        "notes": [
            "Amounts are exact allocations in the published official JSON, not verified paid transfers.",
            "Each epoch sum matches transactionData.totalAmount; calldata is not proof of on-chain execution.",
            "Receiver overrides can merge multiple trading accounts into one recipient; do not join recipients to trading accounts as proven identities.",
            "Absent appliedOverrides means unknown, not evidence that no overrides occurred. Even recorded mappings omit per-origin amounts after merging.",
            "Epoch labels and seven-day intervals describe allocation files; campaign eligibility boundaries require separate source verification.",
            "No USD valuation, acquisition cost, causal ROI or reward per retained trading account is inferred.",
            "Official final-report totals are rounded to two decimals; exact JSON amounts are retained.",
        ],
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest
