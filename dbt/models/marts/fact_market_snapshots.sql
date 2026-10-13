{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='price_date'
) }}

-- Fact table: the numbers. One row per coin per day.
-- Grain (say it out loud before writing): ONE COIN'S NUMBERS ON ONE DAY.
--
-- Incremental by design: the first run (or --full-refresh) builds everything;
-- nightly re-runs reprocess only the last 3 days (a lookback window that
-- absorbs late corrections) and delete+insert REPLACES those dates
-- wholesale — duplicates are impossible by construction, and the uniqueness
-- test would still catch any slip.

select
    coin_id,
    price_date,
    price,
    market_cap,
    total_volume
from {{ ref('stg_market_chart') }}
where price_date is not null

{% if is_incremental() %}
  and price_date >= (
      select dateadd('day', -3, max(price_date)) from {{ this }}
  )
{% endif %}
