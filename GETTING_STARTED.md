# Getting Started with Commodities Intelligence

## What You Have

A complete forecasting system with:
- **Data pipelines** that import from your 3 repos (oil, gas, exchange)
- **LSTM model** for unified forecasting of all 4 series
- **Streamlit dashboard** for interactive exploration
- **Daily refresh** orchestration with logging
- **Analysis notebook** showing methodology

## Quick Test (No Installation)

Check that data loads correctly:

```bash
cd commodities-intelligence
python -c "
from src import fetch
data = fetch.load_internal_data()
print(f'Loaded {len(data)} rows: {data.columns.tolist()}')
print(f'Date range: {data[\"Date\"].min()} to {data[\"Date\"].max()}')
"
```

Expected output:
```
Loaded 7465 rows: ['Date', 'Brent', 'WTI', 'Natural_Gas', 'AUD_USD']
Date range: 1997-01-07 00:00:00 to 2026-06-15 00:00:00
```

## Full Setup (30-60 min on first run)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. First data refresh (trains initial model)
```bash
python refresh.py
```

This will:
- Fetch data from your 3 repos (oil, gas, exchange rates)
- Try to load external data (VIX, USD Index — no keys required)
- Train LSTM model on 7,465 days of history (will take 10-20 min)
- Generate 90-day forecasts
- Save outputs to `data/` folder

### 3. Launch dashboard
```bash
streamlit run app.py
```

Opens at http://localhost:8501

### 4. Set up automation (optional)

**Linux/Mac:**
```bash
crontab -e

# Add this line (daily at 6 AM)
0 6 * * * cd /path/to/commodities-intelligence && python refresh.py
```

**Windows:**
- Use Task Scheduler to run `python refresh.py` daily

## File Structure (After First Run)

```
commodities-intelligence/
├── data/                    # Generated (NOT in git)
│   ├── merged_data.csv     # All historical data (7K+ rows)
│   ├── forecasts.csv       # 90-day forecasts
│   ├── correlations.csv    # Correlation matrix
│   └── metrics.csv         # Data quality metrics
├── models/                  # Generated (NOT in git)
│   └── lstm_model_20260620.h5  # Trained weights
├── logs/                    # Generated (NOT in git)
│   └── refresh.log         # Daily refresh logs
├── src/                     # Source code
│   ├── fetch.py            # Load from 3 repos
│   ├── external_sources.py # Fetch macro data
│   ├── preprocess.py       # Normalize & sequence
│   └── forecast.py         # LSTM model
├── notebooks/
│   └── analysis.ipynb      # Methodology walkthrough
├── app.py                  # Streamlit dashboard
├── refresh.py              # Daily orchestration script
└── README.md               # Full documentation
```

## Architecture Decision Points

### Why LSTM?
- Handles multivariate time-series (4 outputs) naturally
- Learns correlations automatically
- 60-day lookback balances temporal depth with noise
- 90-day horizon aligns with corporate budgeting cycles

### Why Weekly Retraining?
- Balance: fresh data without instability
- Easy to debug (timestamp each model)
- Can revert if accuracy drops

### Why Quantile Regression?
- Point forecast alone is risky for hedging
- 80% confidence interval reflects uncertainty
- Lets corporate hedgers plan hedging around range, not single number

## Performance Notes

- **Data loading:** ~2 seconds
- **Training (first run):** ~10-20 min on CPU (faster with GPU)
- **Daily refresh:** ~5 min (no retraining)
- **Dashboard load:** <1 second (uses cached CSVs)

## Troubleshooting

### "ModuleNotFoundError: No module named 'tensorflow'"
```bash
pip install tensorflow
```

### "No such file or directory" when loading oil/gas/exchange
Make sure your 3 repos are in `C:\Users\henry\Desktop\github\`:
- `oil-prices/data/brent-daily.csv`
- `natural-gas/data/daily.csv`
- `exchange-rates/data/daily.csv`

### Training is slow
- Normal on CPU. Grab coffee ☕
- GPU: install `tensorflow[and-cuda]` instead
- Can interrupt with Ctrl+C and resume later (model will retrain)

### VIX/Fed data not loading
No error — just optional. Requires FRED API key for Fed data:
```bash
export FRED_API_KEY="your_key_here"
python refresh.py
```

Get key free at: https://fred.stlouisfed.org/docs/api/fred/

## Next Steps

1. **Run `python refresh.py`** to train the model
2. **Launch dashboard** with `streamlit run app.py`
3. **Check forecast quality** — does it match your intuition?
4. **Set up daily refresh** (cron/Task Scheduler)
5. **Use forecasts** in your hedging decisions

## Questions?

- See `README.md` for detailed methodology
- Check `notebooks/analysis.ipynb` for walkthrough
- Logs in `logs/refresh.log` for debug info

---

**You're ready to go!** Next step: `python refresh.py`
