"""Daily refresh script: fetch data, preprocess, forecast."""

import logging
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Create logs directory first
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

from src import fetch, external_sources, preprocess, forecast, analysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "refresh.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def refresh_data():
    """Fetch and save latest data."""
    logger.info("=" * 60)
    logger.info("Starting daily data refresh")
    logger.info("=" * 60)

    try:
        # Load internal data
        internal = fetch.load_internal_data(freq="daily")
        logger.info(f"Loaded internal data: {len(internal)} rows")

        # Load external data
        external_dict = external_sources.load_external_data()
        logger.info(f"Loaded {len(external_dict)} external sources")

        # Merge
        merged = preprocess.merge_data(internal, external_dict)

        # Save merged data
        merged.to_csv(DATA_DIR / "merged_data.csv", index=False)
        logger.info(f"Saved merged data to {DATA_DIR / 'merged_data.csv'}")

        return merged

    except Exception as e:
        logger.error(f"Error during data refresh: {e}", exc_info=True)
        raise


def forecast_future_values(data):
    """Generate 90-day forecasts for the commodity/FX targets, in REAL units."""
    logger.info("Generating forecasts")

    try:
        from sklearn.preprocessing import MinMaxScaler

        target_cols = ["Brent", "WTI", "Natural_Gas", "AUD_USD"]

        # Train only on the commodity backbone (complete, full history). A
        # dedicated scaler lets us invert the model output back to real prices.
        prices = data[target_cols].dropna().reset_index(drop=True)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(prices.values)

        X, y = preprocess.create_sequences(scaled, lookback=60)
        logger.info(f"Prepared {len(X)} sequences over {len(prices)} rows for forecasting")

        # Load or train model (retrain if feature count changed)
        try:
            model = forecast.load_model()
            if model.input_shape[-1] != len(target_cols):
                logger.info("Model feature mismatch - retraining")
                raise FileNotFoundError
            logger.info("Loaded existing model")
        except FileNotFoundError:
            logger.info("Training new model")
            model, _ = forecast.train_lstm(X, y, epochs=20)
            forecast.save_model(model)

        # Forecast 90 steps from the most recent window, then invert scaling
        scaled_fc = forecast.forecast_future(model, X[-1], n_steps=90)
        real_fc = scaler.inverse_transform(scaled_fc)

        forecast_df = pd.DataFrame(real_fc, columns=target_cols)
        forecast_df.insert(0, "Day_Ahead", range(1, len(forecast_df) + 1))
        # Attach real future business-day dates for plotting on a real axis
        last_date = pd.to_datetime(data["Date"].max())
        forecast_df.insert(1, "Date",
                           pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=len(forecast_df)))
        forecast_df.to_csv(DATA_DIR / "forecasts.csv", index=False)

        logger.info(f"Saved {len(forecast_df)} day forecasts (real units)")
        return forecast_df

    except Exception as e:
        logger.error(f"Error during forecasting: {e}", exc_info=True)
        raise


def calculate_correlations(data):
    """Calculate and save correlation / R-squared matrices (levels + returns)."""
    logger.info("Calculating correlations & R-squared")

    try:
        from src import stats_analysis as sa

        # Levels correlation (kept for contrast; correlations.csv name preserved
        # for backward compatibility with the API).
        corr_levels = sa.correlation_matrix(data, use="levels")
        corr_levels.to_csv(DATA_DIR / "correlations.csv")
        corr_levels.to_csv(DATA_DIR / "corr_levels.csv")

        # Returns correlation + R-squared (the statistically sound view).
        corr_returns = sa.correlation_matrix(data, use="returns")
        corr_returns.to_csv(DATA_DIR / "corr_returns.csv")

        r2_returns = sa.r_squared_matrix(data, use="returns")
        r2_returns.to_csv(DATA_DIR / "r2_returns.csv")

        logger.info(f"Saved correlation/R2 matrices: {corr_returns.shape[0]} assets")
        return corr_levels

    except Exception as e:
        logger.error(f"Error during correlation calculation: {e}", exc_info=True)
        raise


