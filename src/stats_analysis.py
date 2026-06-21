"""
Cross-asset statistical analysis: correlation, R-squared, rolling correlation,
and regression betas (with significance).

Design note on a common pitfall
--------------------------------
Correlating raw PRICE LEVELS of two assets is usually misleading. Two trending
series (e.g. oil and the S&P 500) can show a high correlation simply because
both drifted upward over time - this is "spurious" correlation, not a genuine
co-movement. The statistically sound approach for financial series is to
correlate RETURNS (daily percentage changes), which are (close to) stationary.

These functions therefore default to returns, while still exposing levels for
illustration. The dashboard explains the difference to the reader.
"""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available - p-values will be omitted")


# Rate / spread series are NOT prices: they can be zero or negative, so a
# percentage change is undefined or explosive. For these we use the first
# DIFFERENCE (change in level, e.g. +0.25% on the Fed funds rate) instead.
RATE_LIKE = {"Fed_Funds_Rate", "Yield_Curve_10Y2Y", "Unemployment_Rate"}


def numeric_columns(df):
    """Return numeric column names excluding Date."""
    return [c for c in df.select_dtypes(include=[np.number]).columns if c != "Date"]


def to_returns(df, cols=None, method="pct"):
    """
    Convert each series to a stationary daily change.

    - Price-like series -> percentage (or log) return.
    - Rate/spread series (see RATE_LIKE) -> first difference, because a percent
      change of a value that can cross zero is meaningless.

    Returns a DataFrame keeping the Date column. Infinities (from any residual
    divide-by-zero) are coerced to NaN so they don't poison correlations.
    """
    cols = cols or numeric_columns(df)
    out = pd.DataFrame({"Date": df["Date"].values}) if "Date" in df.columns else pd.DataFrame()

    for c in cols:
        s = df[c].astype(float)
        if c in RATE_LIKE:
            change = s.diff()
        elif method == "log":
            change = np.log(s / s.shift(1))
        else:
            change = s.pct_change()
        out[c] = change.replace([np.inf, -np.inf], np.nan).values

    return out


def correlation_matrix(df, cols=None, use="returns", method="pearson"):
    """
    Correlation matrix across assets.

    use="returns": correlate daily returns (recommended).
    use="levels":  correlate raw price levels (shown for contrast only).
    Uses pairwise-complete observations, so assets with shorter history
    (e.g. Gold ETF from 2004) still contribute where data overlaps.
    """
    cols = cols or numeric_columns(df)
    data = to_returns(df, cols) if use == "returns" else df[["Date"] + cols]
    return data[cols].corr(method=method)


def r_squared_matrix(df, cols=None, use="returns"):
    """
    R-squared matrix = squared Pearson correlation.

    R^2 is the share of one asset's variance explained by a linear relationship
    with another (0 = none, 1 = perfectly explained). It is direction-agnostic.
    """
    corr = correlation_matrix(df, cols, use=use)
    return corr ** 2


def rolling_correlation(df, asset_a, asset_b, window=90, use="returns"):
    """
    Rolling (time-varying) correlation between two assets.

    Returns a DataFrame [Date, correlation]. Correlations are not static -
    e.g. oil and equities can decouple in calm markets and spike together in a
    crisis. A rolling window reveals that story.
    """
    data = to_returns(df, [asset_a, asset_b]) if use == "returns" else df[["Date", asset_a, asset_b]]
    roll = data[asset_a].rolling(window).corr(data[asset_b])
    return pd.DataFrame({"Date": data["Date"].values, "correlation": roll.values}).dropna()


def pair_regression(df, x, y, use="returns"):
    """
    Univariate OLS of y on x: y = alpha + beta * x.

    Returns dict with slope (beta/sensitivity), intercept, r2, pvalue, n.
    beta answers "if x moves 1%, how much does y move on average?".
    """
    data = to_returns(df, [x, y]) if use == "returns" else df[["Date", x, y]]
    pair = data[[x, y]].dropna()
    n = len(pair)
    if n < 3:
        return {"slope": np.nan, "intercept": np.nan, "r2": np.nan, "pvalue": np.nan, "n": n}

    xv, yv = pair[x].values, pair[y].values
    if SCIPY_AVAILABLE:
        res = scipy_stats.linregress(xv, yv)
        return {"slope": res.slope, "intercept": res.intercept,
                "r2": res.rvalue ** 2, "pvalue": res.pvalue, "n": n}

    # numpy fallback (no p-value)
    slope, intercept = np.polyfit(xv, yv, 1)
    corr = np.corrcoef(xv, yv)[0, 1]
    return {"slope": slope, "intercept": intercept, "r2": corr ** 2, "pvalue": np.nan, "n": n}


