-- All timestamps are UTC. One normalized row represents one execution event.
CREATE TEMP VIEW actions AS
SELECT *,
       success AND action = 'increase' AND size_delta_usd > 0 AS is_increase,
       success AND action IN ('increase', 'decrease') AND size_delta_usd > 0 AS is_voluntary
FROM trades;

-- Keep the denominator fixed, including addresses that never return.
CREATE TEMP TABLE cohort AS
WITH first_seen AS (
    SELECT account, min(timestamp) AS first_trade
    FROM actions WHERE is_voluntary GROUP BY account
), entered AS (
    SELECT account, min(timestamp) AS first_qualifying,
           sum(size_delta_usd) AS campaign_volume_usd
    FROM actions, parameters
    WHERE is_increase AND timestamp >= start_time AND timestamp < end_time
    GROUP BY account
)
SELECT entered.*, first_trade, date_trunc('week', first_qualifying)::DATE AS entry_week
FROM entered JOIN first_seen USING (account);

CREATE TEMP TABLE outcomes AS
SELECT c.*,
       count(*) FILTER (WHERE a.is_increase AND a.timestamp >= p.anchor + INTERVAL '23 days'
                        AND a.timestamp < p.anchor + INTERVAL '30 days') > 0 AS r30,
       count(*) FILTER (WHERE a.is_increase AND a.timestamp >= p.anchor
                        AND a.timestamp < p.anchor + INTERVAL '30 days') > 0 AS cumulative30,
       count(DISTINCT a.timestamp::DATE) FILTER (
           WHERE a.is_increase AND a.timestamp >= p.anchor + INTERVAL '23 days'
           AND a.timestamp < p.anchor + INTERVAL '30 days') >= 2 AS sustained30,
       count(*) FILTER (WHERE a.is_voluntary AND a.timestamp >= p.anchor + INTERVAL '23 days'
                        AND a.timestamp < p.anchor + INTERVAL '30 days') > 0 AS voluntary30,
       count(*) FILTER (WHERE a.is_increase AND a.timestamp >= p.anchor + INTERVAL '23 days'
                        AND a.timestamp < p.anchor + INTERVAL '30 days'
                        AND a.order_created_at >= p.end_time) > 0 AS strict_r30,
       count(*) FILTER (WHERE a.is_increase AND a.timestamp >= p.anchor + INTERVAL '23 days'
                        AND a.timestamp < p.anchor + INTERVAL '30 days'
                        AND a.order_created_at IS NULL) AS strict_missing,
       count(*) FILTER (WHERE a.is_increase AND a.timestamp >= p.anchor + INTERVAL '53 days'
                        AND a.timestamp < p.anchor + INTERVAL '60 days') > 0 AS r60
FROM cohort c CROSS JOIN parameters p LEFT JOIN actions a USING (account)
GROUP BY ALL;

CREATE TEMP TABLE wallet_daily AS
SELECT account, timestamp::DATE AS day,
       count(*) FILTER (WHERE is_increase) AS increases,
       count(*) FILTER (WHERE is_voluntary) AS voluntary_trades,
       sum(position_fee_usd) FILTER (WHERE is_increase) AS position_fee_usd,
       count(*) FILTER (WHERE is_increase AND position_fee_usd IS NULL) AS missing_fees
FROM actions GROUP BY account, day;
