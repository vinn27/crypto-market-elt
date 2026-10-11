# Crypto Market ELT — an autonomous analytics pipeline

![pipeline](https://github.com/vinn27/crypto-market-elt/actions/workflows/daily-pipeline.yml/badge.svg)
![Netlify](https://img.shields.io/badge/dashboard-live-0ca30c)

**Live dashboard: [crypto-market-elt.netlify.app](https://crypto-market-elt.netlify.app)** ·
**How it works: [documentation](https://crypto-market-elt.netlify.app/docs.html)**

Every morning at 06:35 IST this pipeline, unattended: fetches crypto market
data from the CoinGecko API → lands it **raw** in **Snowflake** → rebuilds a
tested **star schema** with **dbt** (15 quality checks) → exports JSON →
**deploys the dashboard** to Netlify's CDN.

> Deliberately **ELT** — load raw first, transform in-warehouse with SQL under
> version control. The counterpart to my [stock-market batch ETL](https://github.com/vinn27/stock-market-etl)
> project, where PySpark transformed data *outside* the database before
> loading to MySQL.

## Architecture

```
CoinGecko API ──▶ Python extract ──▶ Snowflake ──▶ dbt ──▶ JSON export ──▶ Netlify
(free, no key)    + load (no         RAW schema    │      (marts →        (static
                  transforms)        (bronze)      ▼       4 files)       dashboard
                                                    ┌─────────────┐        + docs)
                                                    │ STAGING     │ clean / rename / cast
                                                    │ (silver)    │ one model per source
                                                    ├─────────────┤
                                                    │ MARTS (gold)│ star schema:
                                                    │             │ dim_coins, dim_date,
                                                    │             │ fact_market_snapshots
                                                    └─────────────┘
        ▲                                                        │
        └──────────── GitHub Actions, daily 06:35 IST ───────────┘
         (extract → load → dbt build + 15 tests → export → commit → deploy)
```

## Pipeline stages

| Stage | Tool | What happens |
|---|---|---|
| Extract | Python · `requests` | Top-50 snapshot + 90-day daily history (top 10), retry with backoff honouring `Retry-After` |
| Load | Python · `snowflake-connector` | Land raw rows as-is in `CRYPTO_DB.RAW` — append-only, stamped `loaded_at` |
| Transform | dbt Core | Staging (dedupe latest-load-wins, rename, cast) → marts star schema |
| Test | dbt tests | 15 checks: not-null, unique, relationships, no duplicate facts, positive prices |
| Orchestrate | GitHub Actions | Daily cron on free public-repo minutes; `pipeline-bot` commits fresh data |
| Publish | Netlify CLI | Dashboard + docs deployed to a global CDN; visitors never touch Snowflake |

## Data model

| Table | Type | Grain |
|---|---|---|
| `fact_market_snapshots` | fact | one row per coin per date — price, market cap, volume |
| `dim_coins` | dimension | one row per coin — symbol, rank, supply, ATH/ATL |
| `dim_date` | dimension | one row per calendar day — day name, weekday, month |

The dashboard's "weekday effect" chart is the star schema paying rent: a plain
date doesn't know it's a Saturday — `fact ⟕ dim_date` does.

## Why this stack

Snowflake + dbt is the consensus default stack of 2026 data-engineering job
descriptions. This build covers the ELT pattern, warehouse-native transforms,
model testing, lineage, CI-scheduled runs, and cost governance (the warehouse
auto-suspends after 60 idle seconds and kills runaway queries at 10 minutes).

## Repo structure

```
├── pipelines/            extract_load · setup_snowflake · export_dashboard_data
├── dbt/
│   ├── models/staging/   sources.yml + stg_* views (clean, dedupe, cast)
│   ├── models/marts/     dim_* + fact_* tables + schema.yml tests
│   └── tests/            custom tests (no duplicate facts, positive prices)
├── dashboard/            static site: index.html + docs.html + data/*.json
└── .github/workflows/    daily ELT + export + deploy
```

## Reproduce it

Free Snowflake trial (email only, no card) → clone → fill `.env` from
`.env.example` →

```bash
python pipelines/setup_snowflake.py     # database, schemas, warehouse governance
python pipelines/extract_load.py        # fetch + land raw
cd dbt && dbt build                     # transform + 15 tests
python pipelines/export_dashboard_data.py  # dashboard JSON
```

Market data from CoinGecko. Informational only — not investment advice.
