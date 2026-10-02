# GMX V2 / Arbitrum STIP: evidence and unresolved boundaries

This is a historical descriptive case. No actual retention estimates are claimed in the included synthetic dashboard.

| Evidence | What it establishes | Remaining check |
| --- | --- | --- |
| [GMX STIP Addendum](https://forum.arbitrum.foundation/t/gmx-stip-addendum/23484) | Overall program November 8, 2023–March 29, 2024; trading start recorded as November 15 | Exact first/final trading-rebate earning epochs |
| [GMX final report](https://forum.arbitrum.foundation/t/leveraging-the-stip-grants-program-to-grow-the-gmx-and-arbitrum-defi-ecosystem/23100) | Trading-rebate mechanism and epoch-level category spending; different stated trading start | Reconcile the November 15/16 discrepancy; match earning and payment intervals |
| [GMX weekly updates](https://forum.arbitrum.foundation/t/gmx-bi-weekly-update-17-11-2023/19626) | Periodic reward distribution and adjustments | Verify the final earning cutoff, not just a grant deadline |
| [Trading competition](https://gmxio.substack.com/p/the-gmx-eip4844-trading-competition) | Additional competition around March 13–27, 2024 | Possible exposure differences between entry cohorts |
| [Binance Wallet campaign](https://www.binance.com/en/support/announcement/detail/55199366818140f4afd4bc56000d92f2) | March 27–April 9, 2024 tasks include GMX V2 leverage trading | Later participation is not an entirely incentive-free phase |
| [STIP-B update](https://forum.arbitrum.foundation/t/gmx-stip-b-bi-weekly-update/25219) | Later incentive round starts June 26, 2024 | Follow-up must not silently cross later programs |

`configs/gmx-stip.json` deliberately uses provisional illustrative UTC boundaries. Final retention is blocked by default; `--exploratory` explicitly labels conditional exploration. The overall March 29 end does **not** establish midnight, end-of-day, or a final trading earning cutoff.

## Data semantics

The [official GMX GraphQL documentation](https://docs.gmx.io/docs/api/graphql/) identifies the Arbitrum Subsquid endpoint. A live schema and March 2024 request confirmed TradeAction fields including `account`, `orderKey`, `orderType`, `eventName`, `timestamp`, `transactionHash` and `sizeDeltaUsd`. Live smoke receipts, when generated, record extraction scope and checksums; a successful day does not prove complete historical coverage.

The adapter filters **OrderExecuted**, not OrderCreated or OrderUpdated. It queries created actions by order key to distinguish older limit orders. Historical fees expressed in collateral-token units are not converted without token metadata and a validated historical pricing convention.

[GMX order source](https://github.com/gmx-io/gmx-synthetics/blob/main/contracts/order/Order.sol) defines the order types; [position event source](https://github.com/gmx-io/gmx-synthetics/blob/main/contracts/position/PositionEventUtils.sol) demonstrates protocol-account attribution. Current source is a discovery aid, not proof of the exact historical deployed ABI. This adapter consumes indexed historical semantics; an independent deployed-version/log replay remains a research validation gate.

Addresses are not people. An address using the protocol during the earning window is not automatically a confirmed reward recipient. Claim or payment dates cannot substitute for earning dates. Neither a high-frequency address nor one transaction matching a campaign threshold establishes bot, Sybil or task participation.
