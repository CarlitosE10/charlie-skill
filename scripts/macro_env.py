"""
Macro environment snapshot.

Fetches a lightweight macro context (VIX level, dollar index 3m change) and
a heuristic sector cyclicality classification. The synthesizer uses these as
anchors when judging the macro tailwind/headwind.

Sector cyclicality classification follows standard practice:
- Defensive: Consumer Defensive, Healthcare, Utilities
- Cyclical: Consumer Cyclical, Industrials, Basic Materials, Financial Services
- Highly cyclical: Energy
- Neutral: Technology, Communication Services
- Real Estate: cyclical (rate-sensitive)
"""

from __future__ import annotations

from typing import Literal, Optional

from data_collector import fetch_etf_history
from sector_outlook import calc_period_return

CyclicalityLabel = Literal["defensive", "neutral", "cyclical", "highly_cyclical", "unknown"]

SECTOR_CYCLICALITY: dict[str, CyclicalityLabel] = {
    "Consumer Defensive": "defensive",
    "Healthcare": "defensive",
    "Utilities": "defensive",
    "Technology": "neutral",
    "Communication Services": "neutral",
    "Consumer Cyclical": "cyclical",
    "Industrials": "cyclical",
    "Basic Materials": "cyclical",
    "Financial Services": "cyclical",
    "Real Estate": "cyclical",
    "Energy": "highly_cyclical",
}


def fetch_vix() -> Optional[float]:
    """Pull the latest VIX close as a sentiment / volatility proxy."""
    hist = fetch_etf_history("^VIX", period="5d")
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    try:
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def fetch_dxy_3m_change() -> Optional[float]:
    """% change in the dollar index (DXY) over the trailing 3 months."""
    hist = fetch_etf_history("DX-Y.NYB", period="6mo")
    if hist is None or hist.empty:
        # Fallback to UUP (Invesco DB US Dollar Index Bullish Fund)
        hist = fetch_etf_history("UUP", period="6mo")
    return calc_period_return(hist, 63)


def classify_cyclicality(sector: Optional[str]) -> CyclicalityLabel:
    if not sector:
        return "unknown"
    return SECTOR_CYCLICALITY.get(sector, "unknown")


def calc_macro_facts(sector: Optional[str]) -> dict:
    """
    Returns a dict of macro facts:
      - vix_level
      - dollar_index_3m_change_pct
      - cyclicality (label)
    """
    return {
        "vix_level": fetch_vix(),
        "dollar_index_3m_change_pct": fetch_dxy_3m_change(),
        "cyclicality": classify_cyclicality(sector),
    }
