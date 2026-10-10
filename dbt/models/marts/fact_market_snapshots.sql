-- Fact table: the numbers. One row per coin per day.
-- Grain (say it out loud before writing): ONE COIN'S NUMBERS ON ONE DAY.
-- Keeps only IDs + numbers here; all descriptions live in the dims.

select
    coin_id,
    price_date,
    price,
    market_cap,
    total_volume
from {{ ref('stg_market_chart') }}
where price_date is not null
