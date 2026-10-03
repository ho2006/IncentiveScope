-- DuneSQL companion. Source definitions verified; NOT executed or published.
-- Source pin and execution receipts: docs/dune.md. One row per UTC date.
-- Keep zero-size positions; retention excludes collateral-only changes.
WITH dates AS (
    SELECT day FROM UNNEST(sequence(DATE '2023-09-20', DATE '2024-05-28')) AS d(day)
), positions AS (
    SELECT block_date, block_time, tx_hash, "index" AS position_index,
           account, order_key, order_type, size_delta_usd, 'increase' AS source_action
    FROM gmx_v2_arbitrum.position_increase
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
    UNION ALL
    SELECT block_date, block_time, tx_hash, "index" AS position_index,
           account, order_key, order_type, size_delta_usd, 'decrease' AS source_action
    FROM gmx_v2_arbitrum.position_decrease
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
), executions AS (
    SELECT block_date, block_time, tx_hash, "index" AS execution_index,
           "key" AS order_key, account, secondary_order_type
    FROM gmx_v2_arbitrum.order_executed
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
), creations AS (
    -- Lookup keys across pre-cutoff source history, including before Sep 20.
    -- A duplicated key or conflicting account never becomes a valid creation.
    SELECT "key" AS order_key, min(account) AS account, min(block_time) AS created_at,
           count(*) AS creation_rows, max(order_type) AS order_type
    FROM gmx_v2_arbitrum.order_created
    WHERE block_date < DATE '2024-05-29'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
      AND "key" IN (SELECT order_key FROM executions)
    GROUP BY "key"
), position_daily AS (
    SELECT block_date, count(*) AS position_rows,
           count(*) - count(DISTINCT ROW(tx_hash, position_index)) AS duplicate_position_events
    FROM positions GROUP BY block_date
), execution_daily AS (
    SELECT block_date, count(*) AS execution_rows,
           count(*) - count(DISTINCT ROW(tx_hash, execution_index)) AS duplicate_execution_events
    FROM executions GROUP BY block_date
), joined AS (
    SELECT coalesce(p.block_date, e.block_date) AS block_date,
           p.position_index, e.execution_index, coalesce(p.account, e.account) AS account,
           coalesce(p.block_time, e.block_time) AS block_time,
           p.order_type, p.source_action, p.size_delta_usd, e.secondary_order_type,
           o.created_at, o.creation_rows, o.account AS creation_account,
           o.order_type AS created_order_type,
           p.position_index IS NOT NULL AND e.execution_index IS NOT NULL
             AND ((p.source_action = 'increase' AND p.order_type IN ('MarketIncrease', 'LimitIncrease'))
               OR (p.source_action = 'decrease' AND p.order_type IN
                   ('MarketDecrease', 'LimitDecrease', 'StopLossDecrease', 'Liquidation'))) AS comparable
    FROM positions p FULL OUTER JOIN executions e
      ON p.block_date = e.block_date AND p.tx_hash = e.tx_hash
     AND p.order_key = e.order_key AND p.account = e.account
    LEFT JOIN creations o ON o.order_key = coalesce(p.order_key, e.order_key)
), daily AS (
    SELECT block_date,
           count_if(comparable) AS rows,
           count(DISTINCT account) FILTER (WHERE comparable) AS accounts,
           count_if(comparable AND order_type IN ('MarketIncrease', 'LimitIncrease')
                    AND size_delta_usd > 0) AS increase,
           count_if(comparable AND order_type IN ('MarketDecrease', 'LimitDecrease', 'StopLossDecrease')
                    AND size_delta_usd > 0) AS decrease,
           count_if(comparable AND order_type = 'Liquidation') AS liquidation,
           count_if(comparable AND order_type <> 'Liquidation' AND size_delta_usd = 0) AS collateral,
           count_if(comparable AND size_delta_usd = 0) AS zero_size,
           count_if(position_index IS NOT NULL) AS joined_position_rows,
           count_if(execution_index IS NOT NULL) AS joined_execution_rows,
           count_if(position_index IS NOT NULL AND execution_index IS NULL) AS unmatched_position_rows,
           count_if(position_index IS NULL AND execution_index IS NOT NULL
                    AND creation_rows = 1 AND creation_account = account
                    AND created_order_type IN ('MarketIncrease', 'LimitIncrease', 'MarketDecrease',
                                               'LimitDecrease', 'StopLossDecrease', 'Liquidation'))
             AS unmatched_execution_rows,
           count_if(position_index IS NULL AND execution_index IS NOT NULL
                    AND creation_rows = 1 AND creation_account = account
                    AND created_order_type IN ('MarketSwap', 'LimitSwap')) AS out_of_scope_execution_rows,
           count_if(position_index IS NULL AND execution_index IS NOT NULL
                    AND NOT coalesce(creation_rows = 1 AND creation_account = account
                        AND created_order_type IN ('MarketIncrease', 'LimitIncrease', 'MarketDecrease',
                            'LimitDecrease', 'StopLossDecrease', 'Liquidation', 'MarketSwap', 'LimitSwap'), false))
             AS unclassified_execution_rows,
           count_if(position_index IS NOT NULL AND order_type IS NOT NULL
                    AND NOT ((source_action = 'increase' AND order_type IN ('MarketIncrease', 'LimitIncrease'))
                      OR (source_action = 'decrease' AND order_type IN
                          ('MarketDecrease', 'LimitDecrease', 'StopLossDecrease', 'Liquidation'))))
             AS unexpected_order_type_rows,
           count_if(account IS NULL OR account = from_hex('0000000000000000000000000000000000000000'))
             AS invalid_account_rows,
           count_if(position_index IS NOT NULL AND size_delta_usd IS NULL) AS missing_size_rows,
           count_if(position_index IS NOT NULL AND size_delta_usd < 0) AS negative_size_rows,
           count_if(position_index IS NOT NULL AND order_type IS NULL) AS missing_order_type_rows,
           count_if(comparable AND secondary_order_type = 1) AS adl_rows,
           count_if(comparable AND secondary_order_type IS NULL) AS unknown_secondary_type_rows,
           count_if(comparable AND created_at IS NULL) AS created_missing,
           count_if(comparable AND creation_rows <> 1) AS creation_nonunique,
           count_if(comparable AND creation_rows = 1 AND creation_account <> account) AS creation_account_mismatch,
           count_if(comparable AND created_at > block_time) AS creation_after_execution
    FROM joined GROUP BY block_date
)
SELECT d.day,
       coalesce(a.rows, 0) AS rows, coalesce(a.accounts, 0) AS accounts,
       coalesce(a.increase, 0) AS increase, coalesce(a.decrease, 0) AS decrease,
       coalesce(a.liquidation, 0) AS liquidation, coalesce(a.collateral, 0) AS collateral,
       coalesce(a.zero_size, 0) AS zero_size,
       coalesce(p.position_rows, 0) AS position_rows,
       coalesce(p.duplicate_position_events, 0) AS duplicate_position_events,
       coalesce(e.execution_rows, 0) AS execution_rows,
       coalesce(e.duplicate_execution_events, 0) AS duplicate_execution_events,
       coalesce(a.joined_position_rows, 0) - coalesce(p.position_rows, 0) AS position_join_extra_rows,
       coalesce(a.joined_execution_rows, 0) - coalesce(e.execution_rows, 0) AS execution_join_extra_rows,
       coalesce(a.unmatched_position_rows, 0) AS unmatched_position_rows,
       coalesce(a.unmatched_execution_rows, 0) AS unmatched_execution_rows,
       coalesce(a.out_of_scope_execution_rows, 0) AS out_of_scope_execution_rows,
       coalesce(a.unclassified_execution_rows, 0) AS unclassified_execution_rows,
       coalesce(a.unexpected_order_type_rows, 0) AS unexpected_order_type_rows,
       coalesce(a.invalid_account_rows, 0) AS invalid_account_rows,
       coalesce(a.missing_size_rows, 0) AS missing_size_rows,
       coalesce(a.negative_size_rows, 0) AS negative_size_rows,
       coalesce(a.missing_order_type_rows, 0) AS missing_order_type_rows,
       coalesce(a.adl_rows, 0) AS adl_rows,
       coalesce(a.unknown_secondary_type_rows, 0) AS unknown_secondary_type_rows,
       coalesce(a.created_missing, 0) AS created_missing,
       coalesce(a.creation_nonunique, 0) AS creation_nonunique,
       coalesce(a.creation_account_mismatch, 0) AS creation_account_mismatch,
       coalesce(a.creation_after_execution, 0) AS creation_after_execution
FROM dates d LEFT JOIN daily a ON a.block_date = d.day
LEFT JOIN position_daily p ON p.block_date = d.day
LEFT JOIN execution_daily e ON e.block_date = d.day
ORDER BY d.day;
