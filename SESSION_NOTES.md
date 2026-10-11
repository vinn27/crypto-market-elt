# Session Notes

*Working log for the crypto-market-elt build. One section per session so any
future session (or future me) can pick up cold.*

---

## Day 3 — 2026-10-11 (GitHub Actions) — DONE

**Built:** `.github/workflows/daily-pipeline.yml` — cron `5 1 * * *`
(6:35 AM IST daily) + `workflow_dispatch` manual button. Ubuntu runner:
setup-python 3.12 → pip install (requests, dotenv, snowflake-connector,
dbt-snowflake) → `python pipelines/extract_load.py` → `dbt build` with
`DBT_PROFILES_DIR: .` and `working-directory: dbt`. Secrets injected as job
env (SNOWFLAKE_ACCOUNT/USER/PASSWORD from repo secrets; warehouse/db plain).

**Repo published:** github.com/vinn27/crypto-market-elt (public, pushed via
gh CLI). Verified `.env` not tracked (git ls-files) before push. Secrets set
via `gh secret set` reading values from .env in a loop (values never typed
into commands); `gh secret list` confirmed all 3.

**Password rotation:** user rotated Snowflake password (workbook ALTER
USER), local .env updated, connection re-verified. Note: the new password
was pasted into chat again — accepted for throwaway trial, but the
vault-only habit still needs reinforcing with the user.

**First cloud run: SUCCESS** (run 38121461117). Verified fresh data:
loaded_at 07:31 UTC Oct 11; fact 890→910 rows (Oct 10 + Oct 11 × 10 coins);
dim_date 90→92 rows. Pipeline is now fully autonomous.

**Next:** final piece — `dbt docs generate` static site → Netlify
(permanent live URL), plus README polish + interview story. That completes
D14–16.

---

---

## Day 2 — 2026-10-10 (dbt: staging layer) — DONE

**Built:** `dbt/` project — `dbt_project.yml`, `profiles.yml` (env_var-based,
secret-free, committable), `macros/generate_schema_name.sql` (pass-through
schema naming override — avoids dbt's `STAGING_STAGING` default gotcha),
`models/staging/sources.yml` (both RAW tables declared), and two staging
models: `stg_coins.sql`, `stg_market_chart.sql`.

**dbt anatomy learned:** a project is just dbt_project.yml + SQL files.
`source()` = exists already (Python built it); `ref()` = dbt built it.
Staging = views (no data copied, reads RAW live); marts = tables.

**Verified:** `dbt debug` all green; `dbt run` 2/2 views created in STAGING
schema. Dedupe proven: bitcoin 1 row (latest load's price), 50 coins total.

**Quirk understood (know this for interviews):** market_chart returns 91
points for 90 days — daily 00:00 UTC points PLUS a live "now" point sharing
today's date. Grain "one row per coin per DATE" collapses them to 90.
Yesterday's warning "config path models.crypto_elt.marts unused" = marts
folder doesn't exist yet (expected).

**Commands used (bash):**
```
cd dbt && set -a && source ../.env && set +a
export DBT_PROFILES_DIR=.
dbt debug    # connection + config check, builds nothing
dbt run      # compiles models, creates the views
```

**Also done same day — MARTS + TESTS (full dbt scope complete):**
- `models/marts/`: `dim_coins` (50 rows), `dim_date` (90 rows, built off
  distinct dates in stg_market_chart), `fact_market_snapshots` (890 rows =
  9 coins × 90 days + figure-heloc × 80 — the short-history quirk carried
  through correctly).
- Tests: schema.yml files on staging + marts (not_null, unique,
  relationships with new `arguments:` nesting — dbt 1.12 syntax), plus 2
  custom tests in `tests/` (no duplicate fact rows; prices positive).
  `dbt build` = 20/20 PASS, 0 warnings.
- Star schema proven with a real question: bitcoin avg price by day-of-week
  via fact ⟕ dim_date (Sunday cheapest, Friday priciest).

**Next session:** GitHub Actions — daily cron that runs extract_load.py +
dbt build with secrets injected as env vars (profiles.yml already supports
it). Then dbt docs → Netlify. Buffer banked: ~7 days.

---

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