def driver_ranking(df, target, drivers=None, use="returns"):
    """
    Rank how strongly each driver explains a target asset (univariate).

    Returns a DataFrame sorted by R^2 descending, with correlation, R^2, beta,
    p-value and overlap n - the headline "what moves this asset?" table.
    """
    cols = numeric_columns(df)
    drivers = drivers or [c for c in cols if c != target]

    rows = []
    for d in drivers:
        reg = pair_regression(df, d, target, use=use)
        sign = np.sign(reg["slope"]) if not np.isnan(reg["slope"]) else 0
        corr = sign * np.sqrt(reg["r2"]) if not np.isnan(reg["r2"]) else np.nan
        rows.append({
            "Driver": d,
            "Correlation": corr,
            "R2": reg["r2"],
            "Beta": reg["slope"],
            "P_Value": reg["pvalue"],
            "N": reg["n"],
        })

    table = pd.DataFrame(rows).sort_values("R2", ascending=False).reset_index(drop=True)
    return table


def multi_regression(df, target, drivers, use="returns"):
    """
    Multivariate OLS: target ~ b0 + b1*d1 + ... + bk*dk (on returns).

    Returns (coef_table, summary_dict). coef_table has coefficient, t-stat and
    p-value per driver; summary_dict has overall R^2, adjusted R^2 and n.
    Implemented with numpy + scipy so there's no hard statsmodels dependency.
    """
    use_cols = [target] + list(drivers)
    data = to_returns(df, use_cols) if use == "returns" else df[["Date"] + use_cols]
    data = data[use_cols].dropna()
    n = len(data)

    if n <= len(drivers) + 1:
        return pd.DataFrame(), {"r2": np.nan, "adj_r2": np.nan, "n": n}

    y = data[target].values
    X = np.column_stack([np.ones(n)] + [data[d].values for d in drivers])
    k = X.shape[1]  # params incl. intercept

    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k) if not np.isnan(r2) else np.nan

    # Standard errors -> t-stats -> p-values
    names = ["Intercept"] + list(drivers)
    rows = []
    try:
        sigma2 = ss_res / (n - k)
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        tvals = beta / se
        if SCIPY_AVAILABLE:
            pvals = 2 * (1 - scipy_stats.t.cdf(np.abs(tvals), df=n - k))
        else:
            pvals = [np.nan] * k
        for nm, b, t, p in zip(names, beta, tvals, pvals):
            rows.append({"Variable": nm, "Coefficient": b, "T_Stat": t, "P_Value": p})
    except np.linalg.LinAlgError:
        for nm, b in zip(names, beta):
            rows.append({"Variable": nm, "Coefficient": b, "T_Stat": np.nan, "P_Value": np.nan})

    return pd.DataFrame(rows), {"r2": r2, "adj_r2": adj_r2, "n": n}


# =====================================================================
#  Frequency-aware macro analysis
#
#  Macro drivers (M2, debt, GDP, CPI ...) are monthly or quarterly and slow.
#  Comparing their daily % change to markets is meaningless. Instead we resample
#  everything to month-end and convert each series to a stationary change using
#  the transform declared in the catalog, aligned to an annual (12-month)
#  horizon - the timescale at which macro relationships actually show up.
#
#  Caveat surfaced in the UI: 12-month changes sampled monthly overlap, which
#  mildly understates p-values (autocorrelation). Treat significance as a guide.
# =====================================================================

def resample_monthly(df):
    """Resample a daily frame to month-end levels (last observation in month)."""
    d = df.copy()
    d["Date"] = pd.to_datetime(d["Date"])
    indexed = d.set_index("Date")
    try:  # "ME" on pandas >= 2.2, "M" on older versions
        monthly = indexed.resample("ME").last()
    except ValueError:
        monthly = indexed.resample("M").last()
    return monthly.reset_index()


