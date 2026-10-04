# Three-minute research demo

## 0:00–0:30 — Question and design

"I built IncentiveScope to ask who continues opening GMX V2 positions after the first Arbitrum STIP trading rebates end. I verified earning epochs rather than treating the overall grant deadline or payment day as the cutoff. The campaign cohort is fixed at 22,145 protocol accounts, including every account that never returns."

## 0:30–1:30 — Show the dashboard

"R30 is 954 accounts, or 4.31%, during days 24–30. Any opening in the first 30 days is 13.53%; repeated activity on two dates in the last week is 2.14%. These are different operational questions. Prior-observed accounts return more often, but they are not an untreated control. Removing the top one percent of campaign opening-size accounts gives 4.12%, so the aggregate finding is not eliminated by that sensitivity."

Show the definition chart, then the history comparison and entry-week heatmap. Select a history group in the cohort table and explain that the overall chart denominators remain fixed.

## 1:30–2:30 — Explain credibility and one correction

"The extract has 907,107 indexed executions in 36 contiguous partitions. Input checksums and raw caches make it inspectable; independent Python sets reproduce the SQL counts. I checked five chain receipts and used the position account instead of the keeper sender. I also found ADL can be a market decrease while the indexer omits the secondary marker, so I withheld voluntary-return claims. The main opening-only result remains available."

"Official allocation files total about 4.98 million ARB, but receiver substitutions can merge original accounts. I do not divide that program total by retained opening accounts or call it acquisition cost. Binance Wallet tasks overlap early follow-up, and previous Odyssey exposure affects the historical group. These limitations prevent a causal reward-effect claim."

## 2:30–3:00 — Implication and reproduction

"I recommend monitoring cumulative reach, end-of-month opening activity and repeated-day participation together. The evidence motivates a future experiment; it does not determine an optimal rebate budget. A reviewer can inspect the saved dashboard without credentials, download the frozen input for exact recomputation, or refetch the public source. Dune cross-check SQL is source-reviewed but has not been executed."

## Resume sentence

Built IncentiveScope, a reproducible SQL/Python study of 22,145 GMX V2 trading accounts on Arbitrum using 907,107 indexed executions; independently reconciled post-STIP retention counts, validated selected on-chain events and fee semantics, and published a research dashboard with a frozen-input reproduction path.

## Questions to prepare

- Why use protocol account instead of transaction sender?
- Why is R30 lower than cumulative30, and why can R60 exceed R30?
- What do first-observed labels establish when history is truncated?
- Why can ADL contaminate a decrease-based participation metric?
- Why do published reward recipients differ from the opening cohort?
- What would be needed to estimate a causal effect or acquisition cost?
- What source omissions can local pagination and uniqueness checks fail to detect?

## Optional ML demonstration

Open [the retention-prediction study](https://ho2006.github.io/IncentiveScope/ml/) and compare the primary PyTorch MLP with logistic regression, gradient boosting and recent activity. Show validation-selected configurations before discussing test performance. Explain why all inactive eligible addresses remain, why the scaler only fits training rows, and why seed 42 was fixed before looking at test results. Then show the reliability plot: ranking quality and probability accuracy answer different questions when the positive rate changes after rebates end. Use the published metrics directly, including a baseline win if that is what occurred.

Prepare to explain repeated training addresses, feature leakage from full-campaign aggregates, AP versus trapezoidal PR-AUC, unseen-to-training subgroup meaning, checkpoint replay, correlated-feature permutation importance, and why this event-time experiment is not an incentive causal analysis or audited historical real-time deployment.
