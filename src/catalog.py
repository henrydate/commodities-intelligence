"""
Central catalog of every series in the system: tradeable assets and macro
drivers alike. One source of truth for:

  - display label and theme (grouping)
  - where it comes from (local repo / Yahoo / FRED) and the fetch id
  - the FREQUENCY of the raw data (D/W/M/Q)
  - the correct STATISTICAL TRANSFORM for stationarity:
        ret   = period percentage return   (tradeable prices)
        yoy   = year-over-year % change     (slow nominal levels: M2, CPI, debt)
        diff  = period change in level      (rates, spreads, ratios already in %)
        level = use the value as-is         (standardized indices, e.g. NFCI)
  - 'class': 'asset' (fast, daily-tradeable) vs 'macro' (a driver)
  - 'mechanism': plain-English reason it moves markets, with expected direction

Using the right transform per series is what makes the cross-frequency analysis
honest: taking a daily % change of a forward-filled quarterly debt series would
manufacture noise, so quarterly levels use year-over-year or period differences
measured at monthly frequency instead.
"""

# colname -> metadata
CATALOG = {
    # ---------------- Tradeable assets (daily, analysed on returns) ----------
    "Brent": dict(label="Brent Crude (USD/bbl)", theme="Commodities", source="repo",
                  fred=None, yahoo=None, freq="D", transform="ret", cls="asset",
                  mechanism="Global oil benchmark; set by supply (OPEC) vs demand (growth)."),
    "WTI": dict(label="WTI Crude (USD/bbl)", theme="Commodities", source="repo",
                fred=None, yahoo=None, freq="D", transform="ret", cls="asset",
                mechanism="US oil benchmark; tracks Brent with a regional spread."),
    "Natural_Gas": dict(label="Natural Gas (USD/MMBtu)", theme="Commodities", source="repo",
                        fred=None, yahoo=None, freq="D", transform="ret", cls="asset",
                        mechanism="Largely idiosyncratic: weather, storage and US supply driven."),
    "AUD_USD": dict(label="AUD/USD", theme="FX", source="repo",
                    fred=None, yahoo=None, freq="D", transform="ret", cls="asset",
                    mechanism="A 'risk/commodity currency'; rises with global growth and commodity demand."),
    "DXY": dict(label="US Dollar Index (DXY)", theme="FX", source="yahoo",
                fred=None, yahoo="DX-Y.NYB", freq="D", transform="ret", cls="asset",
                mechanism="USD vs major peers; a strong dollar is a headwind for dollar-priced commodities."),
    "SP500": dict(label="S&P 500", theme="Equities", source="yahoo",
                  fred=None, yahoo="^GSPC", freq="D", transform="ret", cls="asset",
                  mechanism="Global risk benchmark; discounts future earnings at prevailing rates."),
    "ASX200": dict(label="ASX 200", theme="Equities", source="yahoo",
                   fred=None, yahoo="^AXJO", freq="D", transform="ret", cls="asset",
                   mechanism="Australian market; heavy in miners/banks, tied to commodities and China."),
    "Energy_Equities": dict(label="Energy Equities (XLE)", theme="Equities", source="yahoo",
                            fred=None, yahoo="XLE", freq="D", transform="ret", cls="asset",
                            mechanism="Oil & gas producers; equities first, oil price second."),
    "Gold": dict(label="Gold (GLD)", theme="Safe Haven", source="yahoo",
                 fred=None, yahoo="GLD", freq="D", transform="ret", cls="asset",
                 mechanism="Safe haven and real-rate play; hurt by rising real yields, helped by a weak USD."),
    "VIX": dict(label="VIX (Volatility)", theme="Risk", source="yahoo",
                fred=None, yahoo="^VIX", freq="D", transform="ret", cls="asset",
                mechanism="The 'fear gauge'; spikes when equities fall (strongly inverse to the S&P)."),

    # ---------------- Liquidity / monetary -----------------------------------
    "M2": dict(label="M2 Money Supply", theme="Liquidity", source="fred",
               fred="M2SL", yahoo=None, freq="M", transform="yoy", cls="macro",
               mechanism="(+) More money chasing assets lifts prices; the 2020-21 surge preceded asset inflation."),
    "Fed_Balance_Sheet": dict(label="Fed Balance Sheet", theme="Liquidity", source="fred",
                              fred="WALCL", yahoo=None, freq="W", transform="yoy", cls="macro",
                              mechanism="(+) QE expands it (risk-on liquidity); QT shrinks it (risk-off)."),
    "Reverse_Repo": dict(label="Reverse Repo (liquidity drain)", theme="Liquidity", source="fred",
                         fred="RRPONTSYD", yahoo=None, freq="D", transform="diff", cls="macro",
                         mechanism="(-) Cash parked at the Fed is liquidity sitting idle; rising RRP drains markets."),

    # ---------------- Rates ---------------------------------------------------
    "Fed_Funds_Rate": dict(label="Fed Funds Rate (%)", theme="Rates", source="fred",
                           fred="DFF", yahoo=None, freq="D", transform="diff", cls="macro",
                           mechanism="(-) The policy rate; hikes raise the cost of money and cool risk assets."),
    "Treasury_10Y": dict(label="10Y Treasury Yield (%)", theme="Rates", source="fred",
                         fred="DGS10", yahoo=None, freq="D", transform="diff", cls="macro",
                         mechanism="(-) The global discount rate; higher long yields lower the value of future cash flows."),
    "Treasury_2Y": dict(label="2Y Treasury Yield (%)", theme="Rates", source="fred",
                        fred="DGS2", yahoo=None, freq="D", transform="diff", cls="macro",
                        mechanism="(-) Tracks expected Fed policy over the next ~2 years."),
    "Real_Yield_10Y": dict(label="10Y Real Yield (TIPS, %)", theme="Rates", source="fred",
                           fred="DFII10", yahoo=None, freq="D", transform="diff", cls="macro",
                           mechanism="(-) Inflation-adjusted rate; rising real yields are especially negative for gold."),
    "Yield_Curve_10Y2Y": dict(label="Yield Curve 10Y-2Y (%)", theme="Rates", source="fred",
                              fred="T10Y2Y", yahoo=None, freq="D", transform="diff", cls="macro",
                              mechanism="Inversion (<0) has preceded most US recessions; steepening signals recovery."),

    # ---------------- Inflation ----------------------------------------------
    "CPI": dict(label="CPI Inflation (YoY)", theme="Inflation", source="fred",
                fred="CPIAUCSL", yahoo=None, freq="M", transform="yoy", cls="macro",
                mechanism="(+ commodities) Headline inflation erodes real returns; commodities often hedge it."),
    "Core_PCE": dict(label="Core PCE (YoY)", theme="Inflation", source="fred",
                     fred="PCEPILFE", yahoo=None, freq="M", transform="yoy", cls="macro",
                     mechanism="The Fed's preferred inflation gauge; drives the policy rate."),
    "Inflation_Expectations": dict(label="10Y Breakeven Inflation (%)", theme="Inflation", source="fred",
                                   fred="T10YIE", yahoo=None, freq="D", transform="diff", cls="macro",
                                   mechanism="(+) Market-implied future inflation; rising expectations support commodities and gold."),

    # ---------------- Credit & financial conditions --------------------------
    "Credit_Spread_Baa": dict(label="Baa Credit Spread (%)", theme="Credit & Risk", source="fred",
                              fred="BAA10Y", yahoo=None, freq="D", transform="diff", cls="macro",
                              mechanism="(-) Extra yield demanded to hold risky corporate debt; widening = stress = risk-off."),
    "Financial_Conditions": dict(label="Financial Conditions (NFCI)", theme="Credit & Risk", source="fred",
                                 fred="NFCI", yahoo=None, freq="W", transform="level", cls="macro",
                                 mechanism="(-) Chicago Fed index; >0 means tighter-than-average conditions, a drag on risk assets."),
    "Financial_Stress": dict(label="Financial Stress (STLFSI4)", theme="Credit & Risk", source="fred",
                             fred="STLFSI4", yahoo=None, freq="W", transform="level", cls="macro",
                             mechanism="(-) St Louis Fed stress index; spikes during crises."),

    # ---------------- Growth / activity --------------------------------------
    "Industrial_Production": dict(label="Industrial Production (YoY)", theme="Growth", source="fred",
                                  fred="INDPRO", yahoo=None, freq="M", transform="yoy", cls="macro",
                                  mechanism="(+) Real activity; drives demand for energy and industrial commodities."),
    "Jobless_Claims": dict(label="Initial Jobless Claims (YoY)", theme="Growth", source="fred",
                           fred="ICSA", yahoo=None, freq="W", transform="yoy", cls="macro",
                           mechanism="(-) Leading labour indicator; rising claims signal a weakening economy."),
    "Real_GDP": dict(label="Real GDP (YoY)", theme="Growth", source="fred",
                     fred="GDPC1", yahoo=None, freq="Q", transform="yoy", cls="macro",
                     mechanism="(+) Headline economic growth; the ultimate demand driver."),
    "Unemployment_Rate": dict(label="Unemployment Rate (%)", theme="Growth", source="fred",
                              fred="UNRATE", yahoo=None, freq="M", transform="diff", cls="macro",
                              mechanism="(-) Rising unemployment signals recession and weaker demand."),

    # ---------------- Fiscal / debt ------------------------------------------
    "Federal_Debt": dict(label="Federal Debt (YoY)", theme="Fiscal & Debt", source="fred",
                         fred="GFDEBTN", yahoo=None, freq="Q", transform="yoy", cls="macro",
                         mechanism="(+ gold) Rapid debt growth raises fiscal/inflation concerns; can pressure the USD and support gold."),
    "Debt_to_GDP": dict(label="Federal Debt / GDP (%)", theme="Fiscal & Debt", source="fred",
                        fred="GFDEGDQ188S", yahoo=None, freq="Q", transform="diff", cls="macro",
                        mechanism="(+ gold) Debt sustainability gauge; rising ratios weigh on the currency long-term."),
    "Household_Debt_Service": dict(label="Household Debt Service Ratio (%)", theme="Fiscal & Debt", source="fred",
                                   fred="TDSP", yahoo=None, freq="Q", transform="diff", cls="macro",
                                   mechanism="(-) Share of income going to debt payments; high readings mean consumer stress."),

    # ---------------- Dollar (broad) -----------------------------------------
    "USD_Broad": dict(label="Trade-Weighted USD (broad)", theme="FX", source="fred",
                      fred="DTWEXBGS", yahoo=None, freq="D", transform="ret", cls="macro",
                      mechanism="(-) Broad dollar strength makes dollar-priced commodities pricier worldwide."),

    # ---------------- Global cycle (growth bellwethers) ----------------------
    "Copper": dict(label="Copper ('Dr Copper')", theme="Global Cycle", source="yahoo",
                   fred=None, yahoo="HG=F", freq="D", transform="ret", cls="asset",
                   mechanism="(+) The metal 'with a PhD in economics' — industrial demand bellwether; "
                             "rising copper signals global growth and lifts miners and the ASX."),
    "China_Equities": dict(label="China Equities (FXI)", theme="Global Cycle", source="yahoo",
                           fred=None, yahoo="FXI", freq="D", transform="ret", cls="asset",
                           mechanism="(+) China is the marginal buyer of commodities; Chinese equity "
                                     "strength flows through to miners, the ASX and the Australian dollar."),
    "Iron_Ore": dict(label="Iron Ore (USD/t)", theme="Global Cycle", source="fred",
                     fred="PIORECRUSDM", yahoo=None, freq="M", transform="ret", cls="macro",
                     mechanism="(+) Australia's #1 export, priced off Chinese steel & property demand. "
                               "The most Australia-specific commodity — drives BHP/RIO/FMG earnings and "
                               "a large share of national income."),
    "China_Exports": dict(label="China Exports (YoY)", theme="Global Cycle", source="fred",
                          fred="XTEXVA01CNM667S", yahoo=None, freq="M", transform="yoy", cls="macro",
                          mechanism="(+) A proxy for Chinese economic activity and the global trade cycle; "
                                    "strong Chinese exports signal robust industrial demand for Australian inputs."),

    # ---------------- Australia (RBA) ----------------------------------------
    "RBA_Cash_Rate": dict(label="RBA Cash Rate (%)", theme="Australia (RBA)", source="rba",
                          rba_table="f1.1", rba_series="FIRMMCRT", fred=None, yahoo=None,
                          freq="M", transform="diff", cls="macro",
                          mechanism="(-) The RBA policy rate; hikes cool the ASX and can support the AUD "
                                    "via interest-rate differentials."),
    "AU_10Y_Yield": dict(label="Australian 10Y Bond Yield (%)", theme="Australia (RBA)", source="rba",
                         rba_table="f2", rba_series="FCMYGBAG10D", fred=None, yahoo=None,
                         freq="D", transform="diff", cls="macro",
                         mechanism="(-) The domestic discount rate for ASX valuations; tracks global yields "
                                   "plus an Australian risk premium."),
    "AU_Inflation": dict(label="Australian CPI Inflation (YoY %)", theme="Australia (RBA)", source="rba",
                         rba_table="g1", rba_series="GCPIAGYP", fred=None, yahoo=None,
                         freq="Q", transform="level", cls="macro",
                         mechanism="(+ commodities) Australian year-ended inflation; the RBA's mandate and "
                                   "the key driver of its rate decisions."),
    "AUD_TWI": dict(label="AUD Trade-Weighted Index", theme="Australia (RBA)", source="rba",
                    rba_table="f11.1", rba_series="FXRTWI", fred=None, yahoo=None,
                    freq="D", transform="ret", cls="macro",
                    mechanism="A broad read on the Australian dollar versus trading partners — cleaner than "
                              "AUD/USD alone, and tightly linked to commodity prices."),
}