def monthly_changes(df, transforms, horizon=12):
    """
    Convert month-end levels to stationary changes per the catalog transform:
        ret  -> percentage change over `horizon` months
        yoy  -> 12-month percentage change (how these series are always quoted)
        diff -> change in level over `horizon` months
        level-> value as-is
    Expects a month-end frame (see resample_monthly).
    """
    out = pd.DataFrame({"Date": df["Date"].values})
    for c in df.columns:
        if c == "Date":
            continue
        s = df[c].astype(float)
        t = transforms.get(c, "ret")
        if t == "yoy":
            change = s.pct_change(12)
        elif t == "ret":
            change = s.pct_change(horizon)
        elif t == "diff":
            change = s.diff(horizon)
        else:  # level
            change = s
        out[c] = change.replace([np.inf, -np.inf], np.nan).values
    return out


def macro_relationship_table(merged, target, drivers, transforms, horizon=12):
    """
    For each driver, quantify its annual-horizon relationship with the target:
    correlation, R², regression beta and p-value (pairwise-complete, monthly).
    Returned sorted by R² descending - the 'what moves this asset' table.
    """
    monthly = resample_monthly(merged)
    changes = monthly_changes(monthly, transforms, horizon=horizon)

    rows = []
    for d in drivers:
        if d == target or d not in changes.columns:
            continue
        pair = changes[[d, target]].dropna()
        n = len(pair)
        if n < 12:
            continue
        xv, yv = pair[d].values, pair[target].values
        if SCIPY_AVAILABLE:
            res = scipy_stats.linregress(xv, yv)
            corr, r2, beta, p = res.rvalue, res.rvalue ** 2, res.slope, res.pvalue
        else:
            corr = np.corrcoef(xv, yv)[0, 1]
            beta = np.polyfit(xv, yv, 1)[0]
            r2, p = corr ** 2, np.nan
        rows.append({"Driver": d, "Correlation": corr, "R2": r2,
                     "Beta": beta, "P_Value": p, "N": n})

    return pd.DataFrame(rows).sort_values("R2", ascending=False).reset_index(drop=True)


def _ols(y, X):
    """Plain OLS via lstsq. Returns beta, r2, adj_r2, t-stats, p-values, n, k."""
    n, k = X.shape
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    adj = 1 - (1 - r2) * (n - 1) / (n - k) if n > k else np.nan
    try:
        cov = (ss_res / (n - k)) * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        t = beta / se
        p = 2 * (1 - scipy_stats.t.cdf(np.abs(t), df=n - k)) if SCIPY_AVAILABLE else [np.nan] * k
    except np.linalg.LinAlgError:
        t = [np.nan] * k
        p = [np.nan] * k
    return beta, r2, adj, t, p, n, k


