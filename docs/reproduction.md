# Reproducing IncentiveScope

This runbook separates inspecting saved outputs, recomputing a frozen input, and fetching a new upstream snapshot. Only the frozen-input task can be compared with the published results as the same dataset. No wallet, Dune account or API key is needed.

## Inspect the portfolio

Read the [English web report](https://ho2006.github.io/IncentiveScope/portfolio/) or its [PDF](https://ho2006.github.io/IncentiveScope/portfolio/research.pdf), then explore [participation](https://ho2006.github.io/IncentiveScope/) and [prediction](https://ho2006.github.io/IncentiveScope/ml/). Opening them does not refetch or retrain.

Saved notebooks read committed results by default, with explicit raw/ML rerun entry points. Source SQL, metric JSON, predictions, preprocessing, three PyTorch checkpoints and artifact hashes are committed. Raw events are in the separate [v0.2.0 input release](https://github.com/ho2006/IncentiveScope/releases/tag/v0.2.0).

## Complete CPU rehearsal

Prerequisites: Windows, PowerShell **7.4+**, native Git and the Python **3.14** launcher. The reference uses Python **3.14.4** and PyTorch **2.14.1+cpu**. Exact ML comparisons include Python/library versions; another version is a new environment, not an exact replay. Installation uses PyPI and the official PyTorch CPU index. Allow roughly 2 GB of disk space for environment, input and outputs.

```powershell
git clone https://github.com/ho2006/IncentiveScope.git
Set-Location IncentiveScope
& ./scripts/rehearse.ps1
```

The script creates `.venv-rehearsal`, installs the [CPU lock](../requirements-ml-cpu.txt), builds and installs a wheel with no editable-source dependency, and verifies imports come from `site-packages`. It downloads the release input, checks the decompressed CSV hash, runs checks, regenerates the core case into an isolated output directory and retrains all CPU ML runs. Both real notebooks then execute in saved-result inspection mode, distinct from the preceding raw recomputation and training.

No copying of the author's raw data, environments or response caches is required. `pip` may reuse downloaded wheels. This is a fresh-clone/new-environment exercise, not a cold-cache benchmark.

Outputs remain ignored under `reports/live/reproduction`:

| File or directory | Purpose |
| --- | --- |
| `session.json` | Executed stages, elapsed seconds, PowerShell version, tested commit and failure status |
| `comparison.json` | Input hash, versions, exact ML comparisons, core rounding drift and pass/fail |
| `core/`, `ml/` | Regenerated analysis and retrained models, data, curves and reports |
| `gmx-stip.ipynb`, `retention-ml.ipynb` | Executed notebook copies; committed files stay intact |
| `wheels/` | Built distribution installed for the exercise |

The reference is never overwritten. A failed stage stops the script and leaves a failed session receipt. Resolve the cause before retrying; do not edit expectations to make the comparison pass.

## What the comparison verifies

The [verifier](../scripts/verify_reproduction.py) compares all core analytical JSON and both address CSV exports. It also compares all ML analytical JSON, split counts, configuration/source hashes, environment versions, feature CSV, prediction CSV, preprocessing, training curves and three checkpoint hashes. Training data, scores and weights must match exactly.

The default is exact. The rehearsal explicitly permits `1e-12` relative/absolute rounding tolerance for core JSON floats and `campaign_volume_usd` / `position_fee_usd` CSV fields only. Core SQL may sum floating USD quantities in a different parallel reduction order. Accepted differences, counts and examples are recorded. Integer counts, labels, dates and all ML outputs still require exact equality; this is not tolerance for changed data or model selection.

ML execution time, code commit, tracked-worktree state and platform are retained but excluded from matching the older run. The new tracked worktree must be clean. Rendered prose/figures are not byte comparisons; exported data and weights are checked directly. The [ML artifact manifest](../reports/gmx-stip/ml/artifact-manifest.json) separately protects 20 saved files.

Replay validates the published normalized extract, not upstream completeness, historical live-index availability, Dune agreement or incentive causality. Cross-version and CPU/GPU bitwise equality is not promised.

## Manual frozen-input rebuild

For core analysis without ML:

```powershell
py -3.14 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -e .
New-Item -ItemType Directory -Force data/raw/gmx-stip | Out-Null
Invoke-WebRequest https://github.com/ho2006/IncentiveScope/releases/download/v0.2.0/trades.csv.gz -OutFile data/raw/gmx-stip/trades.csv.gz
Invoke-WebRequest https://github.com/ho2006/IncentiveScope/releases/download/v0.2.0/manifest.json -OutFile data/raw/gmx-stip/manifest.json
& ./.venv/Scripts/python.exe -c 'import gzip,shutil; from pathlib import Path; p=Path("data/raw/gmx-stip"); f=gzip.open(p/"trades.csv.gz","rb"); o=(p/"trades.csv").open("wb"); shutil.copyfileobj(f,o); o.close(); f.close()'
& ./.venv/Scripts/python.exe scripts/build_case.py --output reports/live/core-rebuild
```

Expected decompressed CSV SHA-256: `76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3`. The gzip asset has a different hash. Expected cohort: **22,145 addresses**, R30: **954 positives**.

For ML, install the lock in a separate environment:

```powershell
py -3.14 -m venv .venv-ml
& ./.venv-ml/Scripts/python.exe -m pip install -r requirements-ml-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
& ./.venv-ml/Scripts/python.exe -m pip install -e '.[ml,notebook]'
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'incentivescope-matplotlib'
& ./.venv-ml/Scripts/python.exe -m incentivescope ml --config configs/gmx-stip-ml.json --input data/raw/gmx-stip/trades.csv --manifest data/raw/gmx-stip/manifest.json --output reports/live/ml-rebuild --device cpu
```

Optional notebook dependencies are `.[notebook]`. Execute saved results with `scripts/execute_notebook.py notebooks/gmx-stip.ipynb` or `notebooks/retention-ml.ipynb`. Set `INCENTIVESCOPE_RERUN_RAW=1` or `INCENTIVESCOPE_RERUN_ML=1` to recompute; these modes need raw input and the ML mode needs ML dependencies. Remove the flag afterward. The rehearsal uses notebook copies to preserve the checkout.

## Refetching is a different experiment

The public indexed API can be re-extracted without a key:

```powershell
& ./.venv/Scripts/python.exe scripts/fetch_history.py --config configs/gmx-stip.json --output data/raw/new-snapshot --workers 3
& ./.venv/Scripts/python.exe scripts/fetch_rewards.py --output data/raw/rewards
```

Use a new directory and retain its checksum. Service changes or historical corrections can change a later snapshot; do not replace the frozen case silently. Extraction uses keyset pagination, finite retries, immutable caches and empty terminal pages; incomplete input fails analysis. `scripts/audit_history.py` also inspects caches, requiring a full extraction rather than only release assets. Reward allocations remain separate from verified payments.

## Rebuild the English presentation

`docs/portfolio-report.md` is the narrative source. `scripts/build_portfolio.py` renders its small Markdown subset to HTML and emits source/output hashes. Analysis does not require PDF authoring tools.

```powershell
& ./.venv/Scripts/python.exe scripts/build_portfolio.py
# Optional Windows export, separate from the ML environment:
py -3.14 -m venv .venv-pdf
& ./.venv-pdf/Scripts/python.exe -m pip install reportlab==4.4.9 svglib==1.5.1
& ./.venv-pdf/Scripts/python.exe scripts/build_portfolio.py --pdf
```

PDF export embeds Windows Segoe UI fonts and uses existing SVG/PNG evidence. After changing the report, rebuild both formats and inspect the PDF pages. The authoring environment is separate from the CPU experiment lock.

## Recorded rehearsal

On **October 4, 2026**, the independent-clone rehearsal passed at commit [`a7c87de`](https://github.com/ho2006/IncentiveScope/commit/a7c87dec0c18d36ef19e5b001a3c0bcddd8753cc). The [executed session](../data/evidence/reproduction/portfolio-session.json) and [analytical comparison](../data/evidence/reproduction/portfolio-cpu.json) are the unedited receipts. The final model run recorded a clean tracked worktree.

The exercise created its own Python environment, installed a built `0.3.0` wheel, downloaded the public input release and passed **39 checks**. The successful final attempt reused that environment after earlier attempts exposed Windows checkout line-ending problems. Frozen evidence is now protected by `.gitattributes` and hash checks; no expectation or recorded model score was changed to pass. This is not a cold-cache timing result.

| Rebuilt output | Actual comparison |
| --- | --- |
| Core analytical JSON | Exact; cohort 22,145 and R30 numerator 954 |
| Core daily export | All 324,448 rows exact |
| Core cohort export | 22,145 rows; 548 floating USD-field differences within `1e-12`; no other differences |
| ML analytical JSON / environment | Exact matching fields; Python 3.14.4, PyTorch 2.14.1+cpu |
| Features / predictions | 71,146 / 155,015 rows; exact fields and compressed file hashes |
| Preprocessing / training curve | Exact; 123 epoch rows |
| PyTorch checkpoints | All three seeds' SHA-256 hashes exact |
| Notebooks | Both copied notebooks executed successfully in saved-result inspection mode |

The final session's CPU training took 51.375 seconds on this machine; its seven stages ran from 10:09:29 to 10:11:07 UTC. These are recorded local timings with reused downloads/dependencies, not a portable performance claim. The published model reference was produced at `6a75f1f`; its four ML source-file hashes match the tested commit. See [the completion record](completion.md) for the delivered scope and remaining evidence limits.
