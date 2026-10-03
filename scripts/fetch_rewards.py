"""Download and verify all 19 official STIP trading allocation epochs."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from incentivescope.rewards import fetch_rewards

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "data/raw/rewards")
args = parser.parse_args()
manifest = fetch_rewards(args.output)
print(f"Complete: {manifest['epoch_count']} epochs, {manifest['unique_recipients']} recipients, "
      f"{manifest['total_amount_arb']} ARB allocated. Payment and trading-account identity remain unverified.")
