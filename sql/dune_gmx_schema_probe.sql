-- IncentiveScope: one-day schema probe
SELECT block_date, block_time, account, order_key, order_type, size_delta_usd
FROM gmx_v2_arbitrum.position_increase
WHERE block_date = DATE '2024-03-29'
  AND contract_address = 0xc8ee91a54287db53897056e12d9819156d3822fb
LIMIT 5;
