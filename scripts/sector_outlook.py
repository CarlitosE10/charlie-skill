"""
Sector outlook: ETF momentum + relative strength + geopolitical risk mapping.

Produces deterministic facts about the sector that the synthesizer uses to
ground its qualitative outlook judgment.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from data_collector import fetch_etf_history, get_sector_etf
from report import GeopoliticalRisk

# ─────────────────────────────────────────────────────────────────────────────
# GEOPOLITICAL RISK MAP
# Adapted from analyze_stock.py's GEOPOLITICAL_RISK_MAP, expanded with a
# severity rating and made "always-on" rather than news-triggered. Charlie
# flags a baseline geopolitical exposure based on sector + ticker.
# ─────────────────────────────────────────────────────────────────────────────

GEOPOLITICAL_RISK_MAP = {
    "taiwan_strait": {
        "event": "Taiwan Strait / TSMC supply chain",
        "sectors": ["Technology", "Communication Services"],
        "tickers": ["NVDA", "AMD", "TSM", "INTC", "QCOM", "AVGO", "MU", "AAPL", "ASML"],
        "impact": "Semiconductor supply chain disruption; advanced node concentration risk",
        "severity": "strong",
    },
    "us_china_trade": {
        "event": "US–China tariffs and tech export controls",
        "sectors": ["Technology", "Consumer Cyclical", "Consumer Defensive", "Industrials"],
        "tickers": ["AAPL", "QCOM", "NKE", "SBUX", "MCD", "TGT", "WMT", "BA", "TSLA"],
        "impact": "Tech supply chain costs and consumer market access",
        "severity": "strong",
    },
    "russia_ukraine": {
        "event": "Russia–Ukraine war",
        "sectors": ["Energy", "Basic Materials"],
        "tickers": ["XOM", "CVX", "COP", "SLB", "MOS", "CF", "NTR", "ADM"],
        "impact": "Energy and fertilizer/grain price volatility",
        "severity": "neutral",
    },
    "middle_east": {
        "event": "Middle East tensions (Iran/Israel/Gulf)",
        "sectors": ["Energy", "Industrials"],
        "tickers": ["XOM", "CVX", "COP", "LMT", "RTX", "NOC", "GD", "BA"],
        "impact": "Oil-price volatility; defense procurement cycles",
        "severity": "neutral",
    },
    "regulatory_pharma": {
        "event": "US drug-pricing reform & PBM scrutiny",
        "sectors": ["Healthcare"],
        "tickers": ["LLY", "PFE", "MRK", "JNJ", "BMY", "UNH", "CVS", "CI"],
        "impact": "Pricing power compression on top-selling drugs",
        "severity": "neutral",
    },
    "regulatory_bigtech": {
        "event": "Antitrust and Digital Markets Act enforcement",
        "sectors": ["Technology", "Communication Services", "Consumer Cyclical"],
        "tickers": ["GOOGL", "META", "AMZN", "AAPL", "MSFT"],
        "impact": "Forced product changes, fines, structural separation risk",
        "severity": "neutral",
    },
    "energy_transition": {
        "event": "Energy transition / decarbonization policy",
        "sectors": ["Energy", "Utilities", "Basic Materials", "Industrials"],
        "tickers": ["XOM", "CVX", "COP", "F", "GM"],
        "impact": "Stranded-asset and capex re-allocation pressure",
        "severity": "weak",
    },
    "banking_stress": {
        "event": "Regional banking liquidity stress",
        "sectors": ["Financial Services"],
        "tickers": ["USB", "PNC", "TFC", "KEY", "CFG", "FITB"],
        "impact": "Deposit outflows, MtM losses on HTM portfolios",
        "severity": "weak",
    },
}


def assess_geopolitical_risks(ticker: str, sector: Optional[str]) -> list[GeopoliticalRisk]:
    """Return all geopolitical events to which this ticker/sector is exposed."""
    ticker = ticker.upper()
    risks: list[GeopoliticalRisk] = []
    for _key, ev in GEOPOLITICAL_RISK_MAP.items():
        match_ticker = ticker in ev["tickers"]
        match_sector = sector and sector in ev["sectors"]
        if match_ticker or match_sector:
            risks.append(
                GeopoliticalRisk(
                    event=ev["event"],
                    impact=ev["impact"],
                    severity=ev["severity"],  # type: ignore
                )
            )
    return risks


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF MOMENTUM
# ─────────────────────────────────────────────────────────────────────────────


def calc_period_return(hist: Optional[pd.DataFrame], days: int) -> Optional[float]:
    """% return over the trailing N trading days."""
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    if len(hist) < days + 1:
        return None
    try:
        recent = float(hist["Close"].iloc[-1])
        past = float(hist["Close"].iloc[-days - 1])
        if past == 0:
            return None
        return (recent / past - 1) * 100
    except Exception:
        return None


def calc_ytd_return(hist: Optional[pd.DataFrame]) -> Optional[float]:
    """% return year-to-date."""
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    try:
        current_year = hist.index[-1].year
        ytd = hist[hist.index.year == current_year]
        if len(ytd) < 2:
            return None
        first = float(ytd["Close"].iloc[0])
        last = float(ytd["Close"].iloc[-1])
        if first == 0:
            return None
        return (last / first - 1) * 100
    except Exception:
        return None


def calc_sector_outlook_facts(sector: Optional[str], ticker: str) -> dict:
    """
    Compute deterministic sector facts:
      - sector ETF return 3m and YTD
      - sector ETF relative strength vs SPY (3m)
      - geopolitical risks
    """
    out: dict = {
        "sector_etf": None,
        "sector_etf_return_3m_pct": None,
        "sector_etf_return_ytd_pct": None,
        "relative_strength_vs_spy_3m": None,
        "geopolitical_risks": [],
    }

    out["geopolitical_risks"] = assess_geopolitical_risks(ticker, sector)

    etf = get_sector_etf(sector)
    if not etf:
        return out
    out["sector_etf"] = etf

    sector_hist = fetch_etf_history(etf, period="1y")
    spy_hist = fetch_etf_history("SPY", period="1y")

    sector_3m = calc_period_return(sector_hist, 63)  # ~3 months of trading days
    sector_ytd = calc_ytd_return(sector_hist)
    spy_3m = calc_period_return(spy_hist, 63)

    out["sector_etf_return_3m_pct"] = sector_3m
    out["sector_etf_return_ytd_pct"] = sector_ytd

    if sector_3m is not None and spy_3m is not None:
        out["relative_strength_vs_spy_3m"] = sector_3m - spy_3m

    return out
