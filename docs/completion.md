# v0.2 completion record

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
