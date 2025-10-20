# src/utils/db.py
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Default DB URL (relative to project root). Change via environment variable DB_URL.
DB_URL = os.getenv("DB_URL", "sqlite:///src/api/stock.db")

# create_engine handles sqlite and other DBs (postgres, mysql) with same code
engine = create_engine(DB_URL, echo=False, future=True)


def test_connection():
    try:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT 1")).scalar()
            print("DB connected, test query returned:", r)
    except SQLAlchemyError as e:
        print("DB connection error:", e)
        raise


if __name__ == "__main__":
    test_connection()