# Theme display order (for grouped UI)
THEME_ORDER = ["Commodities", "FX", "Equities", "Safe Haven", "Risk",
               "Liquidity", "Rates", "Inflation", "Credit & Risk", "Growth",
               "Fiscal & Debt", "Global Cycle", "Australia (RBA)"]

# A parsimonious, relatively NON-overlapping set of macro drivers - one per
# theme - used as the default multivariate model. Including every rate series at
# once would create severe multicollinearity (2Y, 10Y and real yields all move
# together); picking one representative per theme keeps coefficients stable and
# interpretable. Users can still add/remove drivers in the dashboard.
REPRESENTATIVE_DRIVERS = [
    "M2",                      # Liquidity
    "Treasury_10Y",            # Rates (the discount rate)
    "Inflation_Expectations",  # Inflation
    "Credit_Spread_Baa",       # Credit & risk
    "Industrial_Production",   # Growth
    "Debt_to_GDP",             # Fiscal & debt
    "USD_Broad",               # Dollar
    "Copper",                  # Global cycle (growth/China bellwether)
]


def fred_drivers():
    """{colname: fred_series_id} for everything sourced from FRED."""
    return {c: m["fred"] for c, m in CATALOG.items() if m["source"] == "fred"}


def yahoo_tickers():
    """{colname: yahoo_ticker} for everything sourced from Yahoo Finance."""
    return {c: m["yahoo"] for c, m in CATALOG.items() if m["source"] == "yahoo"}


