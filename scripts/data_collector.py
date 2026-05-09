"""
Data collection layer for Charlie.

Gathers the raw qualitative inputs from yfinance and a few public sources:
- Business summary, sector/industry, country, employees
- Market cap, share counts
- Sector ETF mapping
- Peer tickers (from a curated map; yfinance's recommendations API is unreliable)

All fetches are cached on disk for 1 hour to avoid hammering yfinance.
"""

from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yfinance as yf

CACHE_DIR = Path("/tmp/charlie_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 3600  # 1 hour


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF MAP (parallel to Snowball, kept in-sync)
# ─────────────────────────────────────────────────────────────────────────────

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}


# ─────────────────────────────────────────────────────────────────────────────
# PEER MAP — curated, since yfinance recommendations are unreliable.
# Falls back to "same sector" peers when the ticker isn't here.
# ─────────────────────────────────────────────────────────────────────────────

PEER_MAP = {
    # Mega-cap tech
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "ORCL", "CRM"],
    "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
    "GOOG": ["META", "MSFT", "AMZN", "AAPL"],
    "META": ["GOOGL", "SNAP", "PINS", "MSFT"],
    "AMZN": ["WMT", "MSFT", "GOOGL", "AAPL"],
    "NVDA": ["AMD", "AVGO", "INTC", "TSM"],
    "AMD": ["NVDA", "INTC", "AVGO", "QCOM"],
    "INTC": ["AMD", "NVDA", "TSM", "QCOM"],
    "TSM": ["NVDA", "INTC", "AVGO", "QCOM"],
    "AVGO": ["NVDA", "QCOM", "TXN", "ADI"],
    # Cloud / SaaS
    "CRM": ["MSFT", "ORCL", "NOW", "ADBE"],
    "ORCL": ["MSFT", "CRM", "SAP", "IBM"],
    "ADBE": ["MSFT", "CRM", "INTU", "NOW"],
    "NOW": ["MSFT", "CRM", "ADBE", "WDAY"],
    # EVs / Auto
    "TSLA": ["F", "GM", "TM", "RIVN"],
    "F": ["GM", "TSLA", "STLA", "TM"],
    "GM": ["F", "TSLA", "STLA", "TM"],
    # Banking
    "JPM": ["BAC", "WFC", "C", "GS"],
    "BAC": ["JPM", "WFC", "C", "USB"],
    "WFC": ["JPM", "BAC", "C", "USB"],
    "GS": ["MS", "JPM", "C", "BAC"],
    "MS": ["GS", "JPM", "BAC", "C"],
    # Consumer staples
    "KO": ["PEP", "MNST", "KDP", "STZ"],
    "PEP": ["KO", "MDLZ", "KDP", "MNST"],
    "WMT": ["TGT", "COST", "AMZN", "KR"],
    "COST": ["WMT", "TGT", "BJ", "KR"],
    # Healthcare
    "JNJ": ["PFE", "MRK", "ABBV", "LLY"],
    "PFE": ["JNJ", "MRK", "ABBV", "BMY"],
    "LLY": ["NVO", "PFE", "MRK", "JNJ"],
    "UNH": ["ELV", "CI", "HUM", "CVS"],
    # Energy
    "XOM": ["CVX", "COP", "BP", "SHEL"],
    "CVX": ["XOM", "COP", "BP", "SHEL"],
    # Payments
    "V": ["MA", "PYPL", "AXP", "DFS"],
    "MA": ["V", "PYPL", "AXP", "DFS"],
}


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────


def _cache_key(ticker: str, method: str, **kwargs) -> Path:
    raw = f"{ticker}|{method}|{sorted(kwargs.items())}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{ticker}_{method}_{h}.pkl"


