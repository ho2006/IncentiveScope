"""CLI: fetch real indexed events, or analyze a provenance-labelled snapshot."""

import argparse
import json
import sys
from pathlib import Path

from .analyze import analyze
from .fetch import fetch
from .report import render


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible DeFi incentive and repeat-trading research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquire = subparsers.add_parser("fetch", help="Fetch GMX V2 execution events (no wallet or API key)")
    acquire.add_argument("--config", type=Path, required=True)
    acquire.add_argument("--output", type=Path, required=True)
    acquire.add_argument("--start", help="Override extraction start, ISO timestamp including timezone")
    acquire.add_argument("--end", help="Override extraction end, exclusive")
    acquire.add_argument("--max-pages", type=int, help="Bounded probe; output remains incomplete until terminal page")
    compute = subparsers.add_parser("analyze", help="Validate inputs, run cohort SQL, render report")
    compute.add_argument("--config", type=Path, required=True)
    compute.add_argument("--input", type=Path, required=True)
    compute.add_argument("--manifest", type=Path, required=True)
    compute.add_argument("--output", type=Path, required=True)
    compute.add_argument("--exploratory", action="store_true", help="Explicitly label unverified real campaign boundaries")
    learning = subparsers.add_parser("ml", help="Run optional event-time retention modeling and report")
    learning.add_argument("--config", type=Path, required=True)
    learning.add_argument("--input", type=Path, required=True)
    learning.add_argument("--manifest", type=Path, required=True)
    learning.add_argument("--output", type=Path, required=True)
    learning.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if args.command == "fetch":
            if args.start:
                config["coverage_start"] = args.start
            if args.end:
                config["coverage_end"] = args.end
            manifest = fetch(config, args.output, args.max_pages)
            print(json.dumps({key: manifest[key] for key in ("row_count", "complete", "sha256")}, indent=2))
        elif args.command == "ml":
            from .ml import run
            run(config, args.input, args.manifest, args.output, args.device)
        else:
            results = analyze(config, args.input, args.manifest, args.output, args.exploratory)
            render(results, args.output)
            print(f"Wrote {args.output / 'index.html'} ({results['summary']['cohort_size']} cohort addresses)")
        return 0
    except (ValueError, KeyError, OSError) as error:
        print(f"IncentiveScope: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
