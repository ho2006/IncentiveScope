# IncentiveScope interview demonstration

This walkthrough presents the descriptive GMX V2 incentive study and the PyTorch participation-prediction experiment. The evidence supports address-level observations and predictions from one historical campaign.

[Application copy](application.md) · [English portfolio report](portfolio-report.md) · [Reproduction runbook](reproduction.md)

## Prepare the demonstration

Open these tabs before the interview:

1. [English research report](https://ho2006.github.io/IncentiveScope/portfolio/).
2. [Participation dashboard](https://ho2006.github.io/IncentiveScope/).
3. [Prediction dashboard](https://ho2006.github.io/IncentiveScope/ml/).
4. [Repository](https://github.com/ho2006/IncentiveScope) and [saved ML notebook](https://github.com/ho2006/IncentiveScope/blob/main/notebooks/retention-ml.ipynb).

Use the published snapshots for the timed presentation. Notebooks inspect saved results by default; the runbook describes explicit retraining. If the network fails, use committed HTML reports and notebook outputs locally. Keep detailed evidence pages available for questions.

## Three-minute walkthrough

### 0:00–0:25 — Question and scope

**Show:** the English report's opening findings.

> I built IncentiveScope to investigate whether GMX V2 trading accounts continue opening positions after Arbitrum STIP rebates stop being earned. I then asked whether behavior observed before that cutoff can rank future participation. The study uses 907,107 indexed executions and a fixed cohort of 22,145 accounts. Addresses are the analytical unit; they are not a count of people.

### 0:25–1:05 — Define the outcome before interpreting it

**Show:** the participation dashboard's return definitions and history comparison.

> The earning end is March 27, 2024, verified against archived eligibility code and allocation epochs. R30 means an opening during days 24–30 afterward: 954 accounts, or 4.31%. Any opening in the first 30 days gives 13.53%, while activity on two distinct dates in the R30 window gives 2.14%. These measure occasional return and sustained participation differently. Previously observed accounts return more often, but that comparison is descriptive and the lookback is incomplete.

### 1:05–1:55 — Add prediction with a strict time split

**Show:** the prediction dashboard's model comparison, then reliability plot.

> I built 17 features from executions strictly before each prediction cutoff. Training uses five earlier cutoffs; validation selects configurations and MLP checkpoints before the final test. The PyTorch network is 17–32–16–1, with seed 42 fixed as the primary run and all three seeds reported. Its test Average Precision is 0.3387, versus 0.3412 for logistic regression and 0.3403 for gradient boosting. It does not establish a neural-network advantage. The top 2,215 MLP-ranked accounts capture 565 of 954 returns. Mean predicted probability is 6.48%, above the observed 4.31%, so useful ranking does not mean accurate probabilities after the regime changes.

### 1:55–2:30 — Show research judgment

**Show:** the report's validation and limitations.

> Independent Python sets reproduce the SQL cohort counts, and five selected chain receipts check account attribution and fee semantics. Those receipt checks do not prove upstream completeness. A semantic review found that forced ADL decreases cannot be separated in this indexer, so I withheld a voluntary-return metric. Reward receiver substitutions also prevent a defensible cost-per-retained-trader calculation. Dune companion SQL is source-reviewed but has not been executed.

### 2:30–3:00 — Deliverable and implication

**Show:** repository entry points and reproduction runbook.

> The project publishes code, frozen input hashes, notebooks, predictions, weights and both research dashboards. A reviewer can inspect the evidence without credentials or rerun the CPU experiment. The practical recommendation is to monitor cumulative reach, end-of-month opening activity and repeated-day participation together. Prediction adds a research tool for ranking likely returners; it does not show that rewards caused retention or that targeting these accounts would improve it.

## Five-minute walkthrough

Use the three-minute narrative, with two additional minutes before the closing paragraph.

### Add one minute — Why the backtest is credible

**Show:** the time-split table and [ML methodology](ml.md).

> The last training labels finish on February 16, before the February 21 validation cutoff. Validation labels finish on March 22, before the March 27 test cutoff. Feature windows end strictly before prediction time. The scaler fits training rows only, validation never joins parameter training, and test scores never choose the seed or checkpoint. I keep all eligible inactive accounts: 61.24% have no opening in the last 30 days, but 148 still return. Dropping them would change the population. The final test separately reports 11,363 accounts seen in parameter training and 10,782 absent from it.

Explain that the later frozen indexer extract enables an event-time backtest. Historical real-time index availability and later corrections were not audited.

### Add one minute — Reproduction and a code seam

**Show:** [reproduction runbook](reproduction.md), its recorded rehearsal receipt, then [feature construction](../src/incentivescope/ml_data.py) or [model training](../src/incentivescope/ml_models.py).

> The frozen normalized CSV is identified by SHA-256. The CPU dependency lock, feature order, preprocessing parameters, source hashes and experiment seeds travel with the result. The publication audit independently recalculates metrics from exported predictions and verifies artifact hashes. The training code restores the best validation checkpoint and checks saved-weight replay. The core environment remains usable without PyTorch; a separate CPU ML CI job gates publication alongside the core checks.

> I also rehearsed the complete frozen-input pipeline in an independent clone with an installed wheel. All 39 checks passed; the 71,146 feature rows, 155,015 prediction rows and all three model checkpoint hashes matched exactly. The core cohort remained 22,145 accounts with 954 returns. The core address export had 548 floating USD-field differences within a declared `1e-12` tolerance, which the receipt records rather than hiding.

Open the [session](../data/evidence/reproduction/portfolio-session.json) and [comparison](../data/evidence/reproduction/portfolio-cpu.json) receipts. Notebook execution inspected saved results; the CLI separately rebuilt raw-data metrics and retrained the models. Full training can be demonstrated separately from the timed presentation.

## Technical follow-up routes

Let the reviewer choose a route for a longer discussion:

| Route | Open | Explain |
| --- | --- | --- |
| SQL and data engineering | [Metric SQL](../src/incentivescope/metrics.sql), [data-quality evidence](data-quality.md) | Fixed cohort, half-open UTC windows, successful positive-size increases, pagination and independent recount |
| Protocol semantics | [Boundary evidence](boundary-evidence.md), [receipt checks](event-validation.md) | Earning versus payment date, trader account versus keeper sender, ADL limitation and net position fees |
| PyTorch and evaluation | [ML methods](ml.md), [model code](../src/incentivescope/ml_models.py), [saved notebook](../notebooks/retention-ml.ipynb) | Unweighted BCE, early stopping, baselines, AP and reliability, all seeds |
| Research explanation | [English report](portfolio-report.md), [reward evidence](reward-data.md) | Supported implication, historical confounding, receiver attribution and withheld cost claims |
| Reproduction | [Runbook](reproduction.md), [ML artifact manifest](../reports/gmx-stip/ml/artifact-manifest.json) | Frozen source, pinned environment, checksums, prediction recount and checkpoint replay |

## Questions and defensible answers

| Question | Answer |
| --- | --- |
| Why not use `tx.from` as the trader? | Keeper senders execute orders for position accounts. The indexed position account is the unit; selected receipt checks demonstrate the distinction. |
| Why is R30 below cumulative30? | R30 covers `[E+23 days,E+30 days)`; cumulative30 covers `[E,E+30 days)`. They answer different questions. R60 is another seven-day calendar window and may exceed R30. |
| Are first-observed addresses new users? | No. History starts September 20, 2023. These labels describe observed address history, not first-ever protocol use or people acquired by the campaign. |
| Why retain accounts with no recent trades? | They remain eligible under the campaign cohort definition. The 13,561 accounts without last-30-day openings include 148 future returns. Excluding them would select a more active population. |
| What prevents leakage? | Eligibility and features use events before the cutoff; labels use the future window. Training-only transforms, mature labels, validation-only selection and fixed primary seed separate fitting from final evaluation. Tests inject future events and altered test data to check these boundaries. |
| Do repeated addresses invalidate the experiment? | Training has 32,367 address-cutoff rows but 11,363 unique addresses. It is a landmark prediction design with equal weight per row, not independent-user sampling. The final test reports seen and unseen-to-parameter-training addresses separately. |
| Why AP rather than accuracy? | Only 4.31% of test accounts return. AP summarizes the precision/recall ranking across score thresholds. Predicting everyone negative would have high accuracy without finding returners. AP here uses the official step-weighted definition, not trapezoidal PR area. |
| Did the neural model win? | Seed 42 was primary before testing. Its validation AP is highest among the learned model families, but test AP is below logistic regression and gradient boosting. Seed 73 has higher test AP, but choosing it afterward would change the evaluation rule. No reliable neural superiority claim is made. |
| Why are probabilities too high? | Training prevalence is about 13.95%, validation 9.61% and final test 4.31%. The final test is after earning ends. This shift is consistent with overprediction, but the study does not isolate its cause. No extra calibration model was fitted. |
| Does permutation importance show what causes retention? | No. It measures how validation AP depends on a feature for the fitted model. Correlated windows share information; shuffle variation is not a causal effect or confidence interval. |
| Why withhold voluntary return and acquisition cost? | The indexer omits the marker separating ADL from other decreases. Allocation recipients can merge original accounts through receiver overrides. Neither voluntary decrease classification nor trader-level reward attribution is established. |
| Is the extract complete and Dune-validated? | Local checks establish contiguous requested partitions, unique IDs, terminal pagination and agreement with an independent recount. They cannot prove upstream completeness. Five receipts validate selected fields only. Dune SQL has not run, so no Dune agreement is claimed. |
| What would you do next? | Replicate across other campaigns and market regimes, audit historical data availability, and obtain pre-override reward attribution. A targeting or causal incentive question needs a separately designed experiment or defensible quasi-experiment. |

## Numbers to keep consistent

Use the saved reports as the source during a demonstration:

- Descriptive cohort: **22,145 accounts**; R30: **954 / 22,145 = 4.31%**.
- Cumulative30: **2,997 / 22,145 = 13.53%**; sustained two-day R30: **473 / 22,145 = 2.14%**.
- Primary MLP: **seed 42**, test **AP 0.3387**, top **2,215** captures **565 / 954 = 59.22%**; top-decile precision **25.51%**, lift **5.92×**.
- Baselines: logistic regression test **AP 0.3412**; histogram gradient boosting **0.3403**.
- Mean MLP probability: **6.48%**; observed test return rate: **4.31%**.

The core history comparison uses any observed eligible indexed activity and has 4,016 previously observed accounts. The ML pre-campaign flag uses successful openings only and has 3,985 at the final cutoff. Do not substitute these definitions for one another.
