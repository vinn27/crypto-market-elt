-- Custom test: prices must be positive numbers.
-- A zero or negative price would mean broken source data.

select *
from {{ ref('fact_market_snapshots') }}
where price is null or price <= 0
