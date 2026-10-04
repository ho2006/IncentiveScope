# Retention prediction: a pre-cutoff, time-held-out experiment

**Question:** can observed trading before a cutoff identify addresses more likely to reopen in `[T + 23 days, T + 30 days)`? This extension uses the same frozen GMX V2 / Arbitrum extract as the descriptive case. It does not estimate the causal effect of rebates.

[Public ML research page](https://ho2006.github.io/IncentiveScope/ml/) · [Saved notebook](../notebooks/retention-ml.ipynb) · [Experiment configuration](../configs/gmx-stip-ml.json) · [Machine-readable results](../reports/gmx-stip/ml/results.json)

## Samples and time discipline

One row is one protocol address at one UTC prediction cutoff. Eligibility requires a successful positive-size opening/increase during `[campaign start, T)`. An address need not trade in the latest 30 days. Every feature uses executions strictly before `T`; labels use the half-open future R30 window. The fixed start is `2023-11-15T00:00:01Z` and the test cutoff is the earning end `2024-03-27T00:00:00Z`.

| Role | Cutoff UTC | Rows | R30 returns | Label window UTC |
| --- | --- | ---: | ---: | --- |
| Train | 2023-11-22 | 2,197 | 560 | [2023-12-15, 2023-12-22) |
| Train | 2023-12-06 | 4,457 | 907 | [2023-12-29, 2024-01-05) |
| Train | 2023-12-20 | 6,255 | 997 | [2024-01-12, 2024-01-19) |
| Train | 2024-01-03 | 8,095 | 830 | [2024-01-26, 2024-02-02) |
| Train | 2024-01-17 | 11,363 | 1,221 | [2024-02-09, 2024-02-16) |
| Validation | 2024-02-21 | 16,634 | 1,598 | [2024-03-15, 2024-03-22) |
| Final test | 2024-03-27 | 22,145 | 954 | [2024-04-19, 2024-04-26) |

There are 32,367 training observations, 4,515 positive observations and 11,363 distinct parameter-training addresses. Earlier addresses occur at multiple landmarks, with equal weight per row. These are not 32,367 independent users. The last training label is complete before validation prediction; validation labels are complete before final prediction. Earlier train labels may extend past another training landmark: all are mature when the single training fit occurs before validation.

Final evaluation separately reports 11,363 addresses seen in parameter training and 10,782 absent from parameter training. An address observed during validation only remains absent from parameter training. At the final cutoff, 13,561 addresses (61.24%) had no opening in the last 30 days; 148 of them subsequently returned. Removing them would change the research population.

## Seventeen fixed features

The exact order is published in `preprocessing.json`, each PyTorch checkpoint and `results.json`.

| Order | Columns | Definition |
| --- | --- | --- |
| 1–4 | `opening_count_7d`, `active_days_7d`, `opening_size_usd_7d`, `opening_fee_usd_7d` | Executions, distinct UTC dates, summed USD size, summed net position fees in `[T-7d,T)` |
| 5–8 | Same prefixes ending `_30d` | Same definitions in `[T-30d,T)` |
| 9–12 | Same prefixes ending `_60d` | Same definitions in `[T-60d,T)` |
| 13 | `days_since_first_observed_opening` | Fractional days since earliest opening observed in the extract before `T` |
| 14 | `days_since_last_opening` | Fractional days since latest observed opening before `T` |
| 15 | `pre_campaign_opening` | Observed successful positive-size opening before campaign start |
| 16 | `market_count_30d` | Distinct markets with openings in `[T-30d,T)` |
| 17 | `top_market_share_30d` | Largest market's share of summed opening USD size in `[T-30d,T)` |

No-activity windows contain zero counts, size and fees; market concentration is zero when no openings exist. Missing fees on eligible pre-cutoff opening history terminate construction. Net position fees are after trader discount and before external rebates; they exclude funding, borrowing, UI fees and gas. Aggregated opening size is executed notional, not capital deposited or TVL.

All 15 nonnegative count, amount and age fields use `log1p`. A training-only `StandardScaler` fits the 16 continuous fields, including concentration. The binary pre-campaign flag is unchanged. Address, hash, date and label never enter the feature matrix. Existing full-campaign volume and future return fields are excluded. History begins September 20, so observed age is not lifetime trading age. This opening-only history flag differs from the descriptive case's broader observed activity flag.

## Fixed model comparison

| Model | Procedure |
| --- | --- |
| Constant | Training positive rate for every validation/test address |
| Recent activity | Negative days since latest opening; ranking metrics only |
| Logistic regression | L2, `C ∈ {0.1,1,10}`, maximum 1,000 iterations; validation AP selects C |
| Histogram gradient boosting | Seven leaves, learning rate 0.05; validation AP selects 100/200 iterations; internal early stopping disabled |
| PyTorch MLP | 17 → 32 → 16 → 1, ReLU, dropout 0.1; unweighted BCEWithLogitsLoss, AdamW learning rate 0.001, weight decay 0.001, batch size 256 |

MLP training lasts at most 100 epochs and stops after 10 epochs without a strict validation AP improvement. Evaluation reloads the saved best weights. Seeds 17, 42 and 73 are all reported; 42 is the predeclared primary run. Validation is never refitted into training. Validation AP chooses between the three learned model families. Test performance does not select a seed, configuration or checkpoint.

The main metric is scikit-learn **Average Precision**, using all predictions. It is not a trapezoidal PR-AUC. Secondary metrics are ROC-AUC, top 10% precision/recall/lift, Brier and log loss. The top quota is `ceil(N × 0.1)` with ascending account as the tie-breaker. Constant-score top-decile counts therefore reflect this fixed tie convention, not discriminatory power. Lift uses the evaluated population's observed positive rate; the constant prediction uses training prevalence. PR visual arrays alone are thinned to at most 500 points.

Probability models have reliability plots with up to ten quantile bins and explicit counts; duplicate boundaries collapse. Recent-activity scores do not receive probability metrics. There is no extra probability-calibration fit. Validation permutation importance uses the primary MLP, ten shuffles per feature and AP loss. Correlated windows can share predictive information; importance is model dependence, not a causal effect. Error bars show shuffle variation, not confidence intervals.

## Reproduction and artifacts

Use PowerShell 7 and Python 3.14. The published CPU run uses Python 3.14.4, PyTorch 2.14.1+cpu, NumPy 2.5.3, scikit-learn 1.9.1 and Matplotlib 3.11.2. The fully pinned installed environment is [requirements-ml-cpu.txt](../requirements-ml-cpu.txt). Download and verify the [v0.2.0 frozen input](https://github.com/ho2006/IncentiveScope/releases/tag/v0.2.0) using the README first.

```powershell
py -3.14 -m venv .venv-ml
& .\.venv-ml\Scripts\python.exe -m pip install -r requirements-ml-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
& .\.venv-ml\Scripts\python.exe -m pip install -e '.[ml,notebook]'
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'incentivescope-matplotlib'
& .\.venv-ml\Scripts\python.exe checks.py
& .\.venv-ml\Scripts\python.exe -m incentivescope ml --config configs/gmx-stip-ml.json --input data/raw/gmx-stip/trades.csv --manifest data/raw/gmx-stip/manifest.json --output reports/gmx-stip/ml --device cpu
& .\.venv-ml\Scripts\python.exe scripts/execute_notebook.py notebooks/retention-ml.ipynb
```

The notebook reads saved results by default. Set `$env:INCENTIVESCOPE_RERUN_ML = '1'` to explicitly retrain through the same CLI, then remove that environment variable. Training is never triggered simply by opening the saved notebook. To use a CUDA environment, install a compatible official CUDA wheel into a separate `.venv-ml-cuda` and explicitly pass `--device cuda`. The installed CPU wheel cannot run CUDA; an unavailable device causes an error. The local RTX 5060 Ti is not used for the published CPU benchmark.

Artifacts include raw feature rows, final test predictions for seven runs, split counts/labels, all model metrics and subgroup metrics, preprocessing parameters, candidate validation scores, three training histories and tensor-only PyTorch checkpoints, a feature dictionary, five SVG/PNG figures and the HTML/Markdown report. `results.json` records input/config/source hashes, source commit, device, dependency versions and seeds. `artifact-manifest.json` lists checksums and sizes for completed outputs. Checkpoints load with `weights_only=True` and replay saved predictions.

Single-thread DuckDB feature aggregation and CPU model libraries, deterministic PyTorch algorithms, seeded shuffling and frozen inputs constrain reproduction. Cross-version, cross-platform and CPU/GPU bitwise equality is not promised. Saved predictions support independent metric recount without training. Tests cover temporal boundaries, future-event invariance, missing fees, zero activity, label maturity, forbidden features, training-only scaling, test-isolated fitting and checkpoint replay. A separate standard-library publication audit checks output hashes and independently recounts AP, top-decile and probability metrics from all seven prediction runs. GitHub CI runs the core environment separately from a Python 3.14 CPU ML environment; both gate Pages deployment.

## Interpretation limits and references

Train/validation labels occur during the rebate program while the final test occurs after it. Positive rates and activity distributions change, so uncalibrated probabilities can be systematically too high. This is one final time holdout from one campaign. It does not demonstrate generalisation across campaigns, human-level retention, reward targeting effectiveness, or an incentive causal effect. Historical features are rebuilt by event time from a later frozen indexer snapshot; historical index availability and later corrections have not been audited as a point-in-time data service. Dune SQL execution is not claimed.

- [Tabular-model benchmark motivating a tree baseline (NeurIPS 2022)](https://proceedings.neurips.cc/paper_files/paper/2022/hash/0378c7692da36807bdec87ab043cdadc-Abstract-Datasets_and_Benchmarks.html)
- [PyTorch BCEWithLogitsLoss](https://docs.pytorch.org/docs/2.14/generated/torch.nn.BCEWithLogitsLoss.html)
- [scikit-learn Average Precision definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [scikit-learn calibration guide](https://scikit-learn.org/stable/modules/calibration.html)
- [PyTorch 2.14.1 release](https://github.com/pytorch/pytorch/releases/tag/v2.14.1)
- [PyTorch reproducibility guidance](https://docs.pytorch.org/docs/2.14/notes/randomness.html)
