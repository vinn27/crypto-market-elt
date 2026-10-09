"""Idempotent Snowflake provisioning: creates the database + layer schemas.

Runs from anywhere; safe to re-run (IF NOT EXISTS). Anyone cloning the repo
can provision their trial account with one command:
    .venv/Scripts/python.exe pipelines/setup_snowflake.py
"""
import os

from dotenv import load_dotenv
from snowflake.connector import connect

load_dotenv()

# The three medallion layers live as SCHEMAS inside one database.
# RAW    = raw landed data (bronze) - Python loads here
# STAGING/ + MARTS/  - dbt builds these later
LAYER_SCHEMAS = ["RAW", "STAGING", "MARTS"]

conn = connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
)

with conn.cursor() as cur:
    cur.execute("CREATE DATABASE IF NOT EXISTS CRYPTO_DB")
    for schema in LAYER_SCHEMAS:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS CRYPTO_DB.{schema}")
        print(f"OK  CRYPTO_DB.{schema}")
    cur.execute("SHOW SCHEMAS IN DATABASE CRYPTO_DB")
    print("\nSchemas now in CRYPTO_DB:")
    for row in cur.fetchall():
        print(f"  - {row[1]}")

conn.close()
