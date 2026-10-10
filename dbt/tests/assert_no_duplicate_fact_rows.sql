-- Custom test: the fact table must have ONE row per coin per day.
-- A test is just a SELECT that looks for BAD rows.
-- Zero rows returned = pass. Any rows returned = fail.

select
    coin_id,
    price_date,
    count(*) as row_count
from {{ ref('fact_market_snapshots') }}
group by coin_id, price_date
having count(*) > 1
