"""
Data fetching layer for the qualitative stock analysis skill.

Gathers raw inputs from yfinance:
- Business summary, sector/industry, country, employees
- Market cap, financials, balance sheet, cashflow
- Sector ETF mapping for momentum analysis
- Peer tickers (curated map — yfinance recommendations are unreliable)
- Recent news headlines (up to 5)
- RSI(14) and 1m/3m price returns

Also fetches market/index data (sector ETFs, VIX, dollar index) for the
analysis layer.

All fetches are cached on disk for 1 hour to avoid hammering yfinance.

Granular getters (call directly from any agent):
    get_rsi(ticker)              → (float, str) | (None, None)
    get_price_returns(ticker)    → (1m_pct, 3m_pct)
    get_recent_news(ticker)      → list[str]
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

CACHE_DIR = Path("/tmp/qual_analysis_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 3600  # 1 hour


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF MAP
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
# PEER MAP — curated; falls back to empty if ticker not present
# ─────────────────────────────────────────────────────────────────────────────

PEER_MAP: dict[str, list[str]] = {
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


def _cache_key(identifier: str, method: str, **kwargs) -> Path:
    raw = f"{identifier}|{method}|{sorted(kwargs.items())}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{identifier}_{method}_{h}.pkl"


def _cached(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
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
# TECHNICAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _calc_rsi(history: Optional[pd.DataFrame], period: int = 14) -> tuple[Optional[float], Optional[str]]:
    """Wilder's RSI(14). Returns (value, signal: overbought/neutral/oversold)."""
    if history is None or history.empty or len(history) < period + 1:
        return None, None
    try:
        delta = history["Close"].diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi_val = float((100 - 100 / (1 + rs)).iloc[-1])
        if pd.isna(rsi_val):
            return None, None
        signal = "overbought" if rsi_val > 70 else "oversold" if rsi_val < 30 else "neutral"
        return round(rsi_val, 1), signal
    except Exception:
        return None, None


def _calc_returns(history: Optional[pd.DataFrame]) -> tuple[Optional[float], Optional[float]]:
    """1-month (~21 sessions) and 3-month (~63 sessions) price returns (%)."""
    if history is None or history.empty:
        return None, None
    try:
        closes = history["Close"].dropna()
        current = float(closes.iloc[-1])
        ret_1m = ((current / float(closes.iloc[-21])) - 1) * 100 if len(closes) >= 21 else None
        ret_3m = ((current / float(closes.iloc[-63])) - 1) * 100 if len(closes) >= 63 else None
        return ret_1m, ret_3m
    except Exception:
        return None, None


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
    # Derived from history_1y
    news: list[str] = field(default_factory=list)
    rsi_14d: Optional[float] = None
    rsi_signal: Optional[str] = None
    price_return_1m_pct: Optional[float] = None
    price_return_3m_pct: Optional[float] = None
    sources_succeeded: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


def fetch_bundle(ticker: str, use_cache: bool = True) -> CompanyBundle:
    """Fetch everything the skill needs about a company in a single bundle."""
    ticker = ticker.upper()
    bundle = CompanyBundle(ticker=ticker)

    cache_path = _cache_key(ticker, "bundle")
    if use_cache:
        cached = _cached(cache_path)
        if cached is not None:
            return cached

    try:
        tk = yf.Ticker(ticker)
    except Exception as e:
        bundle.sources_failed.append(f"yf.Ticker:{e}")
        return bundle

    try:
        bundle.info = tk.info or {}
        bundle.sources_succeeded.append("info")
    except Exception as e:
        bundle.sources_failed.append(f"info:{e}")

    try:
        bundle.financials = tk.financials
        if bundle.financials is not None and not bundle.financials.empty:
            bundle.sources_succeeded.append("financials")
    except Exception as e:
        bundle.sources_failed.append(f"financials:{e}")

    try:
        bundle.balance_sheet = tk.balance_sheet
        if bundle.balance_sheet is not None and not bundle.balance_sheet.empty:
            bundle.sources_succeeded.append("balance_sheet")
    except Exception as e:
        bundle.sources_failed.append(f"balance_sheet:{e}")

    try:
        bundle.cashflow = tk.cashflow
        if bundle.cashflow is not None and not bundle.cashflow.empty:
            bundle.sources_succeeded.append("cashflow")
    except Exception as e:
        bundle.sources_failed.append(f"cashflow:{e}")

    try:
        bundle.history_1y = tk.history(period="1y", auto_adjust=True)
        if bundle.history_1y is not None and not bundle.history_1y.empty:
            bundle.sources_succeeded.append("history_1y")
    except Exception as e:
        bundle.sources_failed.append(f"history_1y:{e}")

    if bundle.history_1y is not None and not bundle.history_1y.empty:
        bundle.rsi_14d, bundle.rsi_signal = _calc_rsi(bundle.history_1y)
        bundle.price_return_1m_pct, bundle.price_return_3m_pct = _calc_returns(bundle.history_1y)

    try:
        news_raw = tk.news or []
        bundle.news = [item.get("title", "") for item in news_raw[:5] if item.get("title")]
        if bundle.news:
            bundle.sources_succeeded.append("news")
    except Exception as e:
        bundle.sources_failed.append(f"news:{e}")

    if use_cache:
        _store(cache_path, bundle)

    return bundle


def fetch_market_history(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch price history for any symbol (ETF, index, etc.)."""
    cache_path = _cache_key(symbol, "history", period=period)
    cached = _cached(cache_path)
    if cached is not None:
        return cached
    try:
        hist = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if hist is not None and not hist.empty:
            _store(cache_path, hist)
            return hist
    except Exception:
        pass
    return None


def get_peer_tickers(ticker: str) -> list[str]:
    """Return curated peer tickers for the given ticker."""
    return PEER_MAP.get(ticker.upper(), [])


def get_sector_etf(sector: Optional[str]) -> Optional[str]:
    """Map a yfinance sector string to its SPDR sector ETF ticker."""
    return SECTOR_ETF_MAP.get(sector) if sector else None


# ─────────────────────────────────────────────────────────────────────────────
# SAFE HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def safe_get(df: Optional[pd.DataFrame], row_label: str, col_idx: int = 0) -> Optional[float]:
    """Pull a single numeric value from a yfinance DataFrame, defensively."""
    if df is None or df.empty or row_label not in df.index:
        return None
    try:
        val = df.loc[row_label].iloc[col_idx]
        return None if pd.isna(val) else float(val)
    except Exception:
        return None


def safe_get_series(df: Optional[pd.DataFrame], row_label: str) -> list[float]:
    """Pull a row from a yfinance DataFrame as a list of floats (most-recent first)."""
    if df is None or df.empty or row_label not in df.index:
        return []
    try:
        return [float(x) for x in df.loc[row_label].tolist() if not pd.isna(x)]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# GRANULAR GETTERS
# ─────────────────────────────────────────────────────────────────────────────


def get_rsi(ticker: str, use_cache: bool = True) -> tuple[Optional[float], Optional[str]]:
    """RSI(14) value and signal (overbought/neutral/oversold) for the ticker."""
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    return bundle.rsi_14d, bundle.rsi_signal


def get_price_returns(ticker: str, use_cache: bool = True) -> tuple[Optional[float], Optional[float]]:
    """1-month and 3-month price returns (%) for the ticker."""
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    return bundle.price_return_1m_pct, bundle.price_return_3m_pct


def get_recent_news(ticker: str, use_cache: bool = True) -> list[str]:
    """Up to 5 recent news headlines for the ticker from yfinance."""
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    return bundle.news
