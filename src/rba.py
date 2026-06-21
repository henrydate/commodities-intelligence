"""
Fetch Reserve Bank of Australia (RBA) statistics from their free CSV tables.

The RBA publishes machine-readable CSVs at rba.gov.au/statistics/tables/csv/.
Each file has a metadata block (Title, Description, Frequency, ... , Series ID)
followed by dated rows. We locate the 'Series ID' row to map each column to its
code (e.g. FIRMMCRT = cash rate target, FCMYGBAG10D = 10Y govt bond) and read
the dated values beneath it.
"""

import csv
import io
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE = "https://www.rba.gov.au/statistics/tables/csv/{table}-data.csv"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_rba_series(table, series_id):
    """
    Fetch a single RBA series as a [Date, series_id] DataFrame.

    table:     RBA table code, e.g. 'f1.1', 'f2', 'g1', 'f11.1'
    series_id: RBA series code, e.g. 'FIRMMCRT'
    """
    try:
        url = BASE.format(table=table)
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        text = resp.content.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))

        # Find the 'Series ID' row and the column holding our series code
        col = None
        for r in rows:
            if r and r[0].strip() == "Series ID":
                for j, code in enumerate(r):
                    if code.strip() == series_id:
                        col = j
                        break
                break
        if col is None:
            logger.warning(f"RBA {table}: series {series_id} not found")
            return pd.DataFrame()

        dates, vals = [], []
        for r in rows:
            if not r or len(r) <= col:
                continue
            d = pd.to_datetime(r[0].strip(), dayfirst=True, errors="coerce")
            if pd.isna(d):
                continue  # skip metadata / blank rows
            v = pd.to_numeric(r[col].strip(), errors="coerce")
            if pd.notna(v):
                dates.append(d.normalize())
                vals.append(v)

        if not dates:
            logger.warning(f"RBA {table}/{series_id}: no data rows parsed")
            return pd.DataFrame()

        df = pd.DataFrame({"Date": dates, series_id: vals}).sort_values("Date")
        df = df.drop_duplicates(subset="Date")
        logger.info(f"Fetched RBA {series_id} ({table}): {len(df)} rows, "
                    f"{df['Date'].min().date()} -> {df['Date'].max().date()}")
        return df

    except Exception as e:
        logger.warning(f"RBA fetch failed for {table}/{series_id}: {e}")
        return pd.DataFrame()
