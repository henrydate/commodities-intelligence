"""
Fetch cross-asset market data (equities, gold, volatility) via yfinance.

These series let us measure how commodities and FX co-move with the broader
stock market and risk sentiment. Each fetch is independent and degrades
gracefully: if one ticker fails, the rest still load.
"""

import pandas as pd
import logging

from . import catalog

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    logger.warning("yfinance not installed - market data unavailable")


def fetch_ticker(ticker, name):
    """Fetch maximum available daily history for one ticker. Returns Date+value df."""
    if not YF_AVAILABLE:
        return pd.DataFrame()

    try:
        hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)

        if hist is None or hist.empty:
            logger.warning(f"{name} ({ticker}): no data returned")
            return pd.DataFrame()

        # history() returns a clean single-index frame with a 'Close' column
        df = hist.reset_index()[["Date", "Close"]].rename(columns={"Close": name})

        # Strip timezone so it merges cleanly with naive commodity dates
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
        df[name] = pd.to_numeric(df[name], errors="coerce")
        df = df.dropna().drop_duplicates(subset="Date").sort_values("Date")

        logger.info(
            f"Fetched {name} ({ticker}): {len(df)} rows, "
            f"{df['Date'].min().date()} -> {df['Date'].max().date()}"
        )
        return df

    except Exception as e:
        logger.warning(f"{name} ({ticker}) fetch failed: {e}")
        return pd.DataFrame()


def load_market_data():
    """Fetch every Yahoo-sourced series in the catalog. Returns {name: DataFrame}."""
    tickers = catalog.yahoo_tickers()
    market = {}
    for name, ticker in tickers.items():
        df = fetch_ticker(ticker, name)
        if not df.empty:
            market[name] = df
    logger.info(f"Loaded {len(market)} of {len(tickers)} market series")
    return market
