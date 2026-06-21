"""Flask REST API for commodities forecasts."""

from flask import Flask, jsonify, request
import pandas as pd
from pathlib import Path
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


def _read(name, **kw):
    path = DATA_DIR / name
    return pd.read_csv(path, **kw) if path.exists() else None


def load_data():
    """Load forecast + statistics data into memory."""
    try:
        return {
            "forecasts": _read("forecasts.csv"),
            "merged": _read("merged_data.csv"),
            "correlations": _read("correlations.csv", index_col=0),
            "corr_returns": _read("corr_returns.csv", index_col=0),
            "r2_returns": _read("r2_returns.csv", index_col=0),
            "drivers": _read("driver_rankings.csv"),
            "metrics": _read("metrics.csv").iloc[0].to_dict(),
            "baselines": _read("baselines.csv"),
        }
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return None


# Cache data on startup
DATA = load_data()


@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API docs."""
    return jsonify({
        "name": "Commodities Intelligence API",
        "version": "1.0",
        "endpoints": {
            "/health": "Health check",
            "/forecast": "Get 90-day forecasts",
            "/forecast/<commodity>": "Get forecast for specific commodity",
            "/historical": "Get historical data",
            "/correlations": "Correlation matrix (use ?on=returns|levels)",
            "/r2": "R-squared matrix (daily returns)",
            "/drivers/<asset>": "Ranked drivers of an asset (corr, R2, beta, p-value)",
            "/metrics": "Get data quality metrics",
            "/compare": "Compare LSTM vs baselines"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    if DATA is None:
        return jsonify({"status": "error", "message": "Data not loaded"}), 503

    return jsonify({
        "status": "healthy",
        "data_date": DATA["metrics"].get("Refresh_Date"),
        "data_rows": DATA["metrics"].get("Data_Rows")
    })


@app.route("/forecast", methods=["GET"])
def get_forecast():
    """Get 90-day forecasts for all commodities."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    days = request.args.get("days", 90, type=int)
    forecasts = DATA["forecasts"].head(days)

    return jsonify({
        "horizon_days": days,
        "commodities": ["Brent", "WTI", "Natural_Gas", "AUD_USD"],
        "forecasts": forecasts.to_dict("records")
    })


@app.route("/forecast/<commodity>", methods=["GET"])
def get_commodity_forecast(commodity):
    """Get forecast for specific commodity."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    valid_commodities = ["Brent", "WTI", "Natural_Gas", "AUD_USD"]
    if commodity not in valid_commodities:
        return jsonify({
            "error": f"Invalid commodity. Choose from: {', '.join(valid_commodities)}"
        }), 400

    days = request.args.get("days", 90, type=int)
    forecasts = DATA["forecasts"].head(days)

    return jsonify({
        "commodity": commodity,
        "horizon_days": days,
        "forecast": forecasts[[commodity, "Day_Ahead"]].rename(
            columns={commodity: "price"}
        ).to_dict("records")
    })


@app.route("/historical", methods=["GET"])
def get_historical():
    """Get historical data."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    days = request.args.get("days", 365, type=int)
    commodity = request.args.get("commodity", None)

    historical = DATA["merged"].tail(days).copy()

    if commodity:
        valid = ["Brent", "WTI", "Natural_Gas", "AUD_USD", "DXY"]
        if commodity not in valid:
            return jsonify({"error": f"Invalid commodity. Choose from: {', '.join(valid)}"}), 400
        historical = historical[["Date", commodity]]

    return jsonify({
        "days": len(historical),
        "data": historical.to_dict("records")
    })


@app.route("/correlations", methods=["GET"])
def get_correlations():
    """Correlation matrix. ?on=returns (default, recommended) or levels."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    on = request.args.get("on", "returns")
    key = "corr_returns" if on == "returns" else "correlations"
    matrix = DATA.get(key)
    if matrix is None:
        return jsonify({"error": f"{on} correlations not available"}), 404
    return jsonify({"measured_on": on, "correlations": matrix.to_dict()})


@app.route("/r2", methods=["GET"])
def get_r2():
    """R-squared matrix on daily returns."""
    if DATA is None or DATA.get("r2_returns") is None:
        return jsonify({"error": "R2 not available"}), 503
    return jsonify({"r2": DATA["r2_returns"].to_dict()})


@app.route("/drivers/<asset>", methods=["GET"])
def get_drivers(asset):
    """Ranked drivers of an asset: correlation, R2, beta, p-value."""
    if DATA is None or DATA.get("drivers") is None:
        return jsonify({"error": "Driver rankings not available"}), 503

    drivers = DATA["drivers"]
    subset = drivers[drivers["Target"] == asset]
    if subset.empty:
        valid = sorted(drivers["Target"].unique().tolist())
        return jsonify({"error": f"Unknown asset. Choose from: {valid}"}), 400
    return jsonify({"target": asset, "drivers": subset.to_dict("records")})


@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Get data quality metrics."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    return jsonify(DATA["metrics"])


@app.route("/compare", methods=["GET"])
def compare_models():
    """Compare LSTM vs baseline models."""
    if DATA is None:
        return jsonify({"error": "Data not available"}), 503

    days = request.args.get("days", 30, type=int)
    forecasts = DATA["forecasts"].head(days)
    baselines = DATA["baselines"].head(days * 2)  # 2 baseline models

    return jsonify({
        "days": days,
        "lstm_forecast": forecasts[["Brent", "WTI", "Natural_Gas", "AUD_USD"]].to_dict("records"),
        "ma_baseline": baselines[baselines["Model"] == "Moving_Average"][["Brent", "WTI", "Natural_Gas", "AUD_USD"]].head(days).to_dict("records"),
        "nochange_baseline": baselines[baselines["Model"] == "NoChange"][["Brent", "WTI", "Natural_Gas", "AUD_USD"]].head(days).to_dict("records")
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info("Starting Commodities Intelligence API...")
    logger.info("API docs available at http://localhost:5000/")
    app.run(debug=False, host="0.0.0.0", port=5000)
