"""
Commodities & Cross-Asset Intelligence - Streamlit dashboard.

Two layers of analysis:
  - FAST (daily): how tradeable assets - oil, gas, FX, equities, gold, VIX -
    co-move day to day (returns-based correlation, R^2, regression).
  - MACRO (annual): how the slow forces - money supply, rates, inflation,
    credit, growth, debt, the dollar - drive markets, with the transmission
    mechanism spelled out for each.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from src import stats_analysis as sa
from src import catalog

st.set_page_config(page_title="Cross-Asset Intelligence", page_icon="📈", layout="wide")
DATA_DIR = Path(__file__).parent / "data"

label = catalog.label


@st.cache_data
def load_data():
    def rd(name, **kw):
        p = DATA_DIR / name
        return pd.read_csv(p, **kw) if p.exists() else None
    merged = rd("merged_data.csv")
    if merged is None:
        return None, None, None, None
    merged["Date"] = pd.to_datetime(merged["Date"])
    forecasts = rd("forecasts.csv")
    if forecasts is not None and "Date" in forecasts.columns:
        forecasts["Date"] = pd.to_datetime(forecasts["Date"])
    macro = rd("macro_relationships.csv")
    metrics = rd("metrics.csv")
    metrics = metrics.iloc[0].to_dict() if metrics is not None else {}
    return merged, forecasts, macro, metrics


merged, forecasts, macro_rel, metrics = load_data()

st.title("📈 Cross-Asset Commodities Intelligence")
st.caption("What moves oil, gas, the Australian dollar and the stock market — and *why* — "
           "with full history and proper statistics.")

if merged is None:
    st.warning("No data found. Run `python refresh.py` first.")
    st.stop()

PRESENT = list(merged.columns)
ASSETS = catalog.asset_columns(PRESENT)
MACRO = catalog.macro_columns(PRESENT)
DRIVERS = catalog.driver_columns(PRESENT)  # macro + copper/China as drivers
TRANSFORMS = catalog.transforms_map(PRESENT)
span = f"{merged['Date'].min().date()} → {merged['Date'].max().date()}"

st.sidebar.header("View")
if st.sidebar.button("↻ Reload data", help="Clear the cache and re-read the latest data files"):
    st.cache_data.clear()
    st.rerun()
view = st.sidebar.radio("Section", [
    "Overview", "What Moves Markets", "Macro Drivers", "Multi-Factor Model",
    "Correlation Lab", "Rolling Correlation", "Price Explorer", "Forecasts",
])
st.sidebar.markdown("---")
st.sidebar.caption(f"Data span: {span} · {len(ASSETS)} assets · {len(MACRO)} macro drivers")


def sig_stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


# ============================================================ OVERVIEW
if view == "Overview":
    def pct_change(col, days):
        s = merged[col].dropna()
        if len(s) <= days:
            return np.nan
        return (s.iloc[-1] / s.iloc[-days] - 1) * 100

    # ---- hero KPIs ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("History", span)
    k2.metric("Trading days", f"{len(merged):,}")
    k3.metric("Tradeable assets", len(ASSETS))
    k4.metric("Macro drivers", len(MACRO))

    st.divider()

    # ---- movers bar (the headline graph; switchable horizon) ----
    hcol1, hcol2, hcol3 = st.columns([3, 1.1, 0.9])
    hcol1.markdown("#### Asset performance")
    horizon = hcol2.radio("Window", ["1 month", "1 year"], horizontal=True,
                          label_visibility="collapsed")
    logmag = hcol3.toggle("Log", value=False,
                          help="Plot the SIZE of each move on a log scale (colour shows direction). "
                               "Useful when a few big movers dominate the linear view.")
    days = 22 if horizon == "1 month" else 252
    # round to 2 dp up front so labels never show excess precision
    movers = [(label(c), round(v, 2)) for c in ASSETS if pd.notna(v := pct_change(c, days))]
    if movers:
        mv = pd.DataFrame(movers, columns=["Asset", "chg"])
        if logmag:
            mv["mag"] = mv["chg"].abs().clip(lower=0.01)
            mv["Direction"] = np.where(mv["chg"] >= 0, "up", "down")
            mv = mv.sort_values("mag")
            fig = px.bar(mv, x="mag", y="Asset", orientation="h", color="Direction",
                         color_discrete_map={"up": "#2e9e5b", "down": "#d24b4b"}, text="chg")
            fig.update_xaxes(type="log", title="size of move, % (log scale)")
            fig.update_layout(showlegend=False)
        else:
            mv = mv.sort_values("chg")
            lim = max(abs(mv["chg"]).max(), 5)
            fig = px.bar(mv, x="chg", y="Asset", orientation="h", color="chg",
                         color_continuous_scale="RdYlGn", range_color=[-lim, lim], text="chg")
            fig.update_xaxes(title=f"% change ({horizon})")
            fig.update_layout(coloraxis_showscale=False)
        fig.update_traces(texttemplate="%{text:+.2f}%", textposition="outside", cliponaxis=False,
                          hovertemplate="%{y}: %{text:+.2f}%<extra></extra>")
        fig.update_layout(height=400, yaxis_title="", margin=dict(l=10, r=55, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- asset cards: latest level + coloured 1mo / 1yr % change ----
    st.markdown("#### Markets — latest level & change")
    groups = {}
    for col in ASSETS:
        groups.setdefault(catalog.theme(col), []).append(col)
    for grp in catalog.THEME_ORDER:
        cols = groups.get(grp, [])
        if not cols:
            continue
        st.markdown(f"**{grp}**")
        cards = st.columns(min(len(cols), 4))
        for i, col in enumerate(cols):
            s = merged[col].dropna()
            if s.empty:
                continue
            c = cards[i % 4]
            val = s.iloc[-1]
            fmt = f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"
            m, y = pct_change(col, 22), pct_change(col, 252)
            # 1-month change as the native metric delta (auto green/red)
            c.metric(label(col), fmt, f"{m:+.1f}% 1mo" if pd.notna(m) else None)
            # 1-year change as a separate colour-coded line
            if pd.notna(y):
                clr = "green" if y >= 0 else "red"
                c.markdown(f":{clr}[{y:+.0f}% 1yr]")
        st.write("")

    st.divider()

    # ---- macro snapshot (tucked away; latest + 1-year change) ----
    with st.expander("Macro drivers snapshot — latest & 1-year change", expanded=False):
        mgroups = {}
        for col in MACRO:
            mgroups.setdefault(catalog.theme(col), []).append(col)
        for grp in catalog.THEME_ORDER:
            cols = mgroups.get(grp, [])
            if not cols:
                continue
            st.markdown(f"**{grp}**")
            cards = st.columns(min(len(cols), 4))
            for i, col in enumerate(cols):
                s = merged[col].dropna()
                if s.empty:
                    continue
                val = s.iloc[-1]
                fmt = f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"
                y = pct_change(col, 252)
                cards[i % 4].metric(label(col), fmt, f"{y:+.0f}% 1yr" if pd.notna(y) else None)
            st.write("")

    st.info("Next: **What Moves Markets** for the big-picture map of which forces drive each asset, "
            "then **Macro Drivers** and **Multi-Factor Model** to drill in. "
            "See `ANALYSIS_AUSTRALIA.md` in the repo for the Australia deep-dive.")

# ============================================================ WHAT MOVES MARKETS
elif view == "What Moves Markets":
    st.subheader("What moves markets — the big picture")
    st.markdown(
        "Each cell is the **R²** (0–1) of a macro *theme* against an asset, measured on "
        "annual-horizon changes: how much of that asset's yearly moves the theme explains. "
        "Darker = stronger. This is the map; use **Macro Drivers** to drill into the individual series."
    )
    if macro_rel is None:
        st.warning("Run `python refresh.py` to generate macro relationships.")
    else:
        # Aggregate driver R² to theme level (max R² within theme = its strongest channel)
        mr = macro_rel.copy()
        mr["Theme"] = mr["Driver"].map(catalog.theme)
        pivot = (mr.groupby(["Target", "Theme"])["R2"].max().reset_index()
                 .pivot(index="Target", columns="Theme", values="R2"))
        # order rows by asset theme, cols by THEME_ORDER
        row_order = [a for a in ASSETS if a in pivot.index]
        col_order = [t for t in catalog.THEME_ORDER if t in pivot.columns]
        pivot = pivot.loc[row_order, col_order]
        disp = pivot.copy()
        disp.index = [label(a) for a in pivot.index]
        fig = px.imshow(disp, color_continuous_scale="Viridis", text_auto=".2f",
                        aspect="auto", zmin=0, zmax=float(np.nanmax(pivot.values)))
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10),
                          coloraxis_colorbar=dict(title="R²"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Read across a row to see which forces dominate that asset. Equities are driven by "
                   "credit/risk & inflation expectations; oil by inflation, growth and the dollar; "
                   "gold by rates and the dollar.")

# ============================================================ MACRO DRIVERS
elif view == "Macro Drivers":
    st.subheader("Macro Drivers — what drives a chosen asset, and why")
    st.caption("Annual-horizon relationship (12-month changes, sampled monthly). Note: overlapping "
               "windows make p-values mildly optimistic — read significance as a guide, not gospel.")
    tgt = st.selectbox("Asset", ASSETS,
                       index=ASSETS.index("SP500") if "SP500" in ASSETS else 0, format_func=label)

    if macro_rel is not None:
        tbl = macro_rel[macro_rel["Target"] == tgt].copy()
    else:
        tbl = sa.macro_relationship_table(merged, tgt, DRIVERS, TRANSFORMS, horizon=12)
        tbl["Theme"] = tbl["Driver"].map(catalog.theme)
        tbl["Mechanism"] = tbl["Driver"].map(catalog.mechanism)
    tbl = tbl.sort_values("R2", ascending=False).reset_index(drop=True)

    left, right = st.columns([3, 2])
    with left:
        top = tbl.head(10)
        fig = px.bar(top, x="R2", y=top["Driver"].map(label), orientation="h",
                     color="Correlation", color_continuous_scale="RdBu_r", range_color=[-1, 1])
        fig.update_layout(height=440, yaxis=dict(autorange="reversed"),
                          xaxis_title="R² (variance explained)", yaxis_title="",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown(f"**Top channels for {label(tgt)}**")
        for _, r in tbl.head(5).iterrows():
            st.markdown(f"- **{label(r['Driver'])}** (r={r['Correlation']:+.2f}, R²={r['R2']:.2f}) — "
                        f"{catalog.mechanism(r['Driver'])}")

    show = tbl.copy()
    show["Driver"] = show["Driver"].map(label)
    show["Sig"] = tbl["P_Value"].map(sig_stars)
    show = show.rename(columns={"R2": "R²", "Beta": "Beta", "P_Value": "p", "N": "Months"})
    for c in ["Correlation", "R²", "Beta"]:
        show[c] = show[c].round(3)
    show["p"] = show["p"].map(lambda v: f"{v:.1e}" if pd.notna(v) else "")
    st.dataframe(show[["Driver", "Theme", "Correlation", "R²", "Beta", "p", "Sig", "Months"]],
                 use_container_width=True, hide_index=True)
    st.caption("Beta = average move in the asset's annual change per 1-unit change in the driver. "
               "Significance: *** p<0.01, ** p<0.05, * p<0.10.")

# ============================================================ MULTI-FACTOR MODEL
elif view == "Multi-Factor Model":
    st.subheader("Multi-Factor Model — drivers working together")
    st.markdown(
        "No single factor moves a market on its own. This fits one **multivariate "
        "regression** per asset: every driver's effect is measured *holding the others "
        "constant*. Inputs are standardised, so the **β** columns are directly comparable "
        "(move in the asset, in std deviations, per 1 std-dev move in the driver)."
    )
    tgt = st.selectbox("Asset", ASSETS,
                       index=ASSETS.index("SP500") if "SP500" in ASSETS else 0, format_func=label)
    default_drivers = [d for d in catalog.REPRESENTATIVE_DRIVERS if d in DRIVERS]
    chosen = st.multiselect(
        "Drivers in the model (one per theme avoids multicollinearity)",
        DRIVERS, default=default_drivers, format_func=label)

    if len(chosen) >= 2:
        coef, summ = sa.multi_regression_monthly(merged, tgt, chosen, TRANSFORMS, horizon=12)
        inc = sa.incremental_r2(merged, tgt, chosen, TRANSFORMS, horizon=12)

        m1, m2, m3 = st.columns(3)
        m1.metric("Combined R²", f"{summ['r2']:.2f}",
                  help="Share of the asset's annual moves explained by all drivers together.")
        m2.metric("Best single factor",
                  f"{summ['best_single_r2']:.2f}" if summ['best_single_r2'] == summ['best_single_r2'] else "n/a",
                  help=f"{label(summ['best_single']) if summ['best_single'] else ''} alone")
        lift = (summ['r2'] - summ['best_single_r2']) if summ['best_single_r2'] == summ['best_single_r2'] else float('nan')
        m3.metric("Lift from combining", f"+{lift:.2f}", help="Extra R² beyond the single best factor.")

        cL, cR = st.columns(2)
        with cL:
            st.markdown("**Standardised coefficients** (effect holding others constant)")
            c2 = coef.copy()
            c2["Driver"] = c2["Driver"].map(label)
            c2["Sig"] = coef["P_Value"].map(sig_stars)
            c2 = c2.rename(columns={"Std_Beta": "β", "T_Stat": "t", "P_Value": "p"})
            for col in ["β", "t", "VIF"]:
                c2[col] = c2[col].round(2)
            c2["p"] = c2["p"].map(lambda v: f"{v:.1e}" if pd.notna(v) else "")
            st.dataframe(c2[["Driver", "β", "t", "p", "Sig", "VIF"]],
                         use_container_width=True, hide_index=True)
            st.caption("β bars below. VIF > 5 flags a driver that overlaps heavily with the others "
                       "(its individual coefficient becomes unreliable). Sig: *** p<0.01, ** <0.05, * <0.10.")
            figb = px.bar(coef.sort_values("Std_Beta"), x="Std_Beta",
                          y=coef.sort_values("Std_Beta")["Driver"].map(label),
                          orientation="h", color="Std_Beta",
                          color_continuous_scale="RdBu_r", range_color=[-1, 1])
            figb.update_layout(height=300, yaxis_title="", xaxis_title="standardised β",
                               margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(figb, use_container_width=True)
        with cR:
            st.markdown("**How explanatory power builds up**")
            if not inc.empty:
                inc2 = inc.copy()
                inc2["lbl"] = inc2["driver"].map(label)
                figi = go.Figure()
                figi.add_trace(go.Scatter(x=list(range(1, len(inc2) + 1)), y=inc2["cumulative_r2"],
                                          mode="lines+markers", line=dict(color="#4a8fd2", width=3),
                                          fill="tozeroy", name="cumulative R²"))
                figi.update_layout(height=340, yaxis_range=[0, 1], yaxis_title="cumulative R²",
                                   xaxis=dict(tickmode="array", tickvals=list(range(1, len(inc2) + 1)),
                                              ticktext=[f"+{t[:14]}" for t in inc2["lbl"]], tickangle=-35),
                                   margin=dict(l=10, r=10, t=10, b=90))
                st.plotly_chart(figi, use_container_width=True)
                st.caption("Drivers added strongest-first. The first bar is the best single factor; "
                           "each step adds what the others miss — note the diminishing returns.")
        st.info(f"**Read-out for {label(tgt)}:** the single best factor explains "
                f"{summ['best_single_r2']*100:.0f}% of annual moves; together the {len(chosen)} drivers "
                f"explain {summ['r2']*100:.0f}%. That gap is the multi-factor reality — markets are moved "
                "by a *combination* of forces, and some single-factor correlations shrink once you control "
                "for the rest.")
    else:
        st.info("Pick at least two drivers.")

# ============================================================ PRICE EXPLORER
elif view == "Price Explorer":
    st.subheader("Price Explorer")
    pick = st.multiselect("Series", ASSETS + MACRO,
                          default=[c for c in ["Brent", "SP500", "Gold"] if c in ASSETS],
                          format_func=label)
    a, b, c = st.columns(3)
    rebased = a.toggle("Rebase to 100", value=len(pick) > 1)
    logy = b.toggle("Log scale", value=False)
    max_years = int((merged['Date'].max() - merged['Date'].min()).days / 365) + 1
    years = c.slider("Years", 1, max_years, value=min(15, max_years))
    win = merged[merged["Date"] >= merged["Date"].max() - pd.Timedelta(days=365 * years)]
    if pick:
        fig = go.Figure()
        for col in pick:
            s = win[["Date", col]].dropna()
            y = s[col]
            if rebased and len(y):
                y = y / y.iloc[0] * 100
            fig.add_trace(go.Scatter(x=s["Date"], y=y, name=label(col), mode="lines"))
        fig.update_layout(height=620, hovermode="x unified",
                          yaxis_title="Indexed to 100" if rebased else "Level",
                          yaxis_type="log" if logy else "linear",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02),
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ============================================================ CORRELATION LAB
elif view == "Correlation Lab":
    st.subheader("Correlation Lab (daily, tradeable assets)")
    use = st.radio("Measure on", ["returns", "levels"], horizontal=True,
                   format_func=lambda x: "Daily returns (recommended)" if x == "returns" else "Price levels (illustrative)")
    if use == "levels":
        st.warning("Levels correlation is inflated by shared trends — illustrative only.")
    pick = st.multiselect("Assets", ASSETS, default=ASSETS, format_func=label)
    if len(pick) >= 2:
        corr = sa.correlation_matrix(merged, pick, use=use)
        disp = corr.copy(); disp.index = disp.columns = [label(c) for c in pick]
        t1, t2 = st.tabs(["Correlation", "R²"])
        with t1:
            fig = px.imshow(disp, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, text_auto=".2f", aspect="auto")
            fig.update_layout(height=640, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with t2:
            r2 = disp ** 2
            fig = px.imshow(r2, color_continuous_scale="Blues", zmin=0, zmax=1, text_auto=".2f", aspect="auto")
            fig.update_layout(height=640, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

# ============================================================ ROLLING CORRELATION
elif view == "Rolling Correlation":
    st.subheader("Rolling Correlation")
    st.caption("Correlations are not constant — they strengthen or break down over time.")
    c1, c2, c3 = st.columns(3)
    a = c1.selectbox("Asset A", ASSETS, index=ASSETS.index("Brent") if "Brent" in ASSETS else 0, format_func=label)
    b = c2.selectbox("Asset B", ASSETS, index=ASSETS.index("SP500") if "SP500" in ASSETS else 1, format_func=label)
    window = c3.select_slider("Window (days)", [30, 60, 90, 120, 180, 252], value=90)
    if a != b:
        roll = sa.rolling_correlation(merged, a, b, window=window, use="returns")
        full = sa.pair_regression(merged, a, b, use="returns")
        avg = np.sign(full["slope"]) * np.sqrt(full["r2"])
        fig = go.Figure(go.Scatter(x=roll["Date"], y=roll["correlation"], mode="lines", name=f"{window}d"))
        fig.add_hline(y=0, line_dash="dot", line_color="gray")
        fig.add_hline(y=avg, line_dash="dash", line_color="orange", annotation_text="full-sample avg")
        fig.update_layout(height=540, yaxis_range=[-1, 1], hovermode="x unified",
                          yaxis_title="Correlation", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Full-sample correlation", f"{avg:+.2f}", help=f"R²={full['r2']:.3f}, n={full['n']:,}")

# ============================================================ FORECASTS
elif view == "Forecasts":
    st.subheader("90-Day Forecasts")
    if forecasts is None or forecasts.empty:
        st.info("No forecasts found. Run `python refresh.py`.")
    else:
        targets = [c for c in ["Brent", "WTI", "Natural_Gas", "AUD_USD"] if c in forecasts.columns]
        pick = st.multiselect("Series", targets, default=["Brent"], format_func=label)
        hist_days = st.slider("Days of history", 60, 730, 250)
        for col in pick:
            hist = merged[["Date", col]].dropna().tail(hist_days)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist["Date"], y=hist[col], name="history", mode="lines"))
            if "Date" in forecasts.columns:
                fig.add_trace(go.Scatter(x=forecasts["Date"], y=forecasts[col], name="forecast",
                                         mode="lines", line=dict(dash="dash", color="orange")))
            fig.update_layout(height=420, title=label(col), hovermode="x unified",
                              margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        st.caption("LSTM trained on full commodity history, shown in real units. A model's central path, not a guarantee.")
