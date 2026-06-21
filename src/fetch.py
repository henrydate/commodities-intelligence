"""Fetch data from internal repos and external sources."""

import os
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Base paths to data repos
REPOS_BASE = Path(__file__).parent.parent.parent
OIL_REPO = REPOS_BASE / "oil-prices"
GAS_REPO = REPOS_BASE / "natural-gas"
EXCHANGE_REPO = REPOS_BASE / "exchange-rates"


def load_oil_data(freq="daily"):
    """
    Load oil price data (Brent and WTI).

    freq: 'daily', 'weekly', 'monthly', 'year'
    """
    if freq == "daily":
        brent_path = OIL_REPO / "data" / "brent-daily.csv"
        wti_path = OIL_REPO / "data" / "wti-daily.csv"
    elif freq == "weekly":
        brent_path = OIL_REPO / "data" / "brent-weekly.csv"
        wti_path = OIL_REPO / "data" / "wti-weekly.csv"
    elif freq == "monthly":
        brent_path = OIL_REPO / "data" / "brent-monthly.csv"
        wti_path = OIL_REPO / "data" / "wti-monthly.csv"
    else:
        raise ValueError(f"Unknown frequency: {freq}")

    brent = pd.read_csv(brent_path)
    wti = pd.read_csv(wti_path)

    brent.columns = ["Date", "Brent"]
    wti.columns = ["Date", "WTI"]

    brent["Date"] = pd.to_datetime(brent["Date"])
    wti["Date"] = pd.to_datetime(wti["Date"])

    # Merge Brent and WTI
    oil = brent.merge(wti, on="Date", how="outer").sort_values("Date")
    oil = oil.dropna(subset=["Brent", "WTI"])

    logger.info(f"Loaded oil data ({freq}): {len(oil)} rows, date range {oil['Date'].min()} to {oil['Date'].max()}")

    return oil


def load_gas_data(freq="daily"):
    """Load natural gas price data."""
    if freq == "daily":
        path = GAS_REPO / "data" / "daily.csv"
    elif freq == "monthly":
        path = GAS_REPO / "data" / "monthly.csv"
    else:
        raise ValueError(f"Unknown frequency: {freq}")

    gas = pd.read_csv(path)
    # Rename Price column to Natural_Gas
    gas = gas.rename(columns={"Price": "Natural_Gas"})
    gas["Date"] = pd.to_datetime(gas["Date"])
    gas = gas[["Date", "Natural_Gas"]].dropna(subset=["Natural_Gas"])

    logger.info(f"Loaded gas data ({freq}): {len(gas)} rows, date range {gas['Date'].min()} to {gas['Date'].max()}")

    return gas


def load_exchange_data(freq="daily"):
    """Load exchange rate data (USD/AUD)."""
    if freq == "daily":
        path = EXCHANGE_REPO / "data" / "daily.csv"
    elif freq == "monthly":
        path = EXCHANGE_REPO / "data" / "monthly.csv"
    elif freq == "yearly":
        path = EXCHANGE_REPO / "data" / "yearly.csv"
    else:
        raise ValueError(f"Unknown frequency: {freq}")

    rates = pd.read_csv(path)
    # Filter for Australia (AUD/USD)
    rates = rates[rates["Country"] == "Australia"].copy()
    rates = rates[["Date", "Exchange rate"]].rename(columns={"Exchange rate": "AUD_USD"})
    rates["Date"] = pd.to_datetime(rates["Date"])
    rates = rates.dropna(subset=["AUD_USD"])

    logger.info(f"Loaded exchange data ({freq}): {len(rates)} rows, date range {rates['Date'].min()} to {rates['Date'].max()}")

    return rates


def load_internal_data(freq="daily"):
    """
    Load all internal data (oil, gas, exchange rates).

    Returns merged DataFrame with Date as index.
    """
    oil = load_oil_data(freq)
    gas = load_gas_data(freq)
    rates = load_exchange_data(freq)

    # Merge all on Date
    data = oil.merge(gas, on="Date", how="outer") \
             .merge(rates, on="Date", how="outer") \
             .sort_values("Date")

    # Forward fill for small gaps, then drop any remaining NaN
    data = data.ffill().dropna()

    logger.info(f"Merged internal data: {len(data)} rows, {len(data.columns)} columns")

    return data
