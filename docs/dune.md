# Dune cross-source SQL companion

The repository includes two DuneSQL queries grounded in official Spellbook model definitions and a small schema probe. **None has been run in Dune or published as a Dune query/dashboard.** On October 3, 2026, Chrome reached the signed-in query editor and the probe was entered, but Run and Create were disabled. The session showed an ended trial; the viewed [pricing page](https://dune.com/pricing) listed view/copy access for the current Free plan and query execution for Analyst. No subscription or payment action was performed. The [attempt record](../data/evidence/dune/execution-status.json) explicitly has no query or execution ID.

Current deployed table availability, historical backfill completeness and agreement with the GMX Subsquid extraction therefore remain unverified. The committed research results come from the separately documented official GMX extraction. Local SQL fixtures test query logic on DuckDB; they do not establish Dune execution. See the [SQL validation contract](dune-sql-design.md) for the exact grain, quality counters and creation-time rules.

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

1. Restore query execution access, then run [the one-day schema probe](../sql/dune_gmx_schema_probe.sql). Confirm the table/column names against Dune's actual catalog; successful compilation is separate from complete history.
2. Run [the daily audit](../sql/dune_gmx_stip_daily_audit.sql). Export all 252 rows with the actual query ID, execution ID and timezone-qualified execution timestamp recorded. The explicit date grid includes zero dates; zeros alone do not establish chain inactivity.
3. Require zero duplicates, join multiplication, unmatched perpetual positions/executions, unclassified executions and invalid event fields. Unmatched swaps are out of scope only when one matching-account creation identifies a known swap type. Compare daily categories and accounts with [the independent GMX counts](../data/evidence/history-quality/daily.csv). Position and execution log indices are different identities; they must never be joined by a fixed offset. Zero-size collateral changes remain in the audit and are excluded from retention.
4. Run [the retention query](../sql/dune_gmx_stip_retention.sql) after investigating audit failures. It keeps nonreturners in the fixed denominator. Export exactly five rows with columns `metric,numerator,denominator,rate,strict_unknown_events`. Creation lookups include source history before the extraction start; missing, duplicated, conflicting-account or future creation events withhold strict R30.
5. Copy [the provenance template](../configs/dune-provenance.example.json), replace every placeholder with the actual execution metadata and SHA-256 values, then run the reconciliation command below. Investigate differences before claiming agreement. Selected transaction/order-key checks and an actual Dune execution link should accompany any published comparison.

```powershell
# After obtaining complete, real Dune exports and their execution metadata:
New-Item -ItemType Directory -Force data/raw/dune | Out-Null
Copy-Item configs/dune-provenance.example.json data/raw/dune/provenance.json
Get-FileHash data/raw/dune/daily.csv, data/raw/dune/retention.csv, sql/dune_gmx_stip_daily_audit.sql, sql/dune_gmx_stip_retention.sql -Algorithm SHA256
# Fill provenance.json with these hashes, actual IDs, timestamps and completeness.
& .\.venv\Scripts\python.exe scripts/reconcile_dune.py --daily data/raw/dune/daily.csv --retention data/raw/dune/retention.csv --provenance data/raw/dune/provenance.json --output data/evidence/dune/reconciliation.json
```

The template deliberately contains null IDs/hashes and `complete: false`, so it cannot pass validation. The script compares every UTC date, seven daily counts, source-grain identities, error counters and five fixed-cohort metrics. It rejects duplicate grains, missing dates/values, incomplete exports, wrong hashes and inconsistent rates. Its receipt records the supplied query URLs, execution IDs and local input hashes. It does not independently authenticate supplied execution metadata or prove full-chain completeness.

`validated: true` requires agreement for all five metrics on real inputs with no quality failures. If only strict R30 is withheld, `opening_retention_validated` can separately describe agreement for R30, cumulative30, sustained30 and R60; overall validation stays false and the command exits with code 2. Synthetic fixtures always remain unvalidated. A saved execution alone does not establish source agreement; the dashboard's current status stays explicitly unexecuted until actual evidence is obtained and reviewed.

The UTC earning interval is `[2023-11-15 00:00:01, 2024-03-27 00:00:00)`. R30 uses `[2024-04-19, 2024-04-26)`, cumulative 30 uses `[2024-03-27, 2024-04-26)`, and R60 uses `[2024-05-19, 2024-05-26)`. Sustained R30 requires two distinct UTC dates. Strict R30 is withheld if any qualifying R30 opening/increase event lacks one plausible creation event. R60 should be withheld externally if coverage checks fail, even if the SQL returns a number.

This companion computes address retention only. It makes no Dune-derived fee calculation, recipient-to-trader attribution or claim of incentive causality. Later STIP Bridge rewards and GMX V1 are outside its scope.

## ADL comparison limit

The historical [AdlUtils](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/adl/AdlUtils.sol) creates an ADL reduction as `MarketDecrease`, and [AdlHandler](https://github.com/gmx-io/gmx-synthetics/blob/ff4b95bc0961586bdf704bcb493b12f6d225ec12/contracts/exchange/AdlHandler.sol) passes `SecondaryOrderType.Adl` during execution. Filtering order type alone cannot distinguish it from a regular market decrease. The Subsquid TradeAction schema inspected for the real extraction does not expose this secondary type. The real report therefore withholds its voluntary30 metric and labels its broader opening-or-decrease sensitivity separately; the primary opening/increase R30 definition is unaffected.

The Dune source model exposes `secondary_order_type`, so the daily audit reports ADL and unknown-secondary-type rows explicitly. A future voluntary30 cross-source comparison must inspect this field, exclude ADL and liquidation, establish missingness and reconcile the joined events. This potential distinction has not yet been tested against deployed Dune results.
