"""Export marts + staging data to static JSON files for the Netlify dashboard.

Design rule: dashboard visitors NEVER touch Snowflake. This script runs in
the nightly pipeline, writes small JSON files into dashboard/data/, and the
workflow commits them so Netlify redeploys. Free, fast, credential-free.

Reads:
  STAGING.STG_COINS          current top-50 snapshot (clean, deduped)
  MARTS.FACT_MARKET_SNAPSHOTS  daily history
  MARTS.DIM_DATE             calendar details
Writes:
  dashboard/data/overview.json   KPI numbers + freshness
  dashboard/data/history.json    1-year daily price series, top 8 coins
  dashboard/data/top_coins.json  top-20 snapshot table
  dashboard/data/weekday.json    bitcoin avg price + avg daily change by weekday
"""
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from snowflake.connector import connect

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard", "data")


def fetch_all(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


def iso(dt):
    """Snowflake TIMESTAMP_TZ -> ISO string; pass through anything else."""
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt


def main():
    load_dotenv()
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="MARTS",
    )
    cur = conn.cursor()

    # ---- overview ---------------------------------------------------------
    cur.execute("""
        SELECT COUNT(*), SUM(market_cap)
        FROM STAGING.STG_COINS
    """)
    coins_tracked, total_mcap = cur.fetchone()

    cur.execute("""
        SELECT coin_id, current_price, price_change_percentage_24h
        FROM STAGING.STG_COINS
        WHERE coin_id IN ('bitcoin', 'ethereum')
    """)
    majors = {r[0]: {"price": r[1], "change_24h": r[2]} for r in cur.fetchall()}

    cur.execute("""
        SELECT coin_name, price_change_percentage_24h
        FROM STAGING.STG_COINS
        ORDER BY ABS(price_change_percentage_24h) DESC LIMIT 1
    """)
    mover_name, mover_change = cur.fetchone()

    cur.execute("SELECT MAX(loaded_at) FROM RAW.COINS_MARKETS")
    last_load = cur.fetchone()[0]

    cur.execute("SELECT (SELECT COUNT(*) FROM MARTS.FACT_MARKET_SNAPSHOTS),"
                "       (SELECT COUNT(*) FROM MARTS.DIM_DATE),"
                "       (SELECT COUNT(*) FROM MARTS.DIM_COINS)")
    fact_rows, dim_dates, dim_coins = cur.fetchone()

    overview = {
        "as_of_utc": iso(last_load),
        "coins_tracked": coins_tracked,
        "total_market_cap": total_mcap,
        "bitcoin": majors["bitcoin"],
        "ethereum": majors["ethereum"],
        "top_mover": {"name": mover_name, "change_24h": mover_change},
        "fact_rows": fact_rows,
        "dim_dates": dim_dates,
        "dim_coins": dim_coins,
    }

    # ---- 1-year history, top 8 coins (palette has 8 slots; never cycle) ----
    cur.execute("""
        SELECT s.coin_id, s.symbol, s.coin_name, s.market_cap_rank
        FROM STAGING.STG_COINS s
        ORDER BY s.market_cap_rank
        LIMIT 8
    """)
    meta = cur.fetchall()  # fixed order = fixed color slots; color follows entity

    cur.execute("""
        SELECT f.coin_id, f.price_date, f.price, f.total_volume, f.market_cap
        FROM MARTS.FACT_MARKET_SNAPSHOTS f
        ORDER BY f.price_date
    """)
    by_coin = {m[0]: {"dates": [], "prices": [], "volumes": [], "mcaps": []} for m in meta}
    for coin_id, d, p, v, mc in cur.fetchall():
        if coin_id in by_coin:
            by_coin[coin_id]["dates"].append(d.isoformat())
            by_coin[coin_id]["prices"].append(p)
            by_coin[coin_id]["volumes"].append(v)
            by_coin[coin_id]["mcaps"].append(mc)

    history = {
        "coins": [
            {
                "id": m[0],
                "symbol": m[1],
                "name": m[2],
                "slot": i,  # fixed categorical color slot 0..7
                "dates": by_coin[m[0]]["dates"],
                "prices": by_coin[m[0]]["prices"],
                "volumes": by_coin[m[0]]["volumes"],
                "mcaps": by_coin[m[0]]["mcaps"],
            }
            for i, m in enumerate(meta)
        ]
    }

    # ---- top-20 snapshot table --------------------------------------------
    cur.execute("""
        SELECT market_cap_rank, coin_id, symbol, coin_name,
               current_price, price_change_percentage_24h,
               market_cap, total_volume
        FROM STAGING.STG_COINS
        ORDER BY market_cap_rank
        LIMIT 20
    """)
    top_coins = {
        "coins": [
            {
                "rank": r[0], "id": r[1], "symbol": r[2], "name": r[3],
                "price": r[4], "change_24h": r[5],
                "market_cap": r[6], "volume": r[7],
            }
            for r in cur.fetchall()
        ]
    }

    # ---- weekday insight (bitcoin): the dim_date payoff query --------------
    cur.execute("""
        WITH daily AS (
            SELECT f.price_date,
                   f.price,
                   100.0 * (f.price - LAG(f.price) OVER (ORDER BY f.price_date))
                       / LAG(f.price) OVER (ORDER BY f.price_date) AS day_change_pct
            FROM MARTS.FACT_MARKET_SNAPSHOTS f
            WHERE f.coin_id = 'bitcoin'
        )
        SELECT d.day_of_week,
               ROUND(AVG(daily.price), 0),
               ROUND(AVG(daily.day_change_pct), 2),
               COUNT(*)
        FROM daily
        JOIN MARTS.DIM_DATE d ON daily.price_date = d.date_day
        WHERE daily.day_change_pct IS NOT NULL
        GROUP BY d.day_of_week
        ORDER BY d.day_of_week
    """)
    weekday = {
        "coin": "bitcoin",
        "days": [
            {"day": DAYS[r[0]], "avg_price": r[1],
             "avg_change_pct": r[2], "days_counted": r[3]}
            for r in cur.fetchall()
        ]
    }

    conn.close()

    for name, payload in [("overview", overview), ("history", history),
                          ("top_coins", top_coins), ("weekday", weekday)]:
        path = os.path.join(OUT_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        print(f"wrote {os.path.normpath(path)}")

    print(f"as_of: {overview['as_of_utc']}, fact rows: {fact_rows}")


if __name__ == "__main__":
    main()