def rba_drivers():
    """{colname: (table, series_id)} for everything sourced from the RBA."""
    return {c: (m["rba_table"], m["rba_series"]) for c, m in CATALOG.items()
            if m["source"] == "rba"}


def label(col):
    return CATALOG.get(col, {}).get("label", col)


def theme(col):
    return CATALOG.get(col, {}).get("theme", "Other")


def transform_of(col):
    return CATALOG.get(col, {}).get("transform", "ret")


def mechanism(col):
    return CATALOG.get(col, {}).get("mechanism", "")


def asset_columns(present=None):
    cols = [c for c, m in CATALOG.items() if m["cls"] == "asset"]
    return [c for c in cols if present is None or c in present]


def macro_columns(present=None):
    cols = [c for c, m in CATALOG.items() if m["cls"] == "macro"]
    return [c for c in cols if present is None or c in present]


# Tradeable series that ALSO serve as macro drivers (global-cycle bellwethers):
# shown as assets in the UI, but included in the driver pool for macro analysis.
DRIVER_EXTRAS = ["Copper", "China_Equities"]


def driver_columns(present=None):
    """Macro drivers plus the tradeable global-cycle bellwethers."""
    cols = macro_columns(present) + [c for c in DRIVER_EXTRAS
                                     if present is None or c in present]
    # de-dup preserving order
    seen, out = set(), []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def transforms_map(present=None):
    return {c: m["transform"] for c, m in CATALOG.items()
            if present is None or c in present}
