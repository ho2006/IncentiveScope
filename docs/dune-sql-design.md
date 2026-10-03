# Dune SQL validation contract

These are reviewed SQL companions, not executed Dune results. The [schema receipt](../data/evidence/dune/schema-receipt.json) pins the official Spellbook definitions and retains their immutable source URLs. Actual deployment and historical coverage still require an exported Dune execution.

## Daily audit

[The daily query](../sql/dune_gmx_stip_daily_audit.sql) emits 252 UTC dates from September 20, 2023 through May 28, 2024. A date with no source rows is explicit. A zero is an observation from this query, not evidence that no chain activity occurred; compare every date with the independent [GMX daily extraction](../data/evidence/history-quality/daily.csv).

`rows`, `accounts`, `increase`, `decrease`, `liquidation`, `collateral` and `zero_size` follow the normalized GMX extraction. Only matched execution/position events of order types 2–7 are comparable. Positive-size regular increases/decreases retain their action; zero-size changes become collateral except that a liquidation remains a liquidation. `zero_size` separately includes every zero-size event.

Position and execution log indices are distinct event identities. The full outer join uses UTC date, transaction hash, order key and account; it detects unmatched positions and unmatched executions independently. Raw event duplicate counts are calculated before joining. `position_join_extra_rows` and `execution_join_extra_rows` expose multiplication caused by a nonunique join.

The official [OrderExecuted model](https://github.com/duneanalytics/spellbook/blob/5f54fcf41b34b199c4c4ed1775059ab2d273f466/dbt_subprojects/hourly_spellbook/models/_project/gmx/event/arbitrum/gmx_v2_arbitrum_order_executed.sql) does not expose primary order type and also contains swaps. A uniquely attributed creation event classifies unmatched executions: perpetual types 2–7 are errors, known MarketSwap/LimitSwap executions are out of scope, and unresolved or other types stay unclassified. Unclassified events require investigation; they are never assumed to be swaps.

After the error counters are zero, these grain identities must hold on every date:

```text
position_rows = rows
execution_rows = rows + out_of_scope_execution_rows
rows = increase + decrease + liquidation + collateral
position_join_extra_rows = execution_join_extra_rows = 0
```

Duplicate events, unmatched perpetuals, unclassified executions, unexpected order types, invalid accounts and missing/negative sizes invalidate daily reconciliation. ADL and unknown secondary types are disclosed separately and do not change opening/increase retention. These queries do not calculate position fees.

## Retention and creation coverage

[The retention query](../sql/dune_gmx_stip_retention.sql) exports one row for each of `r30`, `cumulative30`, `sustained30`, `strict_r30` and `r60`. Columns are `metric`, `numerator`, `denominator`, `rate`, `strict_unknown_events`. Distinct names avoid SQL's case-insensitive resolution of an ambiguous `n`/`N` pair. All five rows preserve the campaign denominator, including accounts with no later activity. Window boundaries match [the research definitions](dune.md).

Creation lookups restrict order keys to relevant executions/increases and scan source history before the May 29 extraction cutoff, without imposing a September 20 lower bound. A pending order created earlier than the extraction window can therefore be found if Dune contains that history. Creation rows are grouped by order key alone: a duplicated key across accounts cannot be hidden by grouping by account.

For strict R30, each relevant returning increase needs exactly one creation row with the same account, a timestamp at or after the campaign cutoff and no later than execution. Missing, duplicated, conflicting-account or future creations withhold the entire strict numerator/rate. This withholding does not invalidate the four opening-based metrics. It does not establish that all creation history is complete: missing history remains unknown.

`tests/test_dune_sql.py` runs the query logic on DuckDB fixtures for explicit zero dates, legitimate swaps, zero-size liquidation, duplicated positions, execution-only perpetuals, pre-window creations and missing/conflicting creation keys. Only the date `sequence` function is adapted to DuckDB. This check does not validate the Dune compiler, live tables, backfill, or real-source agreement.
