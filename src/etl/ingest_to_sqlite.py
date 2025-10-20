# src/etl/ingest_to_sqlite.py
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from src.utils.db import engine

# UPDATED: Changed defaults for new data schema
CSV_PATH = os.getenv("CSV_PATH", "./data/synthetic_stock_data.csv")
TABLE_NAME = os.getenv("TABLE_NAME", "stock_data")


def ensure_table_schema(conn):
    # UPDATED: Schema to match the provided CSV file
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        Date TEXT PRIMARY KEY,
        Company TEXT,
        Sector TEXT,
        Open REAL,
        High REAL,
        Low REAL,
        Close REAL,
        Volume INTEGER,
        Market_Cap REAL,
        PE_Ratio REAL,
        Dividend_Yield REAL,
        Volatility REAL,
        Sentiment_Score REAL,
        Trend TEXT
    );
    """
    conn.execute(text(create_sql))
    conn.commit()


def ingest_csv(csv_path=CSV_PATH):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    # UPDATED: Using 'Date' instead of 'timestamp'
    df = pd.read_csv(csv_path, parse_dates=["Date"])
    # UPDATED: Formatting 'Date' column
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    # REMOVED: df["dt"] = df["timestamp"].dt.strftime("%Y-%m-%d") as it's not needed

    with engine.connect() as conn:
        # UPDATED: Table creation to match the provided CSV file
        conn.execute(
            text(
                f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Date TEXT PRIMARY KEY,
            Company TEXT,
            Sector TEXT,
            Open REAL,
            High REAL,
            Low REAL,
            Close REAL,
            Volume INTEGER,
            Market_Cap REAL,
            PE_Ratio REAL,
            Dividend_Yield REAL,
            Volatility REAL,
            Sentiment_Score REAL,
            Trend TEXT
        );
        """
            )
        )
        conn.commit()

        # UPDATED: Fetch existing primary keys ('Date')
        existing_ids = pd.read_sql(f"SELECT Date FROM {TABLE_NAME}", conn)
        existing_set = set(existing_ids["Date"].tolist())

        # UPDATED: Keep only new rows (based on 'Date')
        df_new = df[~df["Date"].isin(existing_set)]

    if len(df_new) == 0:
        print("No new rows to insert. Database is up to date.")
    else:
        df_new.to_sql(TABLE_NAME, con=engine, if_exists="append", index=False)
        print(f"Ingested {len(df_new)} new rows into {TABLE_NAME}")


if __name__ == "__main__":
    ingest_csv()
