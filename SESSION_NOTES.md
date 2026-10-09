# Session Notes — 2026-10-09 (Day 1)

*Working log for the crypto-market-elt build. One file per session so any
future session (or future me) can pick up cold.*

## Where we are vs plan

Planned Day 1–6 → **all of it landed on Day 1.** Five days of buffer banked.

## What got built today

| # | Piece | Where |
|---|---|---|
| 1 | Repo + README (architecture, phase checklist) | `README.md`, commits `96aee3a`, `3ad6a3e`, `8f00340` |
| 2 | Snowflake trial account | org-account `VZJVHYS-IC67204`, user `vinn27` |
| 3 | Provisioning script (idempotent DDL) | `pipelines/setup_snowflake.py` |
| 4 | Connection sanity check | `pipelines/test_connection.py` |
| 5 | Full extract+load pipeline | `pipelines/extract_load.py` |

**Warehouse state**: `CRYPTO_DB` with schemas `RAW` / `STAGING` / `MARTS`
(plus defaults `INFORMATION_SCHEMA`, `PUBLIC`).
- `RAW.COINS_MARKETS` — 100 rows (2 loads × 50 coins), append-only
- `RAW.COIN_MARKET_CHART` — 1,446 rows (10 coins × ~90 days, 2026-07-12 → 2026-10-09)

## Failures we hit and what they taught (interview material)

1. **`invalid identifier 'ID'`** — DDL renamed `id` → `coin_id` while the
   INSERT used API field names. Lesson: in ELT, **RAW column names mirror the
   source exactly; renaming belongs to dbt staging models** (`stg_coins`:
   `id AS coin_id`). Half-created table had to be dropped — `CREATE IF NOT
   EXISTS` doesn't reshape.
2. **HTTP 429 Too Many Requests** — free tier rate-limits even with a 10s
   pause between calls. Lesson: production ingestion always has **retry with
   backoff honoring `Retry-After`** (`get_with_retry()`); bigger sleeps alone
   don't cut it.
3. **`figure-heloc` returned only 81 days** — the coin is newer than 90 days.
   Lesson: sources lie about completeness; the transform layer must not
   assume. Will become a dbt test case.

## Concepts covered (the ground-level layer)

- **ELT vs ETL** — load raw first, transform in-warehouse; raw preserved.
- **Snowflake object model** — account / database / schema / table; warehouse
  = rented compute (XS→6XL, auto-suspend ≈60s); roles hold permissions.
  Interview line: *"storage-compute separation — I scale and pay for compute
  independently; my XS auto-suspends when idle."*
- **Account naming** — org-account name (`VZJVHYS-IC67204`, used in configs)
  vs internal locator (`WM80161`, what `CURRENT_ACCOUNT()` returns).
- **Append-only RAW** — `loaded_at` defaults to `CURRENT_TIMESTAMP()`; re-runs
  never corrupt; dbt dedupes (latest `loaded_at` wins). Today's duplicate
  bitcoin rows (82512 vs 82489 across two loads) are the demo.
- **Medallion as schemas** — RAW/STAGING/MARTS inside one database.
- **Load mechanics** — `executemany` INSERT is optimized by the Snowflake
  connector into bulk multi-row insert; production scale = PUT + `COPY INTO`
  from a stage.

## Tomorrow's session — Day 7 starts (dbt Core)

1. `dbt init` inside `crypto-market-elt/dbt/`; `profiles.yml` reading from env
   vars (so GitHub Actions can inject secrets later, nothing hardcoded).
2. `sources.yml` declaring the two RAW tables (dbt now knows the pipeline's
   upstreams — lineage begins).
3. First staging models: `stg_coins` (rename + cast + dedupe latest
   `loaded_at`), `stg_market_chart` (same pattern).
4. Materializations: view vs table — which layer gets which, and why.

## Conventions we've locked

- Never commit `.env`; secrets only there. Rotate the Snowflake password
  before the repo goes public (it leaked into chat on Day 1).
- Commits: plain messages, no co-author trailer.
- dbt does ALL renaming/casting. Python extracts and loads, nothing else.
