-- Dimension: descriptions of coins. One row per coin.
-- Comes from the clean staging view - marts never touch RAW directly.

select
    coin_id,
    symbol,
    coin_name,
    market_cap_rank,
    circulating_supply,
    total_supply,
    max_supply,
    ath,                                   -- all-time high price
    ath_date,
    atl,                                   -- all-time low price
    atl_date,
    source_last_updated
from {{ ref('stg_coins') }}
where coin_id is not null
