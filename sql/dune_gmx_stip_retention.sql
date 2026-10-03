-- DuneSQL companion. Source definitions verified; NOT executed or published.
-- Run daily audit first, verify all dates/join grain and reconcile to Subsquid.
-- UTC integer-second earning interval: timestamp > launch guard, end excluded.
WITH executions AS (
    SELECT block_date, tx_hash, "key" AS order_key, account
    FROM gmx_v2_arbitrum.order_executed
    WHERE block_date >= DATE '2023-09-20' AND block_date < DATE '2024-05-29'
      AND block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
), increases AS (
    SELECT p.block_date, p.block_time, p.tx_hash, p."index" AS position_index,
           p.account, p.order_key
    FROM gmx_v2_arbitrum.position_increase p
    WHERE p.block_date >= DATE '2023-09-20' AND p.block_date < DATE '2024-05-29'
      AND p.block_time >= TIMESTAMP '2023-09-20 00:00:00'
      AND p.block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND p.contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
      AND p.order_type IN ('MarketIncrease', 'LimitIncrease')
      AND p.size_delta_usd > 0
      AND p.account IS NOT NULL
      AND p.account <> from_hex('0000000000000000000000000000000000000000')
      AND EXISTS (
          SELECT 1 FROM executions e
          WHERE e.block_date = p.block_date AND e.tx_hash = p.tx_hash
            AND e.order_key = p.order_key AND e.account = p.account
      )
), cohort AS (
    SELECT DISTINCT account FROM increases
    WHERE block_time >= TIMESTAMP '2023-11-15 00:00:01'
      AND block_time < TIMESTAMP '2024-03-27 00:00:00'
), creations AS (
    -- Look up relevant keys across pre-cutoff history, including before Sep 20.
    -- Group by key alone: conflicting accounts must not hide a duplicated key.
    SELECT "key" AS order_key, min(account) AS account, min(block_time) AS created_at,
           count(*) AS creation_rows
    FROM gmx_v2_arbitrum.order_created
    WHERE block_date < DATE '2024-05-29'
      AND block_time < TIMESTAMP '2024-05-29 00:00:00'
      AND contract_address = from_hex('c8ee91a54287db53897056e12d9819156d3822fb')
      AND "key" IN (SELECT order_key FROM increases)
    GROUP BY "key"
), outcomes AS (
    SELECT c.account,
           count_if(i.block_time >= TIMESTAMP '2024-04-19 00:00:00'
                    AND i.block_time < TIMESTAMP '2024-04-26 00:00:00') > 0 AS r30,
           count_if(i.block_time >= TIMESTAMP '2024-03-27 00:00:00'
                    AND i.block_time < TIMESTAMP '2024-04-26 00:00:00') > 0 AS cumulative30,
           count(DISTINCT i.block_date) FILTER (
               WHERE i.block_time >= TIMESTAMP '2024-04-19 00:00:00'
                 AND i.block_time < TIMESTAMP '2024-04-26 00:00:00') >= 2 AS sustained30,
           count_if(i.block_time >= TIMESTAMP '2024-04-19 00:00:00'
                    AND i.block_time < TIMESTAMP '2024-04-26 00:00:00'
                    AND o.creation_rows = 1
                    AND o.account = i.account
                    AND o.created_at >= TIMESTAMP '2024-03-27 00:00:00'
                    AND o.created_at <= i.block_time) > 0 AS strict_r30,
           count_if(i.block_time >= TIMESTAMP '2024-04-19 00:00:00'
                    AND i.block_time < TIMESTAMP '2024-04-26 00:00:00'
                    AND (o.created_at IS NULL OR o.creation_rows <> 1
                         OR o.account IS NULL OR o.account <> i.account
                         OR o.created_at > i.block_time)) AS strict_unknown_events,
           count_if(i.block_time >= TIMESTAMP '2024-05-19 00:00:00'
                    AND i.block_time < TIMESTAMP '2024-05-26 00:00:00') > 0 AS r60
    FROM cohort c LEFT JOIN increases i ON i.account = c.account
    LEFT JOIN creations o ON o.order_key = i.order_key
    GROUP BY c.account
), totals AS (
    SELECT count(*) AS cohort_n, count_if(r30) AS r30_n,
           count_if(cumulative30) AS cumulative30_n,
           count_if(sustained30) AS sustained30_n, count_if(strict_r30) AS strict_r30_n,
           coalesce(sum(strict_unknown_events), 0) AS strict_unknown_events, count_if(r60) AS r60_n
    FROM outcomes
), metrics AS (
    SELECT 'r30' AS metric, r30_n AS numerator, cohort_n AS denominator, strict_unknown_events FROM totals
    UNION ALL
    SELECT 'cumulative30', cumulative30_n, cohort_n, strict_unknown_events FROM totals
    UNION ALL
    SELECT 'sustained30', sustained30_n, cohort_n, strict_unknown_events FROM totals
    UNION ALL
    SELECT 'strict_r30', CASE WHEN strict_unknown_events = 0 THEN strict_r30_n END,
           cohort_n, strict_unknown_events FROM totals
    UNION ALL
    SELECT 'r60', r60_n, cohort_n, strict_unknown_events FROM totals
)
SELECT metric, numerator, denominator,
       CAST(numerator AS DOUBLE) / NULLIF(denominator, 0) AS rate, strict_unknown_events
FROM metrics ORDER BY metric;
