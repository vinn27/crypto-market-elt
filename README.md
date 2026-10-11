# Crypto Market Analytics — Cloud ELT Pipeline

End-to-end **ELT** pipeline on the modern data stack: crypto market data from the CoinGecko API lands **raw** in **Snowflake**, is transformed by **dbt** into a star schema, runs daily via **GitHub Actions**, and publishes auto-generated **dbt docs** hosted live on Netlify.

> Deliberately ELT (load raw first, transform in-warehouse with SQL) — the counterpart to my [stock-market batch ETL](https://github.com/vinn27/stock-market-etl) project, where PySpark transformed data *outside* the database before loading to MySQL.

## Architecture

```
CoinGecko API ──▶ Python extract ──▶ Snowflake ──▶ dbt ──▶ dbt docs
(free, no key)    + load (no         RAW schema    │       static site
                  transforms)        (bronze)      ▼       on Netlify
                                                    ┌─────────────┐
                                                    │ STAGING     │ clean / rename / cast
                                                    │ (silver)    │ one model per source
                                                    ├─────────────┤
                                                    │ MARTS (gold)│ star schema:
                                                    │             │ dim_coins, dim_date,
                                                    │             │ fact_market_snapshots
                                                    └─────────────┘
        ▲                                                        │
        └──────────── GitHub Actions fires daily ────────────────┘
                     (extract → load → dbt build → docs deploy)
```

## Pipeline stages

| Stage | Tool | What happens |
|---|---|---|
| Extract | Python (`requests`) | Pull top-N coins market data + daily history from CoinGecko |
| Load | Python (`snowflake-connector`) | Land raw rows as-is in `CRYPTO_DB.RAW` — zero transformation |
| Transform | dbt Core | Staging models → marts (star schema), sources, tests, docs |
| Orchestrate | GitHub Actions | Daily cron: extract → load → `dbt build` → deploy docs |
| Publish | Netlify | `dbt docs generate` static site — live lineage & model catalog |

## Target data model

| Table | Type | Grain |
|---|---|---|
| `fact_market_snapshots` | fact | one row per coin per date (price, volume, market cap) |
| `dim_coins` | dimension | one row per coin (id, symbol, name, category) |
| `dim_date` | dimension | calendar dimension |

## Status

- [x] **Days 1–3** — Snowflake trial account, worksheets, warehouse/role concepts, SQL warm-up *(done Day 1)*
- [x] **Days 4–6** — Python extract from CoinGecko + load to `RAW` schema *(done Day 1 — 3 days ahead)*
- [x] **Days 7–11** — dbt Core: project setup, staging → marts, sources, tests *(done Day 2)*
- [x] **Days 12–13** — GitHub Actions daily schedule, README/architecture polish *(done Day 3)*
- [ ] **Days 14–16** — dbt docs → Netlify (live URL), interview story prep

## Why this stack

Snowflake + dbt is the consensus "default stack" of 2026 data-engineering job descriptions. This project covers the ELT pattern, warehouse-native transforms, model testing, lineage documentation, and CI-scheduled runs — with a live artifact anyone can click through.
