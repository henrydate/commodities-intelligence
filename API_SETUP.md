# API Setup Guide

## Quick Start

```bash
python api.py
```

Opens API at `http://localhost:5000/`

---

## API Endpoints

### 1. Health Check
```bash
GET /health
```
Returns API status and data freshness.

**Example:**
```bash
curl http://localhost:5000/health
```

---

### 2. Get Forecasts
```bash
GET /forecast?days=90
```
Get 90-day forecasts for all commodities.

**Example:**
```bash
curl http://localhost:5000/forecast?days=30
```

**Response:**
```json
{
  "horizon_days": 30,
  "commodities": ["Brent", "WTI", "Natural_Gas", "AUD_USD"],
  "forecasts": [
    {"Brent": 95.2, "WTI": 92.1, ...},
    ...
  ]
}
```

---

### 3. Get Specific Commodity
```bash
GET /forecast/<commodity>?days=90
```

**Example:**
```bash
curl http://localhost:5000/forecast/Brent?days=30
```

**Commodities:** Brent, WTI, Natural_Gas, AUD_USD

---

### 4. Historical Data
```bash
GET /historical?days=365&commodity=Brent
```

**Example:**
```bash
curl "http://localhost:5000/historical?days=30&commodity=Brent"
```

---

### 5. Correlation Matrix
```bash
GET /correlations
```

Returns how features move together.

---

### 6. Model Comparison
```bash
GET /compare?days=30
```

Compare LSTM vs Moving Average vs No-Change baselines.

---

### 7. Data Metrics
```bash
GET /metrics
```

Data quality, refresh date, completeness.

---

## Integration Examples

### Python
```python
import requests

# Get Brent forecast
resp = requests.get("http://localhost:5000/forecast/Brent?days=30")
forecasts = resp.json()

for day in forecasts["forecast"]:
    print(f"Day {day['Day_Ahead']}: {day['price']:.2f}")
```

### JavaScript
```javascript
fetch('http://localhost:5000/forecast/Brent?days=30')
  .then(r => r.json())
  .then(data => {
    data.forecast.forEach(day => {
      console.log(`Day ${day.Day_Ahead}: $${day.price.toFixed(2)}`);
    });
  });
```

### Excel/Power BI
1. Get Data → Web
2. Enter: `http://localhost:5000/forecast?days=90`
3. Load into spreadsheet

---

## Free External Data Sources

### 1. FRED (Federal Reserve)
Get real Fed Funds Rate, Treasury spreads, unemployment.

**Setup:**
1. Register at https://fred.stlouisfed.org/docs/api/fred/
2. Get free API key
3. Set environment variable:
   ```bash
   export FRED_API_KEY="your_key_here"
   ```
4. Restart `refresh.py`

**Series available:**
- `DFF`: Federal Funds Rate
- `T10Y2Y`: 10Y-2Y Treasury Spread
- `UNRATE`: Unemployment Rate

---

### 2. EIA (Energy Info Admin)
Get crude oil inventory, supply/demand data.

**Setup:**
1. Register at https://www.eia.gov/opendata/
2. Get free API key
3. Set environment variable:
   ```bash
   export EIA_API_KEY="your_key_here"
   ```

**Data available:**
- Weekly crude inventory
- Production, imports, refinery runs

---

### 3. RBA (Reserve Bank Australia)
Official Australian cash rate and inflation data.

**Setup:**
- Public data available at https://www.rba.gov.au/statistics/
- No API key needed
- Can be integrated via scraping or manual updates

**Data available:**
- Official Cash Rate (OCR)
- Inflation rate (CPI)
- Exchange rate decisions

---

## Deployment

### Docker
```dockerfile
FROM python:3.9
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "api.py"]
```

### Heroku
```bash
heroku create your-app-name
git push heroku main
heroku config:set FRED_API_KEY="your_key"
```

### AWS Lambda
Use AWS API Gateway + Lambda to wrap `api.py`

---

## Monitoring

Check data freshness:
```bash
curl http://localhost:5000/health
```

If `Refresh_Date` is stale, run:
```bash
python refresh.py
```

---

## Rate Limiting (Optional)

Add rate limiting for production:
```bash
pip install flask-limiter
```

Then in `api.py`:
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route("/forecast")
@limiter.limit("100 per hour")
def get_forecast():
    ...
```

---

## Questions?

- API docs: `GET /` 
- Health: `GET /health`
- Check logs: `tail -f logs/refresh.log`
