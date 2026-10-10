-- Staging model: the RAW top-50 snapshot, made trustworthy.
--
-- Pattern (the staging idiom):  dedupe -> rename + cast -> done.
-- Dedupe rule: RAW is append-only, so the same coin appears once per load.
-- We keep only the row from the LATEST loaded_at ("latest load wins").

with source as (
    select * from {{ source('coingecko', 'coins_markets') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by id
            order by loaded_at desc
        ) as rn
    from source
),

renamed as (
    select
        -- identifiers
        id                                as coin_id,
        upper(symbol)                     as symbol,
        name                              as coin_name,

        -- market metrics (already numeric from the API)
        current_price,
        market_cap,
        market_cap_rank,
        total_volume,
        high_24h,
        low_24h,
        price_change_percentage_24h,
        circulating_supply,
        total_supply,
        max_supply,
        ath,
        atl,

        -- timestamps landed as ISO strings; cast HERE, where dbt owns the logic
        try_to_timestamp_tz(ath_date)     as ath_date,
        try_to_timestamp_tz(atl_date)     as atl_date,
        try_to_timestamp_tz(last_updated) as source_last_updated,

        loaded_at
    from deduped
    where rn = 1
)

select * from renamed
