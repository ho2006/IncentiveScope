# IncentiveScope application portfolio

**Project:** IncentiveScope — On-chain incentive research and participation prediction  
**Case:** GMX V2 / Arbitrum STIP trading rebates, 2023–2024  
**Tools:** SQL, DuckDB, Python, PyTorch, scikit-learn, Git and GitHub Actions

## Reviewer links

| Review goal | Link |
| --- | --- |
| Read the integrated English research story | [English portfolio report](https://ho2006.github.io/IncentiveScope/portfolio/) |
| Explore participation definitions and cohorts | [Research dashboard](https://ho2006.github.io/IncentiveScope/) |
| Inspect model results, reliability and feature dependence | [Prediction dashboard](https://ho2006.github.io/IncentiveScope/ml/) |
| Review implementation and source evidence | [GitHub repository](https://github.com/ho2006/IncentiveScope) |
| Inspect the reproducible experiment | [Saved ML notebook](https://github.com/ho2006/IncentiveScope/blob/main/notebooks/retention-ml.ipynb) |
| Recompute from frozen input | [Reproduction runbook](https://github.com/ho2006/IncentiveScope/blob/main/docs/reproduction.md) |
| Follow a short live demonstration | [Interview walkthrough](https://github.com/ho2006/IncentiveScope/blob/main/docs/interview.md) |

## Resume bullets

Use these bullets where they accurately describe your contribution to the project:

- Built IncentiveScope, a reproducible SQL/Python study of 907,107 GMX V2 indexed executions on Arbitrum; fixed a 22,145-account campaign cohort and measured 4.31% R30 opening participation after STIP rebates ended, with independent count reconciliation and selected on-chain receipt checks.
- Implemented a PyTorch MLP and four reference methods using 17 pre-cutoff behavioral features and a strict temporal holdout; the primary MLP achieved test Average Precision of 0.3387 and captured 565 of 954 returns in its top 10% ranking, while reporting stronger traditional baselines and probability overprediction.
- Published interactive research dashboards, executed notebooks, frozen input hashes, predictions and saved weights; separated event-time prediction from incentive causality and documented data-quality, fee-semantics and reward-attribution limits.

**One-line version:** Built IncentiveScope, an open-source SQL/Python/PyTorch analysis of 907,107 GMX V2 executions, combining independently reconciled incentive-participation metrics with temporal prediction benchmarks and publicly inspectable research artifacts.

## Project description for an application form

> IncentiveScope studies participation after GMX V2's Arbitrum STIP trading rebates and whether prior behavior can predict later opening activity. I built an auditable SQL/Python pipeline over 907,107 indexed executions and a fixed cohort of 22,145 accounts. R30 opening participation was 4.31%, compared with 13.53% cumulative 30-day return. A separate PyTorch experiment uses 17 pre-cutoff features and strict training, validation and test dates. The primary MLP captured 59.22% of returns in its top 10% ranking, but logistic regression had slightly higher test AP. The project publishes research dashboards, notebooks, predictions, checkpoints and a frozen-input reproduction path, with explicit limits on causal inference and reward attribution.

## Short spoken pitch

> I built IncentiveScope to connect on-chain data engineering with careful incentive research. It measures GMX opening participation after rebates ended, then tests whether earlier trading behavior predicts later return. The core cohort has 22,145 accounts; 954 return in the R30 window. The PyTorch model ranks returners well, but a simple logistic model performs slightly better on the final test. I publish that comparison, probability bias and data limitations alongside the code and reproducible artifacts. The project shows how I turn protocol events into a question, defensible metrics and an inspectable research result.

## What the work demonstrates

| Capability | Inspectable evidence |
| --- | --- |
| SQL and data engineering | [Metric SQL](../src/incentivescope/metrics.sql), indexed-history extraction, fixed denominators, UTC windows and independent Python recounts |
| On-chain interpretation | [Earning boundaries](boundary-evidence.md), [selected receipt checks](event-validation.md), account attribution, fee scaling and the ADL classification limitation |
| Research design | [English report](portfolio-report.md), multiple return definitions, historical cohorts, concentration sensitivity and explicit counterfactual limits |
| PyTorch and model evaluation | [ML methods](ml.md), training-only preprocessing, time-held-out evaluation, traditional baselines, all three seeds, checkpoint replay and reliability analysis |
| Reproducibility and communication | [Runbook](reproduction.md), frozen-input release, artifact manifests, saved notebooks, portable dashboards and independent core/ML CI checks |

## Claims supported by this portfolio

The deliverable is an observational study and a historical prediction benchmark from one campaign. It does not estimate incentive-caused retention, acquisition cost or ROI. Protocol addresses are not unique people. Receipt checks cover five selected executions rather than the full history. Dune companion SQL is source-reviewed and unexecuted. The neural model's primary test AP is below the logistic and tree baselines; its reported ranking benefit does not establish an intervention benefit or cross-campaign generalisation.

The language above describes the project itself. Add personal experience, education or role-specific qualifications only when they are supported by your own record.
