"""
Fetch external data for cross-asset analysis.

Two groups, each fetched independently so a single failure never breaks the run:
  1. FRED macro series (Fed funds rate, yield-curve spread, unemployment)
  2. Cross-asset market series (S&P 500, ASX 200, energy equities, gold, VIX,
     real US dollar index) - see src/market_data.py
"""

import os
import logging

import pandas as pd
import requests

from . import market_data
from . import catalog
from . import rba

logger = logging.getLogger(__name__)

# FRED API key (free: https://fred.stlouisfed.org/docs/api/fred/).
# Falls back to a working demo key but honours an env override.
FRED_API_KEY = os.getenv("FRED_API_KEY", "24a12929033c9d12af251fdc657f44ad")

# friendly column name -> FRED series id, sourced from the central catalog.
FRED_SERIES = {name: sid for name, sid in catalog.fred_drivers().items()}


def fetch_fred_data(series_id, start_date="1900-01-01"):
    """
    Fetch a single FRED series as a [Date, series_id] DataFrame.

    Pulls FULL available history by default - FRED macro series go back decades,
    and truncating here is what previously capped the merged dataset to ~5 years.
    """
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set, skipping FRED data")
        return pd.DataFrame()

    try:
        url = (
            "https://api.stlouisfed.org/fred/series/observations?"
            f"series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
            f"&observation_start={start_date}"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if "observations" not in data:
            logger.warning(f"No observations in FRED response for {series_id}")
            return pd.DataFrame()

        df = pd.DataFrame(data["observations"]).rename(
            columns={"date": "Date", "value": series_id})
        df["Date"] = pd.to_datetime(df["Date"])
        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        df = df[["Date", series_id]].dropna()
        logger.info(f"Fetched FRED {series_id}: {len(df)} rows, latest: {df['Date'].max().date()}")
        return df

    except Exception as e:
        logger.warning(f"Failed to fetch FRED {series_id}: {e}")
        return pd.DataFrame()


def load_external_data():
    """Fetch all external sources. Returns {friendly_name: DataFrame[Date, value]}."""
    external = {}

    # 1. FRED macro series (full history)
    if FRED_API_KEY:
        for name, series_id in FRED_SERIES.items():
            df = fetch_fred_data(series_id)
            if not df.empty:
                external[name] = df.rename(columns={series_id: name})
    else:
        logger.info("Set FRED_API_KEY env var to include macro series")

    # 2. Cross-asset market data (yfinance, full history)
    logger.info("Fetching cross-asset market data...")
    external.update(market_data.load_market_data())

    # 3. RBA (Australia) series for the ASX / AUD picture
    logger.info("Fetching RBA (Australia) data...")
    for name, (table, series_id) in catalog.rba_drivers().items():
        df = rba.fetch_rba_series(table, series_id)
        if not df.empty:
            external[name] = df.rename(columns={series_id: name})

    logger.info(f"Loaded {len(external)} external data sources total")
    return external
