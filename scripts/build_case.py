"""Recompute the GMX case, attach audited program allocations and render findings."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from incentivescope.analyze import analyze
from incentivescope.common import atomic_text, write_json
from incentivescope.report import percent, render

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/gmx-stip",
                        help="Report directory; defaults to the published GMX case")
    output = parser.parse_args().output
    result = analyze(json.loads((ROOT / "configs/gmx-stip.json").read_text(encoding="utf-8")),
                     ROOT / "data/raw/gmx-stip/trades.csv", ROOT / "data/raw/gmx-stip/manifest.json", output)
    ledger = ROOT / "data/evidence/reward-allocations"
    rewards = json.loads((ledger / "manifest.json").read_text(encoding="utf-8"))
    epoch_file = next(row for row in rewards["files"] if row["file"] == "epoch_summary.csv")
    if rewards["complete"] is not True or hashlib.sha256((ledger / epoch_file["file"]).read_bytes()).hexdigest() != epoch_file["sha256"]:
        raise ValueError("Incomplete or modified reward epoch evidence")
    with (ledger / "epoch_summary.csv").open(newline="") as stream:
        epochs = list(csv.DictReader(stream))
    if len(epochs) != 19 or sum(int(row["amount_raw"]) for row in epochs) != int(rewards["total_amount_raw"]):
        raise ValueError("Reward epoch totals do not reconcile")
    result["reward_allocations"] = {key: rewards[key] for key in
                                    ("epoch_count", "unique_recipients", "recipient_epoch_rows", "total_amount_arb",
                                     "source_commit", "payment_status", "trading_account_attribution")}
    groups = {}
    for row in result["cohorts"]:
        group = groups.setdefault(row["kind"], {"n": 0, "N": 0})
        group["n"] += row["r30_n"]
        group["N"] += row["size"]
    summary, activity = result["summary"], result["activity"]
    observed, existing = groups["first_observed_in_campaign"], groups["observed_existing"]
    removed = result["segments"][1]
    result["findings"] = [
        f"R30 is {percent(summary['r30']['rate'])} ({summary['r30']['n']:,}/{summary['cohort_size']:,}), versus {percent(summary['cumulative30']['rate'])} cumulative30; these answer different questions. Sustained two-day R30 is {percent(summary['sustained30']['rate'])}.",
        f"First-observed campaign addresses return at {percent(observed['n']/observed['N'])} ({observed['n']:,}/{observed['N']:,}), versus {percent(existing['n']/existing['N'])} ({existing['n']:,}/{existing['N']:,}) for previously observed addresses. These are address-history groups, not acquisition or causal treatment groups.",
        f"Removing the top 1% by campaign opening size gives {percent(removed['r30_rate'])} R30 ({removed['r30_n']:,}/{removed['size']:,}); the low aggregate result is not eliminated by this volume sensitivity.",
        f"For {activity['eligibleN']:,} mature addresses, post/pre active-address-day intensity is {activity['activity_ratio']:.3f} and net opening position-fee intensity is {activity['fee_ratio']:.3f}. These are equal-window descriptive comparisons, not the causal effect of ending rewards.",
        f"Strict new-order R30 equals opening R30; R60 is {percent(summary['r60']['rate'])} ({summary['r60']['n']:,}/{summary['cohort_size']:,}). Voluntary30 remains unavailable because the indexed source cannot separate ADL decreases."
    ]
    repo = "https://github.com/ho2006/IncentiveScope/blob/main/"
    result["evidence_links"] = [{"label": label, "url": repo + path} for label, path in (
        ("Verified earning boundaries", "docs/boundary-evidence.md"),
        ("Five execution and fee receipt checks", "docs/event-validation.md"),
        ("Historical quality and independent recount", "docs/data-quality.md"),
        ("Official reward allocations and attribution limits", "docs/reward-data.md"),
        ("Dune companion: source-reviewed, not executed", "docs/dune.md"))]
    status_path = ROOT / "data/evidence/dune/execution-status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        result["cross_source"] = {"status": status["status"], "message": status["message"],
                                  "attempted_at": status["attempted_at"], "query_id": status["query_id"],
                                  "execution_id": status["execution_id"]}
    write_json(output / "results.json", result)
    render(result, output)
    note = (output / "research.md").read_text(encoding="utf-8")
    discussion = (ROOT / "docs/research-discussion.md").read_text(encoding="utf-8")
    atomic_text(output / "research.md", note + "\n" + discussion)
    print(f"Built real case: {summary['cohort_size']:,} accounts; R30 {summary['r30']['n']:,}; input {result['dataset']['sha256']}")


if __name__ == "__main__":
    main()