def _vif(Xs):
    """Variance inflation factor for each standardized driver column."""
    n, m = Xs.shape
    vifs = []
    for j in range(m):
        others = np.delete(Xs, j, axis=1)
        Xo = np.column_stack([np.ones(n), others])
        b, _, _, _ = np.linalg.lstsq(Xo, Xs[:, j], rcond=None)
        resid = Xs[:, j] - Xo @ b
        ss_res = float(resid @ resid)
        ss_tot = float(((Xs[:, j] - Xs[:, j].mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        vifs.append(1.0 / (1.0 - r2) if r2 < 0.9999 else np.inf)
    return vifs


def multi_regression_monthly(merged, target, drivers, transforms, horizon=12):
    """
    Multivariate OLS at annual horizon: how do drivers JOINTLY explain an asset,
    each effect measured holding the others constant?

    Inputs are standardised (z-scored), so coefficients are 'standardised betas'
    (std-dev move in the asset per 1 std-dev move in the driver) and are directly
    comparable across drivers. Also returns each driver's VIF (multicollinearity:
    >5 means it overlaps heavily with the others) and the best SINGLE-factor R²
    for contrast with the combined R².

    Returns (coef_table, summary_dict).
    """
    monthly = resample_monthly(merged)
    changes = monthly_changes(monthly, transforms, horizon=horizon)
    use = [target] + [d for d in drivers if d in changes.columns and d != target]
    data = changes[use].dropna()
    n = len(data)
    drv = use[1:]

    if n <= len(drv) + 2 or len(drv) == 0:
        return pd.DataFrame(), {"r2": np.nan, "adj_r2": np.nan, "n": n,
                                "best_single_r2": np.nan, "best_single": None}

    y = data[target].values.astype(float)
    Xraw = data[drv].values.astype(float)
    ys = (y - y.mean()) / y.std(ddof=0)
    Xs = (Xraw - Xraw.mean(axis=0)) / Xraw.std(axis=0, ddof=0)

    X = np.column_stack([np.ones(n), Xs])
    beta, r2, adj, t, p, _, _ = _ols(ys, X)
    vifs = _vif(Xs)

    # best single-factor R² among the same drivers (univariate, same sample)
    best_r2, best_name = -1, None
    for j, d in enumerate(drv):
        rj = np.corrcoef(Xs[:, j], ys)[0, 1] ** 2
        if rj > best_r2:
            best_r2, best_name = rj, d

    coef = pd.DataFrame({
        "Driver": drv,
        "Std_Beta": beta[1:],
        "T_Stat": t[1:] if len(t) == len(drv) + 1 else [np.nan] * len(drv),
        "P_Value": p[1:] if len(p) == len(drv) + 1 else [np.nan] * len(drv),
        "VIF": vifs,
    }).sort_values("Std_Beta", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)

    return coef, {"r2": r2, "adj_r2": adj, "n": n,
                  "best_single_r2": best_r2, "best_single": best_name}


def incremental_r2(merged, target, drivers, transforms, horizon=12):
    """
    Forward build-up of explanatory power: order drivers by univariate strength,
    then add them one at a time and record the model's cumulative R².

    Shows directly that no single factor explains the asset - explanatory power
    accumulates as covariates are combined (with diminishing returns).
    Returns DataFrame [step, driver, cumulative_r2, marginal_r2].
    """
    monthly = resample_monthly(merged)
    changes = monthly_changes(monthly, transforms, horizon=horizon)
    use = [target] + [d for d in drivers if d in changes.columns and d != target]
    data = changes[use].dropna()
    n = len(data)
    drv = use[1:]
    if n <= len(drv) + 2 or not drv:
        return pd.DataFrame(columns=["step", "driver", "cumulative_r2", "marginal_r2"])

    y = data[target].values.astype(float)
    ys = (y - y.mean()) / y.std(ddof=0)
    Z = {d: (data[d].values - data[d].values.mean()) / data[d].values.std(ddof=0) for d in drv}

    ranked = sorted(drv, key=lambda d: np.corrcoef(Z[d], ys)[0, 1] ** 2, reverse=True)

    rows, prev = [], 0.0
    for i, d in enumerate(ranked, 1):
        cols = ranked[:i]
        X = np.column_stack([np.ones(n)] + [Z[c] for c in cols])
        _, r2, _, _, _, _, _ = _ols(ys, X)
        rows.append({"step": i, "driver": d, "cumulative_r2": r2, "marginal_r2": r2 - prev})
        prev = r2
    return pd.DataFrame(rows)


def lead_lag(merged, driver, target, transforms, max_lag=12, horizon=12):
    """
    Cross-correlation of driver vs target across monthly lags.

    Positive lag = the DRIVER leads the target (driver shifted forward in time),
    i.e. today's driver value lines up with the target `lag` months LATER -
    the signature of a leading indicator.
    Returns DataFrame [lag, correlation].
    """
    monthly = resample_monthly(merged)
    changes = monthly_changes(monthly, transforms, horizon=horizon)
    if driver not in changes.columns or target not in changes.columns:
        return pd.DataFrame(columns=["lag", "correlation"])

    base = changes[[driver, target]].copy()
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        shifted = base[driver].shift(lag)
        pair = pd.concat([shifted, base[target]], axis=1).dropna()
        if len(pair) >= 12:
            rows.append({"lag": lag, "correlation": pair.iloc[:, 0].corr(pair.iloc[:, 1])})
    return pd.DataFrame(rows)
