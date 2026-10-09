"""Day 1 sanity check: proves Python can reach your Snowflake account.

Run:  .venv/Scripts/python.exe pipelines/test_connection.py
"""
import os

from dotenv import load_dotenv
from snowflake.connector import connect

load_dotenv()

conn = connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)

with conn.cursor() as cur:
    cur.execute(
        "SELECT CURRENT_ACCOUNT(), CURRENT_USER(), "
        "CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()"
    )
    print(cur.fetchone())

conn.close()
print("Connection OK - Python can talk to Snowflake.")
