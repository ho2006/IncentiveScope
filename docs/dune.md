# Dune cross-source SQL companion

The repository includes two DuneSQL queries grounded in official Spellbook model definitions. **Neither query has been run in Dune or published as a Dune query/dashboard.** Chrome was unavailable during this validation phase. Current deployed table availability, historical backfill completeness and agreement with the GMX Subsquid extraction therefore remain unverified. The committed research results come from the separately documented official GMX extraction.

## Verified schema sources

The source pin is `duneanalytics/spellbook@5f54fcf41b34b199c4c4ed1775059ab2d273f466`. Each downloaded model matched its Git blob hash; the [schema receipt](../data/evidence/dune/schema-receipt.json) records hashes and immutable URLs. The model configurations and final SELECTs establish these source-defined names and semantics:

| Source-defined table | Fields used | Meaning |
| --- | --- | --- |
| [gmx_v2_arbitrum.position_increase](https://github.com/duneanalytics/spellbook/blob/5f54fcf41b34b199c4c4ed1775059ab2d273f466/dbt_subprojects/hourly_spellbook/models/_project/gmx/event/arbitrum/gmx_v2_arbitrum_position_increase.sql) | `block_date`, `block_time`, `tx_hash`, `index`, `account`, `order_key`, `order_type`, `size_delta_usd`, `contract_address` | Position event; `account` is the protocol account, `order_type` is a string, and size delta is already divided by 10^30. |
| [gmx_v2_arbitrum.position_decrease](https://github.com/duneanalytics/spellbook/blob/5f54fcf41b34b199c4c4ed1775059ab2d273f466/dbt_subprojects/hourly_spellbook/models/_project/gmx/event/arbitrum/gmx_v2_arbitrum_position_decrease.sql) | Same join and size fields | Includes regular decreases and liquidation; the audit keeps these categories separate. |
| [gmx_v2_arbitrum.order_executed](https://github.com/duneanalytics/spellbook/blob/5f54fcf41b34b199c4c4ed1775059ab2d273f466/dbt_subprojects/hourly_spellbook/models/_project/gmx/event/arbitrum/gmx_v2_arbitrum_order_executed.sql) | `block_date`, `block_time`, `tx_hash`, `index`, `key`, `account`, `secondary_order_type`, `contract_address` | Successful execution event; secondary type is an integer, with 1 identifying ADL. Its log index differs from the position-event index. |
| [gmx_v2_arbitrum.order_created](https://github.com/duneanalytics/spellbook/blob/5f54fcf41b34b199c4c4ed1775059ab2d273f466/dbt_subprojects/hourly_spellbook/models/_project/gmx/event/arbitrum/gmx_v2_arbitrum_order_created.sql) | `block_date`, `block_time`, `key`, `account`, `contract_address` | Creation block time, used to check whether a returning opening/increase order was created after the earning cutoff. |

The query uses the historical GMX EventEmitter `0xc8ee91a54287db53897056e12d9819156d3822fb`, supported by the [independent event validation](event-validation.md). Protocol accounts use binary address literals in Dune, not transaction senders. Joining position events to execution events uses transaction hash, order key, date and account; it never assumes equal log indices or a fixed offset. The source code's declaration of a table does not establish that its deployed history is complete.

## Execute and validate when access is available

1. Run [the daily audit](../sql/dune_gmx_stip_daily_audit.sql) first. Verify the table/column names in Dune's actual catalog. Export the result with the query ID, execution ID, timestamp and source pin recorded.
2. Require zero unmatched positions and invalid accounts, check missing sizes, and require joined row counts to equal distinct position and execution counts. Any excess is a duplicate or join multiplicity to investigate. Check every UTC date in the extraction window, including dates with zero results, against independently established chain activity. A query returning no row cannot prove a genuine zero.
3. Reconcile positive-size increases per day, action/category counts and selected transaction/order keys with the GMX source. The raw GMX dataset uses the OrderExecuted log index; this SQL begins with position-event indices and exposes execution indices separately. Zero-size collateral changes stay in the audit and are excluded from retention.
4. Run [the retention query](../sql/dune_gmx_stip_retention.sql) only after coverage and grain checks pass. It keeps all qualifying campaign accounts in the denominator, including accounts with no return. Confirm `N`, each numerator and the creation-time missingness against the Python/DuckDB report; investigate every discrepancy rather than selecting the preferred source.
5. Publish a Dune link and mark execution verified only after saving that evidence. Until then, treat these SQL files as reviewable, unexecuted companions.

The UTC earning interval is `[2023-11-15 00:00:01, 2024-03-27 00:00:00)`. R30 uses `[2024-04-19, 2024-04-26)`, cumulative 30 uses `[2024-03-27, 2024-04-26)`, and R60 uses `[2024-05-19, 2024-05-26)`. Sustained R30 requires two distinct UTC dates. Strict R30 is withheld if any qualifying R30 opening/increase event lacks one plausible creation event. R60 should be withheld externally if coverage checks fail, even if the SQL returns a number.

This companion computes address retention only. It makes no Dune-derived fee calculation, recipient-to-trader attribution or claim of incentive causality. Later STIP Bridge rewards and GMX V1 are outside its scope.

## ADL comparison limit

The historical [AdlUtils](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/adl/AdlUtils.sol) creates an ADL reduction as `MarketDecrease`, and [AdlHandler](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/exchange/AdlHandler.sol) passes `SecondaryOrderType.Adl` during execution. Filtering order type alone cannot distinguish it from a regular market decrease. The Subsquid TradeAction schema inspected for the real extraction does not expose this secondary type. The real report therefore withholds its voluntary30 metric and labels its broader opening-or-decrease sensitivity separately; the primary opening/increase R30 definition is unaffected.

The Dune source model exposes `secondary_order_type`, so the daily audit reports ADL and unknown-secondary-type rows explicitly. A future voluntary30 cross-source comparison must inspect this field, exclude ADL and liquidation, establish missingness and reconcile the joined events. This potential distinction has not yet been tested against deployed Dune results.
