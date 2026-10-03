# First GMX STIP trading rebates: earning-boundary evidence

Verified from public first-party sources on 2026-10-03 (Asia/Shanghai). This note concerns GMX V2 on Arbitrum, distribution type **1003**, rather than liquidity, migration, trading-competition, or STIP Bridge rewards.

## Decision

The archived trading-rebate earning epochs run from **2023-11-15 00:00:00 UTC** through **2024-03-27 00:00:00 UTC**, with the end excluded. The historical indexer applies a **strictly greater than** start guard: Unix seconds `1700006400 < timestamp < 1711497600`. For an integer-second dataset using a half-open interval, its exact representation is `[2023-11-15T00:00:01Z, 2024-03-27T00:00:00Z)`.

The end is an evidence-based reconstruction from the final published earning epoch, its generating code, and its reconciliation to the final report; it is not inferred from the overall program's March 29 administrative end. This verifies the archived reward-program boundary; it does not independently verify the deployed indexer or prove receipt of every published allocation on chain.

## Reproducible evidence chain

| Question | Evidence | Interpretation |
| --- | --- | --- |
| Did earning begin November 15 or 16? | The [contemporaneous launch indexer](https://github.com/gmx-io/gmx-subgraph/blob/d8ceec8488be098e9350b570639f26ec8c211b12/synthetics-stats/src/entities/incentives/tradingIncentives.ts) sets `INCENTIVES_START_TIMESTAMP` to `1700006400` and tests `timestamp > INCENTIVES_START_TIMESTAMP`. The same guard remains in the [March 2024 revision](https://github.com/gmx-io/gmx-subgraph/blob/f6877d665508241a949e6b857f9a9ff9c406a298/synthetics-stats/src/entities/incentives/tradingIncentives.ts). | The calculation starts after November 15 midnight UTC. November 16 in narrative reporting does not move the earning guard. |
| What does an epoch directory date mean? | The historical [distribution script](https://github.com/gmx-io/gmx-synthetics/blob/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/stipTradingIncentives.ts) requests `userTradingIncentivesStats` at the `fromTimestamp` with period `1w`; [helpers](https://github.com/gmx-io/gmx-synthetics/blob/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/helpers.ts) save the `fromDate` as `epoch_YYYY-MM-DD` and compute the end as start plus seven days. | The directory names earning-period starts, not payment dates. |
| Where are weekly boundaries? | The [historical indexer time utility](https://github.com/gmx-io/gmx-subgraph/blob/f6877d665508241a949e6b857f9a9ff9c406a298/synthetics-stats/src/utils/time.ts) buckets weekly observations as `floor((timestamp + 86400) / 604800) * 604800 - 86400`. | UTC Wednesday midnight, including the lower bucket boundary and excluding the next. The separate launch guard excludes the first start second. |
| Which earning epoch was last? | [Commit ed306a3](https://github.com/gmx-io/gmx-synthetics/commit/ed306a37f1fab314a59c8f4595da18802599db6a), authored 2024-03-27 09:10:28 UTC, adds the March 20 files and describes the epoch as March 20–27. Its complete [Git tree](https://api.github.com/repos/gmx-io/gmx-synthetics/git/trees/ed306a37f1fab314a59c8f4595da18802599db6a?recursive=1) contains 19 trading-rebate JSON files, weekly from November 15 through March 20. | Final earning interval is `[2024-03-20T00:00:00Z, 2024-03-27T00:00:00Z)`. |

The [GMX final report](https://forum.arbitrum.foundation/t/leveraging-the-stip-grants-program-to-grow-the-gmx-and-arbitrum-defi-ecosystem/23100) lists 19 trading epochs, numbered 2–20. Its first row has 2,265 recipients and 247,997.41 ARB; its final row has 2,612 recipients and 224,976.96 ARB. These match the first and last JSONs below to cents. The report's aggregate is 4,984,768.84 ARB. Its narrative says November 16, whereas the [later addendum](https://forum.arbitrum.foundation/t/gmx-stip-addendum/23484) says trading began November 15 and separately gives March 29 as the overall program end. The machine-readable earning definitions resolve the date conflict for this analysis.

## Official reward files and units

Use the immutable revision `ed306a37f1fab314a59c8f4595da18802599db6a` for all 19 first-round files:

```text
https://raw.githubusercontent.com/gmx-io/gmx-synthetics/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/distributions/epoch_YYYY-MM-DD/stipTradingIncentives_distribution.json
```

| File | Recipient count | Sum of integer amounts / 10^18 |
| --- | ---: | ---: |
| [2023-11-15 JSON](https://raw.githubusercontent.com/gmx-io/gmx-synthetics/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/distributions/epoch_2023-11-15/stipTradingIncentives_distribution.json) | 2,265 | 247997.414469294663258992 ARB |
| [2024-03-20 JSON](https://raw.githubusercontent.com/gmx-io/gmx-synthetics/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/distributions/epoch_2024-03-20/stipTradingIncentives_distribution.json) | 2,612 | 224976.957207028746738057 ARB |

Observed schema: `token`, `distributionTypeId`, `id`, `amounts`. `distributionTypeId` is `1003`; token is Arbitrum ARB `0x912CE59144191C1204E64559FE8253a0e49E6548`; IDs are `YYYY-MM-DD_1003`. Amounts are integer decimal strings in ARB base units (18 decimals). Parse integers or exact decimals, not floating-point currency. Companion CSVs format only two decimal places; use JSON for calculation. Companion `stipTradingIncentives_transactionData.json` files contain batch calldata and total amounts, which are transaction inputs rather than proof that the batches executed.

The historical generation code applies a **0.1 ARB minimum allocation threshold** before saving. A trader absent from `amounts` may have traded without meeting that threshold. A positive allocation establishes published reward entitlement, not payment settlement, identity, or an incrementally acquired user. The official files should therefore be labelled **published allocations** until reconciled against transfer logs.

## Recipient attribution caveat

The generating script begins with the subgraph's protocol `account`, then invokes `overrideReceivers` before saving. That helper deletes an original account key and adds its amount to a replacement recipient; if the replacement is already present, it sums the amounts. Historical JSON files do **not** save `appliedOverrides` metadata.

The [receiver override map at the final distribution commit](https://github.com/gmx-io/gmx-synthetics/blob/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/receiverOverrides.ts) contains:

| Original account | Payment recipient | Source label |
| --- | --- | --- |
| `0x7C8FeF8eA9b1fE46A7689bfb8149341C90431D38` | `0xA71A021EF66B03E45E0d85590432DFCfa1b7174C` | Abra |
| Zero address | `0x0000000000000000000000000000000000000001` | Test mapping |

Do not blindly reverse this map: merging can prevent recovery of each original account's allocation. A direct recipient-to-trade-account join is usable as a **direct-address match**, provided unmatched recipients and override exposure are reported. Full trader-level cost attribution needs the contemporaneous weekly source statistics or an unambiguous pre-override ledger.

## Remaining limits

- The reward cohort and the project's positive-size opening/increase cohort differ: rebates also cover closing fees and have a minimum allocation threshold. Keep both denominators explicit.
- Competition distributions use types `2001` and `2002`; later STIP Bridge trading uses `1005`. Exclude them from type-1003 costs. Competition exposure may still affect observed behavior.
- The historical subgraph's `first: 10000` reward query has no pagination. Published recipient counts are below that cap, but this alone does not prove that all pre-threshold source rows were included. Treat the ledger as the official allocation record, not an independent reconstruction of economic eligibility.
- A live read on 2026-10-03 of the old `https://arbitrum-api.gmxinfra.io/incentives/stip?timestamp=...` endpoint returned `trading.isActive=false` for times inside and outside this historical program. It cannot independently establish historical activation; prefer the pinned archive.
- Reporting a post-STIP result still requires complete follow-up data, treatment of overlapping campaigns, and explicit descriptive rather than causal language.
