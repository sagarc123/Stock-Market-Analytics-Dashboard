import logging
import os
import sqlite3
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO)

# CORRECTED PATH: Database is in ../data/stock_data.db relative to api.py
DB_FILENAME = "stock_data.db"
TABLE_NAME = "stock_data"

# Global DataFrame to hold the stock data in memory
df_stock: pd.DataFrame = pd.DataFrame()
data_loaded = False

# Initialize FastAPI app
app = FastAPI(title="Stock Data Analysis API")

# Allow CORS for frontend apps (like Dash or React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA LOADING AND PREPROCESSING ---


@app.on_event("startup")
def load_data():
    """Loads and preprocesses the stock data from SQLite database into memory."""
    global df_stock, data_loaded

    # Get the absolute path to the database file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_FILENAME)

    logging.info(f"Looking for database at: {db_path}")
    logging.info(f"Current working directory: {os.getcwd()}")

    if not os.path.exists(db_path):
        logging.error(f"❌ Database file not found at: {db_path}")
        logging.error("Please ensure the database file exists in the data/ directory")
        df_stock = pd.DataFrame()
        data_loaded = False
        return

    try:
        # Connect and read table
        with sqlite3.connect(db_path) as conn:
            # First, check if table exists
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'"
            )
            table_exists = cursor.fetchone()

            if not table_exists:
                logging.error(f"❌ Table '{TABLE_NAME}' not found in database")
                # List available tables for debugging
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                available_tables = cursor.fetchall()
                logging.error(f"Available tables: {available_tables}")
                df_stock = pd.DataFrame()
                data_loaded = False
                return

            df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)

        logging.info(f"✅ Data loaded successfully. Total rows: {len(df)}")
        logging.info(f"📊 Columns: {list(df.columns)}")

    except Exception as e:
        logging.error(f"❌ Failed to load data from SQLite: {e}")
        df_stock = pd.DataFrame()
        data_loaded = False
        return

    # --- Preprocess ---
    try:
        # Convert 'Date' to datetime
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Ensure numeric columns are properly typed
        numeric_cols = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Market_Cap",
            "PE_Ratio",
            "Dividend_Yield",
            "Volatility",
            "Sentiment_Score",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Fill missing numeric values with 0
        if "Volume" in df.columns:
            df["Volume"] = df["Volume"].fillna(0)
        if "Market_Cap" in df.columns:
            df["Market_Cap"] = df["Market_Cap"].fillna(0)

        df_stock = df
        data_loaded = True
        logging.info(f"✅ Data preprocessed successfully. Loaded {len(df_stock)} rows.")

    except Exception as e:
        logging.error(f"❌ Failed to preprocess data: {e}")
        df_stock = pd.DataFrame()
        data_loaded = False


# --- HELPER FUNCTIONS ---


def get_filtered_df(period: str) -> pd.DataFrame:
    """Filter in-memory DataFrame by year (YYYY) or month (YYYY-MM)."""
    if not data_loaded or df_stock.empty:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded. Please check if database file exists and contains the required table.",
        )

    if not period:
        raise HTTPException(status_code=400, detail="Period parameter is required.")

    df = df_stock.copy()
    period = period.strip()

    try:
        if len(period) == 4 and period.isdigit():
            year = int(period)
            df_filtered = df[df["Date"].dt.year == year]
        elif len(period) == 7 and period.count("-") == 1:
            year, month = map(int, period.split("-"))
            df_filtered = df[
                (df["Date"].dt.year == year) & (df["Date"].dt.month == month)
            ]
        else:
            raise ValueError("Invalid period format. Use YYYY or YYYY-MM.")
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid period format. Use YYYY or YYYY-MM."
        )

    if df_filtered.empty:
        raise HTTPException(
            status_code=404, detail=f"No data found for period {period}"
        )

    return df_filtered


def get_mode_trend(group):
    """Return the most frequent Trend in a group."""
    mode_series = group["Trend"].mode()
    return mode_series.iloc[0] if not mode_series.empty else "Neutral"


