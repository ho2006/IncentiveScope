# GMX STIP published reward allocations

The official type-1003 archive contains **19 earning epochs, 46,855 recipient × epoch rows and 16,528 distinct recipient addresses**, allocating exactly **4,984,768.849960484548991571 ARB**. This is a program-wide allocation total, separate from the positive-size opening/increase cohort used for retention. Published recipient addresses are not verified original trading accounts or people.

## Frozen evidence

The importer pins [GMX commit a85ea349](https://github.com/gmx-io/gmx-synthetics/tree/a85ea3491c19c93bb4b5a002d9b358fb769b7849/scripts/incentives/distributions). All 19 distribution JSONs and their 19 transaction-data companions have **the same Git blob hashes** at the historical [final-epoch commit ed306a37](https://github.com/gmx-io/gmx-synthetics/commit/ed306a37f1fab314a59c8f4595da18802599db6a), dated March 27, 2024. Both recursive trees were complete. The [38-file comparison receipt](../data/evidence/reward-allocations/archive-comparison.json) establishes that this later pinned import preserves the historical artifacts byte for byte.

The public [manifest](../data/evidence/reward-allocations/manifest.json) records every immutable source URL, Git blob SHA, SHA-256 checksum, exact total and extraction timestamp. The [epoch summary](../data/evidence/reward-allocations/epoch_summary.csv) exposes all 19 sums and recipient counts. Its SHA-256 is `60d56b9ec33c23ea0a3f49e824123b675e94968104c55d74aa39e42ebfe54a18`. The larger recipient ledger and original JSONs are regenerated locally rather than committed.

## Units and reconciliation

The token is Arbitrum ARB (`0x912ce59144191c1204e64559fe8253a0e49e6548`, chain 42161). JSON amounts are integer base units with 18 decimals. The importer uses integer arithmetic throughout, rejects duplicate JSON/address keys, validates the token, distribution type and epoch ID, and requires each allocation sum to equal its companion `transactionData.totalAmount`. A batch calldata file is a payment plan; this project has not checked its execution or subsequent transfers on chain.

The [official final report](https://forum.arbitrum.foundation/t/leveraging-the-stip-grants-program-to-grow-the-gmx-and-arbitrum-defi-ecosystem/23100) reports 4,984,768.84 ARB across the trading program. The exact JSON total exceeds that aggregate of rounded reporting by 0.009960484548991571 ARB. The last epoch has 2,612 recipients and 224,976.957207028746738057 ARB, agreeing with the report's 2,612 and 224,976.96 ARB to cents. The [boundary note](boundary-evidence.md) connects the epoch dates to the actual earning interval: after November 15 midnight through March 27 midnight UTC, with the latter excluded.

## Attribution and interpretation

The historical [generation script](https://github.com/gmx-io/gmx-synthetics/blob/ed306a37f1fab314a59c8f4595da18802599db6a/scripts/incentives/stipTradingIncentives.ts) applies receiver overrides and a 0.1 ARB allocation threshold before saving. Overrides can merge multiple original trading-account allocations into one recipient amount. None of the 19 files records `appliedOverrides`; that absence means unknown override exposure, not evidence of no overrides. The historical override map includes a nonzero Abra account-to-recipient replacement, detailed in the boundary note.

Consequently, this ledger does not establish trader-level reward costs, acquisition cost, cost per retained address, USD spend or causal ROI. Even a direct address match would only be a match between two published addresses. A positive allocation need not correspond to the opening/increase cohort, since rebates also cover closing fees; an absent allocation need not mean no activity, since the minimum threshold can exclude small amounts. Those differences require explicit denominators before any future attribution analysis.

## Reproduce

Run from the repository root in PowerShell 7 after installing the project:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_rewards.py --output data/raw/rewards
```

The downloader verifies all 38 source blobs before emitting `recipient_rewards.csv`, `epoch_summary.csv` and `manifest.json`. Cached source corruption or a missing/mismatched epoch fails the run rather than producing a partial ledger. The download uses public GMX artifacts and requires no Dune account or API key.
