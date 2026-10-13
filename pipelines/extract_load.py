"""Extract CoinGecko market data and land it raw in Snowflake.

The ELT rule of this project: Python only EXTRACTS and LOADS.
No cleaning, no business logic, no type casting beyond what is needed to
unpack the API's structure. ALL transformation happens in dbt, in-warehouse.

Sources (free public API, no key):
  /coins/markets           top-50 snapshot            -> RAW.COINS_MARKETS
  /coins/{id}/market_chart 1-year history, top-10     -> RAW.COIN_MARKET_CHART

RAW is append-only: every run adds rows stamped with loaded_at (Snowflake
fills it via DEFAULT CURRENT_TIMESTAMP). dbt dedupes downstream, so re-running
this script is always safe.
"""
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from snowflake.connector import connect

BASE_URL = "https://api.coingecko.com/api/v3"
SNAPSHOT_COINS = 50      # top-N by market cap, daily snapshot
HISTORY_COINS = 10       # top-N that also get a full year of daily history
HISTORY_DAYS = 365       # free tier allows up to 365 days (probed: 200 OK)
CALL_PAUSE_SECONDS = 10  # free tier is rate-limited; stay polite
MAX_RETRIES = 5

# The fields we land from /coins/markets, in column order. Values arrive
# as-is; no renaming, no casting.
MARKET_FIELDS = [
    "id", "symbol", "name",
    "current_price", "market_cap", "market_cap_rank",
    "total_volume", "high_24h", "low_24h",
    "price_change_percentage_24h",
    "circulating_supply", "total_supply", "max_supply",
    "ath", "ath_date", "atl", "atl_date",
    "last_updated",
]

DDL_MARKETS = """
CREATE TABLE IF NOT EXISTS RAW.COINS_MARKETS (
    id                        VARCHAR,   -- column names mirror the API exactly;
    symbol                    VARCHAR,   -- renaming happens in dbt staging, not here
    name                      VARCHAR,
    current_price             FLOAT,
    market_cap                FLOAT,
    market_cap_rank           INTEGER,
    total_volume              FLOAT,
    high_24h                  FLOAT,
    low_24h                   FLOAT,
    price_change_percentage_24h FLOAT,
    circulating_supply        FLOAT,
    total_supply              FLOAT,
    max_supply                FLOAT,
    ath                       FLOAT,
    ath_date                  VARCHAR,   -- ISO string lands raw; dbt casts later
    atl                       FLOAT,
    atl_date                  VARCHAR,
    last_updated              VARCHAR,
    loaded_at                 TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
)
"""

DDL_CHART = """
CREATE TABLE IF NOT EXISTS RAW.COIN_MARKET_CHART (
    coin_id       VARCHAR,
    price_date    DATE,       -- derived from ms-epoch only to unpack the array
    price         FLOAT,
    market_cap    FLOAT,
    total_volume  FLOAT,
    loaded_at     TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
)
"""


def get_with_retry(url, params):
    """GET with backoff on rate limits (429) and server errors (5xx).
    Honours the Retry-After header when the API sends one."""
    for attempt in range(1, MAX_RETRIES + 1):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code in (429, 503, 504) and attempt < MAX_RETRIES:
            wait = int(r.headers.get("Retry-After", 30))
            print(f"   rate-limited ({r.status_code}): backing off {wait}s "
                  f"(attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()


def fetch_snapshot():
    """One call: top-N coins by market cap, current values."""
    return get_with_retry(
        f"{BASE_URL}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": SNAPSHOT_COINS,
            "page": 1,
            "sparkline": "false",
        },
    )


def fetch_history(coin_id):
    """One call per coin: three parallel [ms_epoch, value] arrays -> rows.

    The only 'transformation' here is structural: zipping three arrays into
    one row per date and turning ms-epoch into a DATE. Values are untouched.
    """
    data = get_with_retry(
        f"{BASE_URL}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": HISTORY_DAYS, "interval": "daily"},
    )

    rows = []
    for (ts_ms, price), (_ts, market_cap), (_ts2, total_volume) in zip(
        data["prices"], data["market_caps"], data["total_volumes"]
    ):
        price_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()
        rows.append((coin_id, price_date, price, market_cap, total_volume))
    return rows


def insert_rows(cur, table, columns, rows):
    """executemany on a single INSERT is optimized by the Snowflake connector
    into one bulk multi-row insert - fine at our scale. The production-scale
    path would be PUT to a stage + COPY INTO, same warehouse."""
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
    cur.executemany(sql, rows)


def main():
    load_dotenv()
    conn = connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="RAW",
    )
    cur = conn.cursor()

    print("== Ensuring RAW tables exist ==")
    cur.execute(DDL_MARKETS)
    cur.execute(DDL_CHART)

    print(f"== Extract: top {SNAPSHOT_COINS} snapshot ==")
    markets = fetch_snapshot()
    rows = [tuple(m.get(f) for f in MARKET_FIELDS) for m in markets]
    insert_rows(cur, "RAW.COINS_MARKETS", MARKET_FIELDS, rows)
    print(f"   loaded {len(rows)} rows into RAW.COINS_MARKETS")

    print(f"== Extract: {HISTORY_DAYS}-day history for top {HISTORY_COINS} ==")
    top_ids = [m["id"] for m in markets[:HISTORY_COINS]]
    for coin_id in top_ids:
        hist = fetch_history(coin_id)
        insert_rows(cur, "RAW.COIN_MARKET_CHART",
                    ["coin_id", "price_date", "price", "market_cap", "total_volume"],
                    hist)
        print(f"   {coin_id:20} {len(hist)} days loaded")
        time.sleep(CALL_PAUSE_SECONDS)  # last sleep is wasted, keeps code simple

    cur.close()
    conn.close()
    print("== Done: RAW layer populated ==")


if __name__ == "__main__":
    main()
