-- Custom test: the data must be FRESH.
-- Born from a real incident: on Oct 12 GitHub's cron silently skipped the
-- nightly run and the dashboard quietly served yesterday's data. This test
-- turns "silently stale" into "build fails loudly": if the newest fact row
-- is more than 2 days old, something upstream stalled.

select 1 as stale_data
where (
    select datediff('day', max(price_date), current_date())
    from {{ ref('fact_market_snapshots') }}
) > 2
