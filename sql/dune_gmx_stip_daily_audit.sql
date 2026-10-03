-- DuneSQL companion. Source definitions verified; NOT executed or published.
-- Source pin and validation workflow: docs/dune.md.
-- Keep zero-size positions in this audit; the retention query excludes them.
WITH positions AS (
    SELECT block_date, block_time, tx_hash, "index" AS position_index,
           account, order_key, order_type, size_delta_usd, 'increase' AS action
    FROM gmx_v2_arbitrum.position_increase
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = 0xc8ee91a54287db53897056e12d9819156d3822fb
      AND (order_type IN ('MarketIncrease', 'LimitIncrease') OR order_type IS NULL)
    UNION ALL
    SELECT block_date, block_time, tx_hash, "index" AS position_index,
           account, order_key, order_type, size_delta_usd, 'decrease' AS action
    FROM gmx_v2_arbitrum.position_decrease
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = 0xc8ee91a54287db53897056e12d9819156d3822fb
      AND (order_type IN ('MarketDecrease', 'LimitDecrease', 'StopLossDecrease', 'Liquidation')
           OR order_type IS NULL)
), executions AS (
    SELECT block_date, tx_hash, "index" AS execution_index, "key" AS order_key,
           account, secondary_order_type
    FROM gmx_v2_arbitrum.order_executed
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = 0xc8ee91a54287db53897056e12d9819156d3822fb
), audited AS (
    SELECT p.*, e.execution_index, e.secondary_order_type
    FROM positions p LEFT JOIN executions e
      ON p.block_date = e.block_date AND p.tx_hash = e.tx_hash
     AND p.order_key = e.order_key AND p.account = e.account
)
SELECT block_date, action, order_type,
       count(*) AS joined_rows,
       count(DISTINCT ROW(tx_hash, position_index)) AS distinct_position_events,
       count(DISTINCT ROW(tx_hash, execution_index))
           FILTER (WHERE execution_index IS NOT NULL) AS distinct_execution_events,
       count_if(execution_index IS NULL) AS unmatched_position_rows,
       count_if(account IS NULL OR account = 0x0000000000000000000000000000000000000000)
           AS invalid_account_rows,
       count_if(size_delta_usd IS NULL) AS missing_size_rows,
       count_if(order_type IS NULL) AS missing_order_type_rows,
       count_if(size_delta_usd = 0) AS zero_size_rows,
       count_if(size_delta_usd > 0) AS positive_size_rows,
       count(DISTINCT account) FILTER (WHERE size_delta_usd > 0) AS positive_size_accounts,
       count_if(secondary_order_type = 1) AS adl_rows,
       count_if(secondary_order_type IS NULL) AS unknown_secondary_type_rows
FROM audited
GROUP BY block_date, action, order_type
ORDER BY block_date, action, order_type;
