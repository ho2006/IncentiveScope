# IncentiveScope — GMX V2 / Arbitrum STIP trading rebates (2023–2024)

**HISTORICAL DESCRIPTIVE RESEARCH**



This note measures execution-based repeat participation. It does not estimate causal acquisition or count people.

Data coverage: 2023-09-20T00:00:00Z to 2024-05-29T00:00:00Z (exclusive), UTC.

Configured earning window: [2023-11-15T00:00:01Z, 2024-03-27T00:00:00Z). Post anchor: 2024-03-27T00:00:00Z.

Source: https://gmx.squids.live/gmx-synthetics-arbitrum:prod/api/graphql

Input SHA-256: `76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3`



## Findings

- R30 is 4.3% (954/22,145), versus 13.5% cumulative30; these answer different questions. Sustained two-day R30 is 2.1%.

- First-observed campaign addresses return at 3.4% (608/18,129), versus 8.6% (346/4,016) for previously observed addresses. These are address-history groups, not acquisition or causal treatment groups.

- Removing the top 1% by campaign opening size gives 4.1% R30 (904/21,923); the low aggregate result is not eliminated by this volume sensitivity.

- For 17,390 mature addresses, post/pre active-address-day intensity is 0.559 and net opening position-fee intensity is 0.337. These are equal-window descriptive comparisons, not the causal effect of ending rewards.

- Strict new-order R30 equals opening R30; R60 is 5.1% (1,126/22,145). Voluntary30 remains unavailable because the indexed source cannot separate ADL decreases.

19 official epochs: 4984768.849960484548991571 ARB allocated to 16,528 recipient addresses. Allocation files are not payment receipts; receiver overrides prevent full trader-level attribution. Cost per retained account remains unavailable.

## Results

Fixed campaign cohort: **22145 addresses**.

- r30: 4.3% (954/22,145 addresses).

- cumulative30: 13.5% (2,997/22,145 addresses).

- sustained30: 2.1% (473/22,145 addresses).

- open_or_decrease30: 5.0% (1,101/22,145 addresses).

- voluntary30: N/A — unavailable.

- strict_r30: 4.3% (954/22,145 addresses).

- r60: 5.1% (1,126/22,145 addresses).



Concentration sensitivity:

- All addresses: 4.3% (954/22145 addresses).

- Excluding top 1% (ceil): 4.1% (904/21923 addresses).

Mature equal-window cohort: 17390 addresses. Post/pre activity ratio: 0.5589; position-fee ratio: 0.3372. N/A includes zero baselines and unavailable inputs.



## Method and sensitivity

The campaign cohort includes accounts with a successful positive-size opening/increase during the configured earning window. It includes accounts that never return. R30 counts at least one such execution during post days 24–30. Cumulative30 counts a return anywhere within the first 30 complete days. Sustained30 requires two distinct UTC activity dates in the R30 window.

Strict return additionally requires an order created after earning ended; it is withheld when creation timestamps are missing for qualifying R30 events. Liquidations, collateral-only changes and cancelled orders are excluded from opening-only metrics. Open-or-decrease30 is a broader candidate measure. Voluntary30 is withheld when ADL decreases cannot be independently separated.

Entry-week and observed-history groups reveal exposure differences. Top-1% exclusion ranks on campaign-period size only, with a ceiling rule and account tie-break. These are sensitivity checks, not a randomized control group.

## Limitations

- Indexed data, not an independent replay of historical deployed contracts.

- Order types 2–7 only; type 7 liquidations are excluded from opening/increase. ADL may appear as type 4; this surface has no secondaryOrderType, so voluntary-decrease classification is unverified.

- USD sizeDeltaUsd is scaled by 10^30.

- Net position fee USD=(positionFeeAmount-traderDiscountAmount)*collateralTokenPriceMin/10^30; missing fields stay unknown. Excludes external rebates, borrowing, funding, UI fees and gas.

- Missing OrderCreated records remain unknown, never treated as post-campaign creations.

- Raw response caches are immutable snapshots for this request; use a new directory to refresh.

- Archived type-1003 epochs verify earning after Nov 15 midnight through Mar 27 midnight UTC (exclusive). The historical indexer uses timestamp >1700006400, represented as start=00:00:01 for integer-second events. Final epoch, historical code and report reconcile; March 29 is the overall administrative end. See docs/boundary-evidence.md.

- First-observed labels use this extraction window, not complete protocol history.