def _cached(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _store(path: Path, value: Any) -> None:
    try:
        with open(path, "wb") as f:
            pickle.dump(value, f)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY BUNDLE
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompanyBundle:
    """Raw fetched data for a single company."""

    ticker: str
    info: dict[str, Any] = field(default_factory=dict)
    financials: Optional[pd.DataFrame] = None
    balance_sheet: Optional[pd.DataFrame] = None
    cashflow: Optional[pd.DataFrame] = None
    history_1y: Optional[pd.DataFrame] = None
    sources_succeeded: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


def fetch_company_bundle(ticker: str, use_cache: bool = True) -> CompanyBundle:
    """Fetch everything Charlie needs about a company in a single bundle."""
    ticker = ticker.upper()
    bundle = CompanyBundle(ticker=ticker)

    # Reuse cached bundle if available
    cache_path = _cache_key(ticker, "company_bundle")
    if use_cache:
        cached = _cached(cache_path)
        if cached is not None:
            return cached

    try:
        tk = yf.Ticker(ticker)
    except Exception as e:
        bundle.sources_failed.append(f"yf.Ticker:{e}")
        return bundle

    # Info
    try:
        info = tk.info or {}
        bundle.info = info
        bundle.sources_succeeded.append("info")
    except Exception as e:
        bundle.sources_failed.append(f"info:{e}")

    # Financials (annual income statement)
    try:
        bundle.financials = tk.financials
        if bundle.financials is not None and not bundle.financials.empty:
            bundle.sources_succeeded.append("financials")
    except Exception as e:
        bundle.sources_failed.append(f"financials:{e}")

    # Balance sheet
    try:
        bundle.balance_sheet = tk.balance_sheet
        if bundle.balance_sheet is not None and not bundle.balance_sheet.empty:
            bundle.sources_succeeded.append("balance_sheet")
    except Exception as e:
        bundle.sources_failed.append(f"balance_sheet:{e}")

    # Cashflow
    try:
        bundle.cashflow = tk.cashflow
        if bundle.cashflow is not None and not bundle.cashflow.empty:
            bundle.sources_succeeded.append("cashflow")
    except Exception as e:
        bundle.sources_failed.append(f"cashflow:{e}")

    # History (for relative strength)
    try:
        bundle.history_1y = tk.history(period="1y", auto_adjust=True)
        if bundle.history_1y is not None and not bundle.history_1y.empty:
            bundle.sources_succeeded.append("history_1y")
    except Exception as e:
        bundle.sources_failed.append(f"history_1y:{e}")

    if use_cache:
        _store(cache_path, bundle)

    return bundle


def fetch_etf_history(etf_ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch a sector ETF's price history for relative-strength calcs."""
    cache_path = _cache_key(etf_ticker, "history", period=period)
    cached = _cached(cache_path)
    if cached is not None:
        return cached
    try:
        tk = yf.Ticker(etf_ticker)
        hist = tk.history(period=period, auto_adjust=True)
        if hist is not None and not hist.empty:
            _store(cache_path, hist)
            return hist
    except Exception:
        return None
    return None


def get_peer_tickers(ticker: str, sector: Optional[str] = None) -> list[str]:
    """Return a list of peer tickers. Curated first; falls back to empty."""
    ticker = ticker.upper()
    if ticker in PEER_MAP:
        return PEER_MAP[ticker]
    return []


def get_sector_etf(sector: Optional[str]) -> Optional[str]:
    """Map yfinance's sector string to the corresponding SPDR sector ETF."""
    if not sector:
        return None
    return SECTOR_ETF_MAP.get(sector)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def safe_get(df: Optional[pd.DataFrame], row_label: str, col_idx: int = 0) -> Optional[float]:
    """Pull a numeric value from a yfinance DataFrame, defensively."""
    if df is None or df.empty:
        return None
    if row_label not in df.index:
        return None
    try:
        val = df.loc[row_label].iloc[col_idx]
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


def safe_get_series(df: Optional[pd.DataFrame], row_label: str) -> list[float]:
    """Pull a row from a yfinance DataFrame as a list of floats (most-recent first)."""
    if df is None or df.empty or row_label not in df.index:
        return []
    try:
        s = df.loc[row_label]
        return [float(x) for x in s.tolist() if not pd.isna(x)]
    except Exception:
        return []
