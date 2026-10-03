# IncentiveScope — Synthetic STIP-style example / not GMX research findings

**SYNTHETIC DEMONSTRATION — NOT GMX FINDINGS**



This note measures execution-based repeat participation. It does not estimate causal acquisition or count people.

Data coverage: 2023-09-20T00:00:00Z to 2024-05-29T00:00:00Z (exclusive), UTC.

Configured earning window: [2023-11-15T00:00:00Z, 2024-03-29T00:00:00Z). Post anchor: 2024-03-29T00:00:00Z.

Source: https://github.com/ho2006/IncentiveScope

Input SHA-256: `d9263b14cf27032cc82b062c670c02297515430cbd18a3bec85d990bbedf2452`



## Findings

Reward cost: unavailable until address-level earning-epoch allocations can be reconciled.

## Results

Fixed campaign cohort: **6 addresses**.

- r30: 50.0% (3/6 addresses).

- cumulative30: 66.7% (4/6 addresses).

- sustained30: 16.7% (1/6 addresses).

- open_or_decrease30: 66.7% (4/6 addresses).

- voluntary30: 66.7% (4/6 addresses).

- strict_r30: 33.3% (2/6 addresses).

- r60: 33.3% (2/6 addresses).



Concentration sensitivity:

- All addresses: 50.0% (3/6 addresses).

- Excluding top 1% (ceil): 40.0% (2/5 addresses).

Mature equal-window cohort: 5 addresses. Post/pre activity ratio: N/A; position-fee ratio: N/A. N/A includes zero baselines and unavailable inputs.



## Method and sensitivity

The campaign cohort includes accounts with a successful positive-size opening/increase during the configured earning window. It includes accounts that never return. R30 counts at least one such execution during post days 24–30. Cumulative30 counts a return anywhere within the first 30 complete days. Sustained30 requires two distinct UTC activity dates in the R30 window.

Strict return additionally requires an order created after earning ended; it is withheld when creation timestamps are missing for qualifying R30 events. Liquidations, collateral-only changes and cancelled orders are excluded from opening-only metrics. Open-or-decrease30 is a broader candidate measure. Voluntary30 is withheld when ADL decreases cannot be independently separated.

Entry-week and observed-history groups reveal exposure differences. Top-1% exclusion ranks on campaign-period size only, with a ceiling rule and account tie-break. These are sensitivity checks, not a randomized control group.

## Limitations

- All accounts, orders and amounts are synthetic. These are software checks, not GMX observations.

- The constructed universe includes non-returners, late entry, closing-only return, liquidation and an old limit order.

- First-observed labels use this extraction window, not complete protocol history.

- Amounts are preserved in source CSV; volume ranking uses floating point, fees use 12 decimal places.

- Other incentives and market conditions may affect participation after the configured campaign ends.

- Reward cost is withheld without reconciled address-level allocations. Fees are withheld when missing; no funding or gas is imputed as a position fee.



## Operating implications

For synthetic data, these are pipeline checks only. For real exploratory data, conclusions remain conditional on earning-boundary verification. For verified historical data, assess sustained participation alongside concentration and fee coverage; observed changes alone do not justify changing incentive budgets. No causal ROI is estimated.

## Evidence



## Reproduction

See the repository README for the exact analyze command. results.json, wallet_cohorts.csv and wallet_daily.csv are generated from one frozen input and its checksum manifest.
