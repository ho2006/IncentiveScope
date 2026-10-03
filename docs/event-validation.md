# Independent receipt checks: GMX V2 / Arbitrum

Five executions from the 2024-03-29 smoke extract passed a comparison with transaction receipts obtained directly from the [official Arbitrum One RPC](https://arb1.arbitrum.io/rpc). The checked fields are protocol account, order key, market, order type, exact USD size, execution log index and block timestamp. Four indexed fee fields also matched the corresponding `PositionFeesCollected` logs. This is a small, deliberately selected sample, **not** validation of every row or historical completeness.

Evidence was retrieved on **2026-10-03 UTC**. The input CSV contained 5,902 rows and had SHA-256 `e65ede1e6453131180c267aeae352367ac61f7888f4edae2791ca78bf63809a9`. This identifies the original smoke extract before any later fee enrichment.

## Evidence and selection

- [Raw selected receipt logs, decoded fields and comparisons](../data/evidence/event-validation/rpc-responses.json): receipt headers, block timestamps, original indexed records and normalized rows, and three relevant event logs per transaction. Unrelated receipt logs are omitted; the file records a canonical hash of each complete receipt.
- [Independent fee-field query response](../data/evidence/event-validation/indexed-fees.json): the five original `TradeAction` IDs queried at the [GMX Subsquid endpoint](https://gmx.squids.live/gmx-synthetics-arbitrum:prod/api/graphql).
- RPC methods: `eth_getTransactionReceipt(transactionHash)` and `eth_getBlockByHash(blockHash, false)`. The RPC is listed in [Arbitrum's official documentation](https://docs.arbitrum.io/arbitrum-bridge/quickstart).

The sample is the lexicographically smallest `TradeAction.id` for each of order types **2, 3, 4, 6 and 7** in the smoke extract. It covers market increase, limit increase, market decrease, stop-loss decrease and liquidation semantics. Type 5 and zero-size collateral changes were not sampled. It is not a random sample and does not estimate an error rate.

| Transaction | Order type | Block | Position log | Execution log / indexed suffix | Exact size USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| [0x0041e159…](https://arbiscan.io/tx/0x0041e15909edfabfbf7a2cf9b9429bc336f792d241ef212502a35c80b4f6b89f#eventlog) | 2 | 195446162 | 64 | 65 | 26.8993650612074504 |
| [0x0258a629…](https://arbiscan.io/tx/0x0258a629532039d2cd8ee064363906b84942a434e56113aa459bd10edbb8e0b6#eventlog) | 3 | 195493156 | 41 | 42 | 507.911677757964158675 |
| [0x00462251…](https://arbiscan.io/tx/0x00462251c947bab60533869ccb0de0f16d23b8923d928a2a33b03dd6547ccc0b#eventlog) | 4 | 195257641 | 31 | 33 | 45.384417959008752 |
| [0x01ab6175…](https://arbiscan.io/tx/0x01ab6175c06f7eafd9cb153e3ea3372db2a15bffbf7b1774e963ec4ee5a7a428#eventlog) | 6 | 195367634 | 75 | 77 | 101169.728810352 |
| [0x01fe78b2…](https://arbiscan.io/tx/0x01fe78b2969bd456f8824e6a39e7500d7e9438f0a7bbd8dc7fc717864d7dcb12#eventlog) | 7 | 195466899 | 77 | 79 | 724.40859557190765696 |

Explorer links are navigation aids; the actual checks used RPC responses, not explorer-decoded labels.

## Event semantics checked

The receipts emit from `0xc8ee91a54287db53897056e12d9819156d3822fb`. This agrees with the [official EventEmitter deployment inventory pinned at commit a85ea3491c19c93bb4b5a002d9b358fb769b7849](https://github.com/gmx-io/gmx-synthetics/blob/a85ea3491c19c93bb4b5a002d9b358fb769b7849/deployments/arbitrum/EventEmitter.json). That inventory is a current discovery reference; it is not a historical bytecode attestation.

For historical interpretation, the reference source is the last repository commit before 2024-03-29 UTC, **ff4b95bc0961586bdf704bcb493b12f6d225ec12** (2024-03-28 16:05:39 UTC): [EventEmitter](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/event/EventEmitter.sol), [EventUtils](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/event/EventUtils.sol), [OrderEventUtils](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/order/OrderEventUtils.sol), [PositionEventUtils](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/position/PositionEventUtils.sol), and [Order enum](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/order/Order.sol). Selecting a historical source commit does not prove which full code version was deployed.

The raw log data was decoded using ABI dynamic offsets into the named address, unsigned-integer and bytes32 scalar-item groups. Field names were read from the bytes; array positions were not assumed to stay constant across versions. The actual log contents establish the following for all five samples:

1. The receipt succeeded and the block timestamp equals the indexed timestamp.
2. The indexed ID suffix is the **block-global `OrderExecuted` log index**. It is not the position log index or a transaction-local event number.
3. `OrderExecuted` contains account and order key. Its related `PositionIncrease` / `PositionDecrease` log supplies account, market, order type and executed `sizeDeltaUsd`; both logs were joined by the same order key.
4. Raw executed size equals the indexed integer exactly, and dividing by `10^30` equals the normalized CSV decimal exactly.
5. Receipt `from` differs from protocol `account` in **all five samples**. Counting transaction senders would attribute these executions incorrectly.

The related position log precedes `OrderExecuted` by one or two log indices in these samples. Consumers must join by order key, not assume a fixed offset. The enriched indexed record should not be described as one raw Solidity event containing every column.

## Position fee USD: checked definition

The same receipts contain `PositionFeesCollected` events keyed by the same order key. The indexed `positionFeeAmount`, `traderDiscountAmount`, `collateralTokenPriceMin` and `collateralTokenPriceMax` matched the four corresponding on-chain integer fields for all five transactions, including one nonzero referral discount.

The [pinned PositionPricingUtils source](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/pricing/PositionPricingUtils.sol) calculates a gross position fee in collateral-token atomic units and subtracts the trader discount separately when forming trading costs. `positionFeeAmount` therefore has **not** already had `traderDiscountAmount` deducted. The [pinned Precision source](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/utils/Precision.sol) uses `10^30` fixed-point precision.

For the metric **net position trading fee, after referral discount, before external rebates**:

```text
net_position_fee_usd =
    (positionFeeAmount - traderDiscountAmount)
    * collateralTokenPriceMin / 10^30
```

The collateral price is already scaled for token atomic units: amount × this price yields USD with 30 decimal places. No additional token-decimal division is needed. The formula follows the historical contract's minimum-price convention and the emitted price; it does not require an external historical price feed. Integer-to-decimal arithmetic must retain full precision until display or the documented analytical storage rounding.

The type-6 transaction provides a nonzero-discount check:

```text
positionFeeAmount       = 50579168
traderDiscountAmount    = 2528958
collateralTokenPriceMin = 1000112610000000000000000
gross position fee USD  = 50.58486372010848
net position fee USD    = 48.0556209341481
```

This metric excludes borrowing, funding, UI fees, gas, and subsequent STIP or other off-chain/claimable rebates. It is not protocol revenue: affiliate and pool/receiver allocation are separate. An absent fee/discount/price must remain missing; it must not become zero. Require integer nonnegative amounts, a positive price and discount ≤ gross fee before calculating it.

All five sampled fees use USDC collateral (`0xaf88d065e77c8cc2239327c5edb3a432268e5831`). The dimensional rule is established by the contract formula, but other collateral decimals and other deployment periods were not independently sampled here.

## Remaining limits and reproduction

These checks do not establish STIP earning boundaries, payment eligibility, unique human counts, the completeness of 5,902 rows, the full-history indexer's absence of omissions, or exact historical deployed bytecode. `OrderCreated` times were not separately replayed from creation receipts. Liquidation versus ADL subcategories were not audited. No population-wide independent validation should be claimed from this sample.

To repeat the network check, send each stored transaction hash to the RPC using `eth_getTransactionReceipt`, then request its block using `eth_getBlockByHash`. Decode the named fields at the saved EventEmitter logs, join position/fee and execution records by order key, and compare to the saved indexed/normalized values. To repeat the indexed fee query, use the five full `indexed.id` values from the evidence file:

```graphql
query($ids: [String!]!) {
  tradeActions(where: {id_in: $ids}) {
    id
    collateralTokenPriceMin
    collateralTokenPriceMax
    positionFeeAmount
    traderDiscountAmount
  }
}
```

The saved raw logs allow inspection independently of later indexer changes. The `checks_passed` fields record this run's successful assertions; they are not substitutes for decoding and rechecking the retained bytes.
