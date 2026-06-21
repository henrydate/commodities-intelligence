"""Data preprocessing and normalization."""

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import logging

logger = logging.getLogger(__name__)


def merge_data(internal_df, external_dict):
    """
    Merge internal (commodity/FX) data with external macro & market series.

    The COMMODITY data is the backbone (spine): we keep every commodity
    trading day and align external series onto it with a left join. External
    series are forward-filled (Fed rate is a step function; equities have
    weekend/holiday gaps), but we deliberately do NOT global-dropna afterwards.

    Why this matters: a previous version did an outer-join then ffill().dropna(),
    which silently truncated ~25 years of commodity history down to the span of
    the shortest external series. Here, assets that simply did not exist yet
    (e.g. Gold ETF pre-2004) are left as NaN at the start; correlation/R^2 use
    pairwise-complete observations, so nothing is wasted and nothing is faked.

    internal_df: DataFrame with Date, Brent, WTI, Natural_Gas, AUD_USD
    external_dict: Dict of {name: DataFrame[Date, value]}

    Returns merged DataFrame (full commodity history), Date as a column.
    """
    merged = internal_df.copy()
    merged["Date"] = pd.to_datetime(merged["Date"]).dt.normalize()
    merged = merged.sort_values("Date").reset_index(drop=True)

    commodity_cols = [c for c in merged.columns if c != "Date"]

    for name, ext_df in external_dict.items():
        if ext_df is None or ext_df.empty or "Date" not in ext_df.columns:
            continue
        ext = ext_df.copy()
        ext["Date"] = pd.to_datetime(ext["Date"]).dt.normalize()
        ext = ext.sort_values("Date").drop_duplicates(subset="Date")
        # merge_asof (backward) attaches, for each commodity date, the most
        # recent external observation on/before it. This is the "carry last
        # known value forward" semantic, but tolerant of ANY reporting calendar
        # (e.g. initial jobless claims are dated week-ending Saturday and never
        # line up with weekday trading dates — an exact join would drop them all).
        merged = pd.merge_asof(merged, ext, on="Date", direction="backward")

    # Real DXY is preferred (from market data). Only synthesise a proxy if the
    # real series is entirely absent, so the dashboard always has USD strength.
    if "DXY" not in merged.columns and "AUD_USD" in merged.columns:
        merged["DXY"] = 1 / merged["AUD_USD"]
        logger.info("Real DXY unavailable - created proxy from 1 / AUD_USD")

    # Require only the commodity backbone to be present (always true); keep the
    # full history rather than dropping rows for not-yet-existing assets.
    merged = merged.dropna(subset=commodity_cols).reset_index(drop=True)

    span = f"{merged['Date'].min().date()} -> {merged['Date'].max().date()}"
    logger.info(f"Merged data: {len(merged)} rows, {len(merged.columns)} columns ({span})")
    logger.info(f"Columns: {', '.join(merged.columns.tolist())}")

    return merged


def normalize_data(df, scaler=None):
    """
    Normalize data to [0, 1] range.

    If scaler is None, fits a new MinMaxScaler.
    Returns normalized df and fitted scaler.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    if scaler is None:
        scaler = MinMaxScaler()
        normalized = scaler.fit_transform(df[numeric_cols])
    else:
        normalized = scaler.transform(df[numeric_cols])

    normalized_df = pd.DataFrame(
        normalized,
        columns=numeric_cols,
        index=df.index
    )
    normalized_df["Date"] = df["Date"].values

    logger.info(f"Normalized {len(numeric_cols)} numeric columns")

    return normalized_df, scaler


def create_sequences(data, lookback=60):
    """
    Create sequences for LSTM training.

    data: 2D array (time_steps, features)
    lookback: number of timesteps to look back

    Returns (X, y) where X is sequences and y is target values.
    """
    X, y = [], []

    for i in range(len(data) - lookback):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback])

    return np.array(X), np.array(y)


def prepare_forecast_data(df, target_cols, lookback=60):
    """
    Prepare data for LSTM training.

    df: Merged, normalized DataFrame
    target_cols: Columns to forecast (e.g., ['Brent', 'WTI', 'Natural_Gas', 'AUD_USD'])
    lookback: number of timesteps to look back

    Returns (X_train, y_train) and metadata for scaling/dates.
    """
    if not all(col in df.columns for col in target_cols):
        raise ValueError(f"Some target columns not in data: {target_cols}")

    data = df[target_cols].values
    X, y = create_sequences(data, lookback=lookback)

    logger.info(f"Created sequences: X shape {X.shape}, y shape {y.shape}")

    return X, y, df
