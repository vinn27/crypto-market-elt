-- Dimension: the calendar. One row per day that exists in our data.
-- Every date gets a name, weekday number, month - so questions like
-- "weekend vs weekday prices" become easy queries later.

with dates as (
    select distinct price_date as date_day
    from {{ ref('stg_market_chart') }}
)

select
    date_day,
    dayname(date_day)                      as day_name,      -- 'Saturday'
    dayofweek(date_day)                    as day_of_week,   -- 0 = Sunday
    monthname(date_day)                    as month_name,
    date_trunc('month', date_day)          as month_start_date
from dates
