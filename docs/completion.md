# IncentiveScope completion record

## v0.3 portfolio and prediction delivery — October 4, 2026

The application-ready package combines the historical GMX STIP case with a PyTorch participation-prediction experiment. Start with the [English report](https://ho2006.github.io/IncentiveScope/portfolio/), [six-page PDF](https://ho2006.github.io/IncentiveScope/portfolio/research.pdf), [application copy](application.md) and [three/five-minute demonstration](interview.md). The [v0.3.0 release](https://github.com/ho2006/IncentiveScope/releases/tag/v0.3.0) packages the report, tested wheel and reproduction receipts. The separate v0.2.0 release remains the frozen raw-input source.

Delivered prediction research uses 17 pre-cutoff features, five earlier training cutoffs, a later validation cutoff and one final post-rebate holdout. A training-only scaler, fixed seeds 17/42/73, validation-only selection/early stopping and saved checkpoints make the experiment inspectable. The primary seed is 42: test AP **0.3387**, below logistic regression **0.3412** and histogram gradient boosting **0.3403**. Its top 2,215 scores capture 565 of 954 returns. Reliability, validation permutation importance and seen/unseen training-address results are published with the full metrics; no neural-model superiority or incentive-causal claim is made.

The integrated English report joins the research question, event definitions, validation, descriptive results, temporal model comparison and limitations. Its HTML and PDF are backed by a [source/output manifest](../reports/gmx-stip/portfolio/manifest.json). All six PDF pages were rendered and visually inspected; the browser report was checked at desktop and mobile widths. README now provides reviewer, technical, reproduction and interview entry points.

### Actual full CPU reproduction rehearsal

The [session receipt](../data/evidence/reproduction/portfolio-session.json) and [comparison receipt](../data/evidence/reproduction/portfolio-cpu.json) record a successful independent-clone exercise at **`a7c87dec0c18d36ef19e5b001a3c0bcddd8753cc`**, completed **2026-10-04 10:11:07 UTC**. It used PowerShell **7.6.5**, Python **3.14.4**, DuckDB **1.5.6** and PyTorch **2.14.1+cpu**; all **39 checks passed**. The separately created environment installed a built wheel and verified a `site-packages` import, then downloaded and checked the public frozen release input. The final model run recorded a clean tracked worktree.

- Core analytical JSON matched exactly: **22,145 addresses / 954 R30 positives**. All **324,448** daily-export rows matched exactly.
- The **22,145-row** core cohort export had **548** accepted floating USD-field differences under the explicit `1e-12` relative/absolute policy, with no other differences. Counts and labels require exact equality.
- All **71,146 feature rows**, **155,015 prediction rows**, preprocessing parameters and **123 training-curve rows** matched exactly. Their corresponding saved data hashes and all **three PyTorch checkpoint hashes** matched.
- Both notebook copies executed in saved-result inspection mode, following the separate raw CLI rebuild and full CPU retraining. Their execution is not presented as notebook retraining.

Earlier attempts caught Windows Git newline conversion of frozen evidence. `.gitattributes` now preserves hashed bytes, and checks cover the reward ledger, sample input, Dune probe and CUDA probe sources. The final successful attempt reused its own environment after these repairs; installation may use download caches. The 51.375-second training stage is a local recorded timing, not a cold-start or cross-machine benchmark. No expected analytical result was changed to obtain a pass.

The optional RTX 5060 Ti probe separately checks synthetic CUDA training and checkpoint reloads. It is not a full-dataset GPU benchmark. Dune execution remains unavailable; reward allocations are not payment verification, and the study still has no causal control group or complete historical chain/indexer audit.

## v0.2 historical case delivery — October 3, 2026

Recorded October 3, 2026. This is a historical 2023–2024 study, not current GMX monitoring.

## Completed research scope

- Reconstructed earning boundaries from contemporaneous calculation code, 19 archived epochs and the official final report.
- Acquired 36 contiguous partitions: 907,107 indexed execution rows over September 20, 2023–May 29, 2024, with exclusive UTC end. Frozen CSV SHA-256: `76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3`.
- Independently reconciled the 22,145-account cohort and opening-based R30, cumulative30, sustained30, strictR30 and R60 using Python sets.
- Independently reconciled mature-account equal-window activity and net opening-fee totals; inspected the September address surge and earlier task-campaign context.
- Validated five selected March chain receipts for account, type, size, execution index and fee semantics. This is a limited sample, not a full-chain replay.
- Reconciled all 19 official type-1003 allocation epochs and verified 38 source blobs against the contemporary archive.
- Generated five SVG figures, offline interactive HTML, public CSV/JSON evidence, a 1,962-word English research report and an interview demo.
- Executed both notebooks. The real notebook's opt-in raw mode reproduces all metric groups; its committed default mode is explicitly snapshot inspection.

## Reproduction and checks

`checks.py`: **22 checks passed**. They cover input integrity, boundaries, fixed denominators, missingness, semantic withholding, fees, rewards, cache integrity, partition publication and public artifact reconciliation.

A fresh virtual environment installed a built **incentivescope 0.2.0** wheel with **DuckDB 1.5.6**, using **Python 3.14.4** on Windows and PowerShell 7. The import came from the new environment's `site-packages`, not the editable source tree. The release gzip was decompressed into a separate working directory; installed-package analysis matched the frozen dataset/campaign metadata and all summary, cohort, weekly, heatmap, segment, robustness, activity and quality fields. GitHub Actions additionally checks Python 3.11 on Windows.

Browser checks covered desktop and narrower responsive layouts, five figures and the native cohort filter. Selecting the existing-history group shows 20 rows and leaves other tables and overall denominators unchanged. Large scientific-notation displays and narrow chart panels were revised for readability.

## Publication

The GitHub repository contains the source-backed outputs. GitHub Pages is configured to publish `reports/gmx-stip` only after the Windows checks pass. The v0.2.0 release provides the compressed normalized CSV, source manifest and asset checksums; original query-response caches remain local.

## Explicit limits and deferred work

- Dune table definitions and companion SQL were checked against pinned official Spellbook source. Queries have **not been executed or published** in Dune; cross-source agreement is unknown.
- Voluntary30 is withheld because the indexed source lacks the secondary marker needed to distinguish ADL market decreases. The broader candidate metric is labelled open-or-decrease30.
- Reward allocations are not verified payments. Receiver merging prevents full original-trader cost attribution; unit acquisition cost and causal ROI are not produced.
- Full upstream population completeness, historical deployed bytecode, other collateral/period receipt samples and order-creation receipt replay remain unverified.
- Address histories are truncated, prior incentive exposure is documented and post windows overlap other campaigns. The case makes descriptive claims with no treatment-control or causal attribution.

These deferred validations are disclosed evidence limits. They do not invalidate the delivered, reproducible opening-based historical case.

## Dune follow-up, October 3, 2026

The Chrome connection reached a signed-in Dune editor and prepared the one-day schema probe. Run and Create remained disabled on the view-only plan after its trial ended. The [attempt record](../data/evidence/dune/execution-status.json) keeps query/execution IDs null; no Dune execution or independent source agreement has been obtained.

The revised daily SQL emits 252 dates, checks event matching in both directions, counts raw duplicates and join multiplication, and separates uniquely identified swaps. Retention exports five unambiguous metric rows and checks creation keys across all source history before the cutoff. A new provenance-bound CSV reconciler detects missing days, invalid grain, incorrect hashes and metric differences while withholding strict retention when creation evidence is incomplete. Synthetic checks cannot produce a real validation flag.

All **24 checks passed** after these changes. DuckDB fixtures validate SQL logic, not the Dune compiler or deployed datasets. Regenerated real artifacts retain the 22,145-account cohort and R30 numerator 954, and now display exact UTC measurement windows and the pending cross-source status. The frozen v0.2.0 input release remains the reproduction source.
