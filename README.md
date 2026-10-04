# IncentiveScope

**After the rebates: who keeps trading?**

A reproducible SQL/Python study of GMX V2 perpetual trading on Arbitrum after the first STIP trading-rebate program.

- **4.31% R30:** 954 of 22,145 campaign accounts reopened/increased during post days 24–30; cumulative30 was 13.53% and sustained two-day R30 was 2.14%.
- **Observed history matters:** R30 was 3.35% for first-observed campaign addresses and 8.62% for previously observed addresses. These are bounded address-history groups, not newly acquired people or a causal control group.
- **The result survives a volume sensitivity:** excluding the largest 1% by campaign opening size gives 4.12% R30. Mature-account post/pre activity intensity was 0.559 and net opening-fee intensity was 0.337.

![Real activity-definition sensitivity](reports/gmx-stip/figures/robustness.svg)

[Interactive research dashboard](https://ho2006.github.io/IncentiveScope/) · [English research report](reports/gmx-stip/research.md) · [Saved real-data notebook](notebooks/gmx-stip.ipynb) · [Metric JSON](reports/gmx-stip/results.json) · [Frozen input release](https://github.com/ho2006/IncentiveScope/releases/tag/v0.2.0)

**v0.3 extension — retention prediction:** [ML research page](https://ho2006.github.io/IncentiveScope/ml/) · [Method and reproduction](docs/ml.md) · [Saved PyTorch notebook](notebooks/retention-ml.ipynb). Seventeen pre-cutoff features, five model families, three MLP seeds and a strict final time holdout test whether earlier trading predicts later opening return. Neural-network superiority is not an acceptance condition.

The primary MLP's test AP is **0.3387**, versus **0.3412** for logistic regression and **0.3403** for gradient boosting. Its top 2,215 addresses capture **565 of 954 returns (59.22%)**, with **5.92× lift**. Validation selected the MLP, but this final test does not demonstrate a neural-network advantage. Mean MLP probability is 6.48% against 4.31% observed returns; the reliability chart exposes this bias without a calibration refit.

**Status: v0.2 real historical case.** The frozen indexed extract contains 907,107 executions across 36 contiguous partitions, from September 20, 2023 through May 29, 2024 (UTC, exclusive end). Local checks and an independent standard-library recount passed. Five March receipts validate selected account/type/size/fee fields; upstream completeness is not independently proven. Dune SQL is source-reviewed but **not executed**. Voluntary30 and trader-level reward unit costs are withheld.

## Inspect without credentials

Clone the repo and open `reports/gmx-stip/index.html`, or use the dashboard link above. The HTML, five SVGs, metric JSON, address cohort CSV and address-day CSV work offline. The history filter affects only the cohort table. No wallet, Dune login, API key or JavaScript dependency is required.

A separate [six-address synthetic example](reports/demo/research.md) tests edge cases; its numbers are not GMX findings.

## Set up and check

Use **PowerShell 7** and Python 3.11 or newer:

```powershell
git clone https://github.com/ho2006/IncentiveScope.git
Set-Location IncentiveScope
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe checks.py
```

The only core dependency is DuckDB, pinned in `pyproject.toml`. GitHub Actions runs on Windows with `pwsh` and Python 3.11 for the core workflow, plus a separate Python 3.14 CPU ML job. The original 24 checks cover fixed denominators, window edges, liquidations, old orders, incomplete input, duplicate events, exact fees/rewards, partition publication, missing ADL classification, Dune SQL fixtures/export validation and published-artifact reconciliation. Additional ML checks cover historical features, train-only preprocessing and saved inference. Optional model/report tests skip when ML dependencies are absent.

## Optional PyTorch experiment

After downloading the same frozen input, create an independent Python 3.14 environment:

```powershell
py -3.14 -m venv .venv-ml
& .\.venv-ml\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
& .\.venv-ml\Scripts\python.exe -m pip install -e '.[ml,notebook]'
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'incentivescope-matplotlib'
& .\.venv-ml\Scripts\python.exe checks.py
& .\.venv-ml\Scripts\python.exe -m incentivescope ml --config configs/gmx-stip-ml.json --input data/raw/gmx-stip/trades.csv --manifest data/raw/gmx-stip/manifest.json --output reports/gmx-stip/ml --device cpu
& .\.venv-ml\Scripts\python.exe scripts/execute_notebook.py notebooks/retention-ml.ipynb
```

The default notebook only reads committed results. Explicitly set `INCENTIVESCOPE_RERUN_ML=1` to retrain. The [method](docs/ml.md) defines each feature, label, split, baseline and interpretation limit. [The full CPU environment lock](requirements-ml-cpu.txt) supports the published run. Training uses 32,367 address-cutoff rows from 11,363 unique addresses; the final test contains 22,145 addresses and 954 positives. Train/validation occur during rebates, test after rebates: performance is predictive association under a period shift, not incentive causal impact.

## Exactly recompute the frozen real case

Download `trades.csv.gz` and `manifest.json` from the [v0.2.0 release](https://github.com/ho2006/IncentiveScope/releases/tag/v0.2.0) into `data/raw/gmx-stip`. `SHA256SUMS.txt` records the release assets. The decompressed CSV must have SHA-256 `76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3`; analysis verifies it automatically.

```powershell
New-Item -ItemType Directory -Force data/raw/gmx-stip | Out-Null
Invoke-WebRequest https://github.com/ho2006/IncentiveScope/releases/download/v0.2.0/trades.csv.gz -OutFile data/raw/gmx-stip/trades.csv.gz
Invoke-WebRequest https://github.com/ho2006/IncentiveScope/releases/download/v0.2.0/manifest.json -OutFile data/raw/gmx-stip/manifest.json
& .\.venv\Scripts\python.exe -c 'import gzip,shutil; from pathlib import Path; p=Path("data/raw/gmx-stip"); f=gzip.open(p/"trades.csv.gz","rb"); o=(p/"trades.csv").open("wb"); shutil.copyfileobj(f,o); o.close(); f.close()'
& .\.venv\Scripts\python.exe scripts/build_case.py
Start-Process .\reports\gmx-stip\index.html
```

`build_case.py` validates the input, runs the shared SQL, checks the public epoch ledger, and generates findings, tables, figures and the English report from the same `results.json`. The release provides normalized events and provenance; original query-response caches remain local. Source corrections can change a later refetch, so a fresh API snapshot is a different reproduction level.

## Refetch from public sources

The [official GMX GraphQL API](https://docs.gmx.io/docs/api/graphql/) and pinned official reward artifacts require no wallet or API key:

```powershell
& .\.venv\Scripts\python.exe scripts/fetch_history.py --config configs/gmx-stip.json --output data/raw/gmx-stip --workers 3
& .\.venv\Scripts\python.exe scripts/fetch_rewards.py --output data/raw/rewards
& .\.venv\Scripts\python.exe scripts/build_case.py
& .\.venv\Scripts\python.exe scripts/audit_history.py
```

History uses ID keyset pagination, finite retries, terminal empty pages and immutable request caches. Interrupted partitions resume from cache; a capped or incomplete extraction fails analysis. Use a new directory if requesting a fresh snapshot; compare its checksum before replacing the frozen case. The independent audit also inspects the anomalous September partition's raw caches, so it requires a full fetch rather than only the release CSV.

The reward importer validates all 19 allocation epochs and companion batch totals at an immutable Git revision. [Public epoch evidence](data/evidence/reward-allocations/epoch_summary.csv) totals exactly **4,984,768.849960484548991571 ARB**, across 16,528 recipient addresses. These are published allocations, not verified payment transfers. Receiver overrides prevent a complete original-trader join; no program-wide spend is divided by the retained opening cohort.

[Dune SQL companions](docs/dune.md) use pinned official Spellbook definitions for event-grain and retention cross-checks. The daily audit covers 252 explicit UTC dates, checks both matching directions and exposes duplicates and join multiplication. `scripts/reconcile_dune.py` compares complete exports and execution provenance with the frozen case. The signed-in browser attempt currently has disabled Run/Create controls; [the attempt record](data/evidence/dune/execution-status.json) contains no execution ID. No Dune result or source agreement is claimed. The dashboard displays this status and the exact metric windows.

## Definitions and interpretation

The earning interval is `[2023-11-15T00:00:01Z, 2024-03-27T00:00:00Z)`. The historical indexer has a strict launch guard; the last earning epoch ends March 27, distinct from the March 29 administrative deadline. See [the boundary evidence](docs/boundary-evidence.md).

| Measure | Window and definition |
| --- | --- |
| Fixed cohort | Successful positive-size opening/increase during the earning window; all nonreturners retained |
| R30 | At least one opening/increase in `[2024-04-19, 2024-04-26)` UTC |
| Cumulative30 | At least one in `[2024-03-27, 2024-04-26)` UTC |
| Sustained30 | At least two distinct opening/increase UTC dates in the R30 window |
| Strict R30 | R30 with an order created at/after earning end; withheld if relevant creation times are missing |
| R60 | At least one in `[2024-05-19, 2024-05-26)` UTC |
| Open-or-decrease30 | Broader candidate measure; may include forced ADL decreases |
| Voluntary30 | Withheld for this source because the secondary ADL marker is unavailable |

Protocol `account` owns the activity; keeper `tx.from` does not. Zero-size collateral actions and type-7 liquidations do not count as opening participation. ADL may be a type-4 market decrease. Net position fee USD is `(positionFeeAmount - traderDiscountAmount) * collateralTokenPriceMin / 10^30`, after trader discount and before external rebates. It excludes decrease fees in the opening analysis, funding, borrowing, UI fees and gas, and is not protocol revenue.

Mature-account intensity uses the same 17,390 addresses and 30 UTC days before/after the end, including inactive days. Three sensitivity cuts cover entry/history, pre-end volume concentration and activity definitions. First-observed history is left-truncated and can include forced decreases. The early post window overlaps Binance Wallet tasks; an earlier Odyssey campaign affects prehistory. These are historical observational findings, not causal CAC, ROI or verified human-user retention.

[Campaign context](docs/campaign.md) · [Five receipt checks](docs/event-validation.md) · [Daily quality and independent recount](docs/data-quality.md) · [Reward attribution](docs/reward-data.md) · [Original plan and completion record](docs/PLAN.md) · [Three-minute interview demo](docs/interview.md)

## Notebook companion

[The real notebook](notebooks/gmx-stip.ipynb) displays the committed snapshot and all five figures by default, with saved outputs. Opt into a full raw recomputation with the environment flag after downloading the input. Both modes are explicitly labelled; notebook packages are optional:

```powershell
& .\.venv\Scripts\python.exe -m pip install -e '.[notebook]'
& .\.venv\Scripts\python.exe scripts/execute_notebook.py notebooks/gmx-stip.ipynb
$env:INCENTIVESCOPE_RERUN_RAW = '1'
& .\.venv\Scripts\python.exe scripts/execute_notebook.py notebooks/gmx-stip.ipynb
Remove-Item Env:INCENTIVESCOPE_RERUN_RAW
```

## License

Project code and synthetic examples are MIT licensed. GMX indexed data, official distribution artifacts and referenced materials retain their original terms and provenance; no ownership over third-party data is claimed. The release redistributes a normalized historical extract with its source manifest.