- Voluntary30 is withheld: this indexer does not expose secondary order type; ADL can be a market decrease. Open-or-decrease30 and first-observed history may include ADL decreases. Opening-only retention is unaffected.

- Amounts are preserved in source CSV; volume ranking uses floating point, fees use 12 decimal places.

- Other incentives and market conditions may affect participation after the configured campaign ends.

- Reward cost is withheld without reconciled address-level allocations. Fees are withheld when missing; no funding or gas is imputed as a position fee.



## Operating implications

For synthetic data, these are pipeline checks only. For real exploratory data, conclusions remain conditional on earning-boundary verification. For verified historical data, assess sustained participation alongside concentration and fee coverage; observed changes alone do not justify changing incentive budgets. No causal ROI is estimated.

## Cross-source validation

Dune SQL is prepared but not executed: the browser session had disabled Run/Create controls on a view-only plan. No query/execution ID or cross-source agreement is claimed. Local independent Python recounts remain available.

## Evidence

- [Verified earning boundaries](https://github.com/ho2006/IncentiveScope/blob/main/docs/boundary-evidence.md)

- [Five execution and fee receipt checks](https://github.com/ho2006/IncentiveScope/blob/main/docs/event-validation.md)

- [Historical quality and independent recount](https://github.com/ho2006/IncentiveScope/blob/main/docs/data-quality.md)

- [Official reward allocations and attribution limits](https://github.com/ho2006/IncentiveScope/blob/main/docs/reward-data.md)

- [Dune companion: source-reviewed, not executed](https://github.com/ho2006/IncentiveScope/blob/main/docs/dune.md)



## Reproduction

See the repository README for the exact analyze command. results.json, wallet_cohorts.csv and wallet_daily.csv are generated from one frozen input and its checksum manifest.

## Decision question and incentive mechanism

The practical question is whether campaign-period trading addresses continue to open positions after a trading rebate stops being earned. This can inform how an analyst monitors an incentive budget, but it cannot alone establish how many traders the program acquired or how many would have traded without subsidies. Opening activity, occasional return and sustained participation should be monitored separately. A large cumulative return count may coexist with a much smaller end-of-month active population.

The case isolates the first GMX STIP trading-rebate program on Arbitrum, distribution type 1003. It does not combine LP rewards, migration incentives, competition prizes or the subsequent STIP Bridge round. GMX allocated ARB against eligible trading fees; published allocation files apply a minimum reward threshold and recipient overrides. The study's opening/increase cohort therefore differs from the reward-recipient population. A trader can qualify for the analytical cohort without appearing in the allocation ledger, while an allocation recipient may represent a trading account that only closed positions or a substituted receiver.

The [archived indexer](https://github.com/gmx-io/gmx-subgraph/blob/d8ceec8488be098e9350b570639f26ec8c211b12/synthetics-stats/src/entities/incentives/tradingIncentives.ts) starts eligibility strictly after November 15 midnight UTC. The final archived epoch is March 20–27, as recorded in the [March 27 distribution commit](https://github.com/gmx-io/gmx-synthetics/commit/ed306a37f1fab314a59c8f4595da18802599db6a). The one-second lower-bound representation follows the integer timestamp guard. March 29 describes the overall program's administrative end and would shift both the cohort and return windows if used incorrectly. Payment dates are not substitutes for earning boundaries.

## Reading the findings

The opening-only result shows that most campaign-period addresses did not open or increase during the final week of the first complete post month. It does not mean that every absent address abandoned GMX. Some may have retained positions, only reduced exposure, traded after the measured week, or used another address. That is why the report pairs R30 with cumulative30, sustained30, weekly participation and R60. R60's later seven-day observation is allowed to exceed R30: these are distinct calendar windows, not a survival curve that must decline monotonically.

Previously observed addresses have a higher measured R30 than addresses first observed during the earning window. A plausible reading is that earlier observed participation helps identify a more persistent subset. Alternative explanations include account age, market exposure, interface choice, prior incentive exposure and the incomplete lookback. The extraction begins in September 2023 rather than protocol deployment, so "first observed" is a statement about this dataset. It is not evidence of a new person, a newly acquired customer or a first-ever GMX user. The history comparison should guide deeper cohort investigation rather than serve as an untreated control.

Excluding the largest one percent of campaign opening-size accounts modestly changes the aggregate percentage. This guards against a result dominated by a few very large traders, although it does not establish that volume or fee spending is evenly distributed. The cutoff uses information available before the end of earning. Selecting accounts by later returns would introduce outcome-based selection and undermine the comparison. An analyst evaluating reward caps should inspect the allocation and fee distributions separately before recommending a budget rule.

The mature-account comparison holds both the addresses and the number of observed days constant. Eligibility requires prior observed activity before the start of the final 30 pre days. Inactive account-days contribute zero activity; they are not removed from the denominator. Net opening position fees are measured after trader discount and before external ARB rebates. They omit decrease fees, funding, borrowing, UI fees and gas and cannot be described as total trader cost or protocol revenue. Comparing their intensity with participation helps distinguish fewer active account-days from changes in the fee-generating size mix, without isolating a causal mechanism.

## Validation strengths and remaining uncertainty

Every published result refers to one SHA-256-identified CSV with contiguous requested coverage. The extractor uses execution-ID keyset pagination, retains immutable response caches and waits for an empty terminal page. Partial runs cannot pass analysis. Independent Python sets reproduce the fixed cohort and return counts without running the DuckDB metric SQL. Daily source diagnostics disclose the September surge and an earlier GMX task campaign as possible context. This makes the results inspectable, while still leaving upstream indexer omissions or historical decoder errors possible.

Five selected execution receipts validate protocol-account attribution, event types, raw sizes, execution log indexes and collateral fee fields. They were deliberately chosen across available order types rather than randomly sampled. Their keeper transaction senders differ from position accounts, demonstrating why `tx.from` is inappropriate for this analysis. The sample covers one March day and USDC collateral; it does not certify every historical row, order type or collateral asset. Creation timestamps have complete indexed coverage for qualifying increases, but their underlying creation receipts were not independently replayed.

An additional semantic check found that [historical ADL orders](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/adl/AdlUtils.sol) use the market-decrease order type. The execution handler distinguishes them with a secondary marker that this indexed surface does not expose. The report consequently withholds voluntary30. Open-or-decrease30 remains explicitly labelled as a candidate containing potentially forced decreases. The principal opening-only measures do not depend on this missing marker. Dune companion SQL uses independently documented event models to support a future comparison, but no Dune execution or agreement is claimed here.

The 19 allocation epochs reconcile exactly to their companion batch totals and approximately to the cents-rounded official final report. Their Git blobs are unchanged between the contemporary archive and the pinned extraction revision. This establishes the published program ledger, not successful on-chain payment. Receiver substitutions can merge original amounts into another address; reversing a final receiver map cannot recover each origin's entitlement. Dividing program-wide ARB by the retained opening cohort would therefore create an unsupported unit-cost figure. No ARB/USD conversion, acquisition cost, reward per retained trader or causal ROI is reported.

## Overlaps and operating implications

The [GMX trading competition](https://gmxio.substack.com/p/the-gmx-eip4844-trading-competition) overlaps the closing weeks of the rebate campaign. The [Binance Wallet tasks](https://www.binance.com/en/support/announcement/detail/55199366818140f4afd4bc56000d92f2) overlap the first two post weeks. The R30 window is later than those documented tasks, but that does not make the whole follow-up incentive-free: task exposure can have lasting effects and other campaigns may be unobserved. Trading decisions also respond to volatility, prices, funding and broader market conditions. Neither this timeline nor equal pre/post windows provides a counterfactual for those factors.

For an incentive research team, the supported next step is a monitoring framework that reports cumulative reach, end-of-month activity and repeated-day participation together, with explicit fixed denominators. Compare entry-week and observed-history groups before interpreting a headline percentage. Preserve the distinction between trader accounts and reward receivers, and inspect budget concentration using a pre-override ledger if it becomes available. A future experiment could specify eligible cohorts and sustained-participation outcomes in advance, then randomize reward exposure or exploit a defensible quasi-experiment. The current observational results motivate those questions; they do not establish the optimal rebate level or a reason to stop rewards.

## Reproduction levels

The committed JSON, CSVs, SVGs and portable HTML provide a no-key inspection path. The saved notebook reads that audited snapshot by default and labels this as inspection, not a fresh upstream extraction. The release contains the compressed normalized input and manifest for exact local SQL recomputation. Refetching the public indexed API uses no wallet or API key, but availability and future historical corrections can change the returned snapshot. Reproduction should compare checksums and disclose any difference rather than silently overwrite the frozen result. The README provides PowerShell 7 commands for each level.
