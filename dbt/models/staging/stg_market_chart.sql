-- Staging model: daily price history, made trustworthy.
--
-- Same pattern as stg_coins, but note the dedupe GRANULARITY differs:
--   snapshot table -> keep 1 row per COIN          (partition by coin id)
--   history table  -> keep 1 row per COIN per DATE (partition by coin + date)
-- Granularity is a per-model design decision - always state it out loud.

with source as (
    select * from {{ source('coingecko', 'coin_market_chart') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by coin_id, price_date
            order by loaded_at desc
        ) as rn
    from source
)

select
    coin_id,
    price_date,
    price,
    market_cap,
    total_volume,
    loaded_at
from deduped
where rn = 1