# --- API ENDPOINTS ---


@app.get("/")
def root():
    """Root endpoint with API information."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_FILENAME)

    return {
        "message": "Stock Data Analysis API",
        "status": "running",
        "data_loaded": data_loaded,
        "data_rows": len(df_stock) if data_loaded else 0,
        "database_path": db_path,
        "database_exists": os.path.exists(db_path),
        "endpoints": {
            "/health": "Health check",
            "/metrics/sector_summary": "Sector summary data",
            "/data/daily_prices": "Aggregated daily prices",
        },
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_FILENAME)

    return {
        "status": "ok",
        "data_loaded": data_loaded,
        "data_rows": len(df_stock) if data_loaded else 0,
        "database_path": db_path,
        "database_exists": os.path.exists(db_path),
    }


@app.get("/metrics/sector_summary")
def get_sector_summary(period: str):
    """Return aggregated metrics per sector for a given period."""
    if not data_loaded:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded. Please check if database file exists and contains the required table.",
        )

    df_filtered = get_filtered_df(period)

    # Check if required columns exist
    required_cols = ["Sector", "Close", "Volume", "Volatility"]
    missing_cols = [col for col in required_cols if col not in df_filtered.columns]
    if missing_cols:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required columns in data: {missing_cols}. Available columns: {list(df_filtered.columns)}",
        )

    agg_df = (
        df_filtered.groupby("Sector")
        .agg(
            avg_close=("Close", "mean"),
            total_volume=("Volume", "sum"),
            avg_volatility=("Volatility", "mean"),
        )
        .reset_index()
    )

    agg_df = agg_df[agg_df["total_volume"] > 0].sort_values(
        by="total_volume", ascending=False
    )

    if agg_df.empty:
        raise HTTPException(
            status_code=404, detail=f"No sector data found for period {period}"
        )

    return agg_df.to_dict(orient="records")


@app.get("/data/daily_prices")
def get_aggregated_prices(period: str, limit: int = 500):
    """Return aggregated stock data per company for a given period."""
    if not data_loaded:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded. Please check if database file exists and contains the required table.",
        )

    df_filtered = get_filtered_df(period)

    # Check if required columns exist
    required_cols = [
        "Company",
        "Sector",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Volatility",
        "PE_Ratio",
        "Market_Cap",
        "Trend",
    ]
    missing_cols = [col for col in required_cols if col not in df_filtered.columns]
    if missing_cols:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required columns in data: {missing_cols}. Available columns: {list(df_filtered.columns)}",
        )

    agg_df = (
        df_filtered.groupby(["Company", "Sector"])
        .agg(
            Open=("Open", "mean"),
            High=("High", "mean"),
            Low=("Low", "mean"),
            Close=("Close", "mean"),
            Volume=("Volume", "sum"),
            Volatility=("Volatility", "mean"),
            PE_Ratio=("PE_Ratio", "mean"),
            Market_Cap=("Market_Cap", "sum"),
        )
        .reset_index()
    )

    # Add most common trend
    trend_mode = (
        df_filtered.groupby(["Company", "Sector"])
        .apply(get_mode_trend)
        .reset_index(name="Trend")
    )
    agg_df = pd.merge(agg_df, trend_mode, on=["Company", "Sector"])

    # Add the period as display column
    agg_df["Date"] = period

    # Sort and limit
    agg_df = agg_df.sort_values(by="Market_Cap", ascending=False).head(limit)

    if agg_df.empty:
        raise HTTPException(
            status_code=404, detail=f"No company price data found for period {period}"
        )

    return agg_df.to_dict(orient="records")


# --- MAIN ENTRY POINT ---

if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("Starting Stock Data Analysis API...")
    print("=" * 50)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_FILENAME)

    print(f"📁 API Location: {current_dir}")
    print(f"📊 Database Path: {db_path}")
    print(f"📋 Database Exists: {os.path.exists(db_path)}")
    print(f"🔍 Table Name: {TABLE_NAME}")
    print("=" * 50)

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