def generate_statistics(data):
    """Build driver tables: fast (daily, asset-vs-asset) and macro (annual)."""
    logger.info("Generating driver/regression statistics")

    try:
        from src import stats_analysis as sa
        from src import catalog

        present = list(data.columns)
        assets = catalog.asset_columns(present)
        # Driver pool = macro series + tradeable global-cycle bellwethers
        # (copper, China) so they explain other assets even though the UI
        # also shows them as assets in their own right.
        macro = catalog.driver_columns(present)
        transforms = catalog.transforms_map(present)

        # 1. Fast view: what other tradeable assets move with each target (daily)
        targets = ["Brent", "WTI", "Natural_Gas", "AUD_USD"]
        fast = []
        for tgt in targets:
            t = sa.driver_ranking(data, tgt, drivers=[a for a in assets if a != tgt], use="returns")
            t.insert(0, "Target", tgt)
            fast.append(t)
        pd.concat(fast, ignore_index=True).to_csv(DATA_DIR / "driver_rankings.csv", index=False)

        # 2. Macro view: annual-horizon relationship of each macro driver with
        #    every tradeable asset (the deep-dive "what moves markets" table).
        macro_rows = []
        for tgt in assets:
            tbl = sa.macro_relationship_table(data, tgt, macro, transforms, horizon=12)
            if tbl.empty:
                continue
            tbl.insert(0, "Target", tgt)
            tbl["Theme"] = tbl["Driver"].map(catalog.theme)
            tbl["Mechanism"] = tbl["Driver"].map(catalog.mechanism)
            macro_rows.append(tbl)

        macro_df = pd.concat(macro_rows, ignore_index=True)
        macro_df.to_csv(DATA_DIR / "macro_relationships.csv", index=False)
        logger.info(f"Saved macro relationships: {len(macro_df)} rows "
                    f"({len(assets)} assets x {len(macro)} drivers)")

        # 3. Multivariate models: each asset jointly explained by a parsimonious
        #    set of macro drivers (effects holding others constant).
        rep = [d for d in catalog.REPRESENTATIVE_DRIVERS if d in present]
        coef_rows, summary_rows = [], []
        for tgt in assets:
            coef, summ = sa.multi_regression_monthly(data, tgt, rep, transforms, horizon=12)
            if coef.empty:
                continue
            coef.insert(0, "Target", tgt)
            coef_rows.append(coef)
            summary_rows.append({
                "Target": tgt, "Combined_R2": summ["r2"], "Adj_R2": summ["adj_r2"],
                "Best_Single": summ["best_single"], "Best_Single_R2": summ["best_single_r2"],
                "N": summ["n"],
            })

        if coef_rows:
            pd.concat(coef_rows, ignore_index=True).to_csv(DATA_DIR / "multifactor_coefficients.csv", index=False)
            pd.DataFrame(summary_rows).to_csv(DATA_DIR / "multifactor_summary.csv", index=False)
            logger.info(f"Saved multivariate models for {len(summary_rows)} assets "
                        f"({len(rep)} drivers)")

        return macro_df

    except Exception as e:
        logger.error(f"Error generating statistics: {e}", exc_info=True)
        raise


def generate_baselines(data, target_cols):
    """Generate baseline forecasts for comparison."""
    logger.info("Generating baseline forecasts")

    try:
        ma_baseline = analysis.baseline_ma_forecast(data, target_cols, window=20, horizon=90)
        nochange_baseline = analysis.baseline_nochange_forecast(data, target_cols, horizon=90)

        baselines = pd.concat([ma_baseline, nochange_baseline], ignore_index=True)
        baselines.to_csv(DATA_DIR / "baselines.csv", index=False)

        logger.info(f"Generated baselines: {len(baselines)} forecasts")
        return baselines

    except Exception as e:
        logger.error(f"Error generating baselines: {e}", exc_info=True)
        raise


def generate_metrics(data):
    """Generate basic data quality metrics."""
    logger.info("Generating metrics")

    try:
        metrics = {
            "Refresh_Date": datetime.now().isoformat(),
            "Data_Rows": len(data),
            "Data_Columns": len(data.columns),
            "Date_Range": f"{data['Date'].min()} to {data['Date'].max()}",
            "Missing_Values": data.isnull().sum().sum()
        }

        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(DATA_DIR / "metrics.csv", index=False)

        logger.info(f"Metrics: {metrics}")

        return metrics

    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        # Refresh cycle
        data = refresh_data()
        forecasts = forecast_future_values(data)
        correlations = calculate_correlations(data)
        stats = generate_statistics(data)

        # Generate baselines for comparison
        target_cols = ["Brent", "WTI", "Natural_Gas", "AUD_USD"]
        baselines = generate_baselines(data, target_cols)

        metrics = generate_metrics(data)

        logger.info("=" * 60)
        logger.info("Daily refresh complete")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
