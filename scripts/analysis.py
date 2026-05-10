"""
Deterministic analysis layer for the qualitative stock analysis skill.

Computes all grounded, non-LLM facts about a ticker:
- MOAT quantitative proxies (margin stability, ROIC, R&D/CAPEX intensity, CAGR)
- Sector outlook (ETF momentum vs SPY, geopolitical risk exposure)
- Peer comparison (market cap rank, margin rank, relative position)
- Macro context (VIX, dollar index 3m change, sector cyclicality)
- FactPack assembly (structured collection of all deterministic facts)

Uses the 1-hour disk cache via fetch_bundle / fetch_market_history.

Granular getters (call directly from any agent):
    get_moat_proxies(ticker)      → MoatQuantitativeProxies
    get_sector_outlook(ticker)    → SectorOutlookFacts
    get_peer_comparison(ticker)   → Optional[PeerComparison]
    get_macro(ticker)             → MacroFacts
    build_fact_pack(ticker)       → FactPack
"""

from __future__ import annotations

import statistics
from typing import Literal, Optional

from pydantic import BaseModel, Field

from data import (
    CompanyBundle,
    fetch_bundle,
    fetch_market_history,
    get_peer_tickers,
    get_sector_etf,
    safe_get_series,
)

# ─────────────────────────────────────────────────────────────────────────────
# SECTOR CYCLICALITY
# ─────────────────────────────────────────────────────────────────────────────

_CYCLICALITY: dict[str, str] = {
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

# ─────────────────────────────────────────────────────────────────────────────
# GEOPOLITICAL RISK MAP
# Always-on structural exposures by sector and ticker.
# ─────────────────────────────────────────────────────────────────────────────

_GEO_RISKS = {
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

# ─────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES (shared with qualify.py)
# ─────────────────────────────────────────────────────────────────────────────

QualitativeRating = Literal["very_weak", "weak", "neutral", "strong", "very_strong"]

# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────────


class MoatQuantitativeProxies(BaseModel):
    """Numerical fingerprints used to anchor the qualitative MOAT assessment."""

    gross_margin_avg: Optional[float] = Field(None, description="Average gross margin (last 4y)")
    gross_margin_stability: Optional[float] = Field(None, description="CV of gross margin — lower = more stable")
    operating_margin_avg: Optional[float] = None
    operating_margin_stability: Optional[float] = None
    roic_avg: Optional[float] = Field(None, description="Average ROIC")
    roic_stability: Optional[float] = None
    rd_intensity_avg: Optional[float] = Field(None, description="R&D / Revenue")
    capex_intensity_avg: Optional[float] = Field(None, description="CAPEX / Revenue")
    revenue_cagr_3y: Optional[float] = None


class GeopoliticalRisk(BaseModel):
    event: str
    impact: str
    severity: QualitativeRating


class PeerSnapshot(BaseModel):
    ticker: str
    name: Optional[str] = None
    market_cap: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    pe_ratio: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None


class PeerComparison(BaseModel):
    peers: list[PeerSnapshot] = Field(default_factory=list)
    market_cap_rank: Optional[int] = Field(None, description="1 = largest among peers")
    market_cap_share_pct: Optional[float] = None
    margin_rank: Optional[int] = None
    growth_rank: Optional[int] = None
    relative_position: Literal["leader", "challenger", "follower", "laggard", "unknown"] = "unknown"


class SectorOutlookFacts(BaseModel):
    sector: Optional[str] = None
    sector_etf: Optional[str] = None
    sector_etf_return_3m_pct: Optional[float] = None
    sector_etf_return_ytd_pct: Optional[float] = None
    relative_strength_vs_spy_3m: Optional[float] = Field(
        None, description="Sector ETF return − SPY return (3m), in pct points"
    )
    geopolitical_risks: list[GeopoliticalRisk] = Field(default_factory=list)


class MacroFacts(BaseModel):
    vix_level: Optional[float] = None
    dollar_index_3m_change_pct: Optional[float] = None
    cyclicality: Literal["defensive", "neutral", "cyclical", "highly_cyclical", "unknown"] = "unknown"


class FactPack(BaseModel):
    """Structured collection of deterministic facts passed to the LLM synthesis layer."""

    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    business_summary: Optional[str] = None
    country: Optional[str] = None
    employees: Optional[int] = None
    market_cap: Optional[float] = None

    # Sector
    sector_etf: Optional[str] = None
    sector_etf_return_3m_pct: Optional[float] = None
    sector_etf_return_ytd_pct: Optional[float] = None
    relative_strength_vs_spy_3m: Optional[float] = None
    geopolitical_risks: list[GeopoliticalRisk] = Field(default_factory=list)

    # Macro
    vix_level: Optional[float] = None
    dollar_index_3m_change_pct: Optional[float] = None
    cyclicality: str = "unknown"

    # Technical context
    rsi_14d: Optional[float] = None
    rsi_signal: Optional[str] = None
    price_return_1m_pct: Optional[float] = None
    price_return_3m_pct: Optional[float] = None
    recent_news: list[str] = Field(default_factory=list)

    # MOAT proxies
    moat_proxies: MoatQuantitativeProxies = Field(default_factory=MoatQuantitativeProxies)

    # Peers
    peer_comparison: Optional[PeerComparison] = None

    # Provenance
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# MOAT PROXIES
# ─────────────────────────────────────────────────────────────────────────────


def _cv(values: list[float]) -> Optional[float]:
    """Coefficient of variation (std / mean). Lower = more stable."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    m = statistics.mean(clean)
    if m == 0:
        return None
    try:
        return abs(statistics.stdev(clean) / m)
    except statistics.StatisticsError:
        return None


def _avg(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def _ratios(num: list[float], den: list[float]) -> list[float]:
    n = min(len(num), len(den))
    return [num[i] / den[i] for i in range(n) if den[i] != 0]


def calc_moat_proxies(bundle: CompanyBundle) -> MoatQuantitativeProxies:
    """Compute quantitative MOAT anchors from the company's financials."""
    fin, bs, cf = bundle.financials, bundle.balance_sheet, bundle.cashflow

    revenue = safe_get_series(fin, "Total Revenue")
    gross_profit = safe_get_series(fin, "Gross Profit")
    operating_income = safe_get_series(fin, "Operating Income")
    net_income = safe_get_series(fin, "Net Income")
    rd = safe_get_series(fin, "Research And Development")
    capex_series = safe_get_series(cf, "Capital Expenditure")
    equity = safe_get_series(bs, "Stockholders Equity") or safe_get_series(bs, "Total Stockholder Equity")
    total_debt = safe_get_series(bs, "Total Debt") or safe_get_series(bs, "Long Term Debt")

    gross_margins = _ratios(gross_profit, revenue)
    operating_margins = _ratios(operating_income, revenue)

    roic_series: list[float] = []
    for i in range(min(len(net_income), len(equity))):
        debt_i = total_debt[i] if total_debt and i < len(total_debt) else 0.0
        invested = equity[i] + debt_i
        if invested > 0:
            roic_series.append(net_income[i] / invested)

    capex_abs = [abs(c) for c in capex_series]

    revenue_cagr_3y: Optional[float] = None
    if len(revenue) >= 4:
        try:
            if revenue[3] > 0 and revenue[0] > 0:
                revenue_cagr_3y = (revenue[0] / revenue[3]) ** (1 / 3) - 1
        except Exception:
            pass

    return MoatQuantitativeProxies(
        gross_margin_avg=_avg(gross_margins),
        gross_margin_stability=_cv(gross_margins),
        operating_margin_avg=_avg(operating_margins),
        operating_margin_stability=_cv(operating_margins),
        roic_avg=_avg(roic_series),
        roic_stability=_cv(roic_series),
        rd_intensity_avg=_avg(_ratios(rd, revenue)) if rd else None,
        capex_intensity_avg=_avg(_ratios(capex_abs, revenue)) if capex_abs else None,
        revenue_cagr_3y=revenue_cagr_3y,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR OUTLOOK
# ─────────────────────────────────────────────────────────────────────────────


def _period_return(hist, days: int) -> Optional[float]:
    if hist is None or hist.empty or "Close" not in hist.columns or len(hist) < days + 1:
        return None
    try:
        recent = float(hist["Close"].iloc[-1])
        past = float(hist["Close"].iloc[-days - 1])
        return (recent / past - 1) * 100 if past != 0 else None
    except Exception:
        return None


def _ytd_return(hist) -> Optional[float]:
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    try:
        current_year = hist.index[-1].year
        ytd = hist[hist.index.year == current_year]
        if len(ytd) < 2:
            return None
        first, last = float(ytd["Close"].iloc[0]), float(ytd["Close"].iloc[-1])
        return (last / first - 1) * 100 if first != 0 else None
    except Exception:
        return None


def _assess_geopolitical_risks(ticker: str, sector: Optional[str]) -> list[GeopoliticalRisk]:
    ticker = ticker.upper()
    risks = []
    for ev in _GEO_RISKS.values():
        if ticker in ev["tickers"] or (sector and sector in ev["sectors"]):
            risks.append(GeopoliticalRisk(
                event=ev["event"],
                impact=ev["impact"],
                severity=ev["severity"],  # type: ignore
            ))
    return risks


def calc_sector_outlook(ticker: str, sector: Optional[str]) -> SectorOutlookFacts:
    """Sector ETF momentum vs SPY and structural geopolitical risk exposure."""
    geo_risks = _assess_geopolitical_risks(ticker, sector)
    etf = get_sector_etf(sector)

    if not etf:
        return SectorOutlookFacts(sector=sector, geopolitical_risks=geo_risks)

    sector_hist = fetch_market_history(etf, period="1y")
    spy_hist = fetch_market_history("SPY", period="1y")

    sector_3m = _period_return(sector_hist, 63)
    spy_3m = _period_return(spy_hist, 63)
    rel_strength = (sector_3m - spy_3m) if sector_3m is not None and spy_3m is not None else None

    return SectorOutlookFacts(
        sector=sector,
        sector_etf=etf,
        sector_etf_return_3m_pct=sector_3m,
        sector_etf_return_ytd_pct=_ytd_return(sector_hist),
        relative_strength_vs_spy_3m=rel_strength,
        geopolitical_risks=geo_risks,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PEER COMPARISON
# ─────────────────────────────────────────────────────────────────────────────


def _build_peer_snapshot(ticker: str) -> Optional[PeerSnapshot]:
    try:
        info = fetch_bundle(ticker, use_cache=True).info
    except Exception:
        return None
    if not info:
        return None
    return PeerSnapshot(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName"),
        market_cap=info.get("marketCap"),
        gross_margin=info.get("grossMargins"),
        operating_margin=info.get("operatingMargins"),
        pe_ratio=info.get("trailingPE"),
        revenue_growth_yoy=info.get("revenueGrowth"),
    )


def _rank_of(value: Optional[float], values: list[Optional[float]], higher_is_better: bool = True) -> Optional[int]:
    if value is None:
        return None
    ranked = sorted([(v, i) for i, v in enumerate(values) if v is not None],
                    key=lambda x: x[0], reverse=higher_is_better)
    for rank, (v, _) in enumerate(ranked, start=1):
        if v == value:
            return rank
    return None


def calc_peer_comparison(ticker: str) -> Optional[PeerComparison]:
    """Side-by-side peer ranking against the curated peer group."""
    ticker = ticker.upper()
    peer_tickers = get_peer_tickers(ticker)
    if not peer_tickers:
        return None

    subject = _build_peer_snapshot(ticker)
    if subject is None:
        return None

    peers = [s for s in (_build_peer_snapshot(p) for p in peer_tickers) if s is not None]
    if not peers:
        return None

    all_ = [subject] + peers
    market_caps = [s.market_cap for s in all_]
    margins = [s.operating_margin for s in all_]
    growths = [s.revenue_growth_yoy for s in all_]

    cap_rank = _rank_of(subject.market_cap, market_caps)
    margin_rank = _rank_of(subject.operating_margin, margins)
    growth_rank = _rank_of(subject.revenue_growth_yoy, growths)

    valid_caps = [c for c in market_caps if c is not None]
    cap_share = (
        (subject.market_cap / sum(valid_caps)) * 100
        if subject.market_cap is not None and valid_caps and sum(valid_caps) > 0
        else None
    )

    used_ranks = [r for r in (cap_rank, margin_rank) if r is not None]
    if not used_ranks:
        position = "unknown"
    else:
        pct = (sum(used_ranks) / len(used_ranks)) / len(all_)
        position = "leader" if pct <= 0.25 else "challenger" if pct <= 0.5 else "follower" if pct <= 0.75 else "laggard"

    return PeerComparison(
        peers=peers,
        market_cap_rank=cap_rank,
        market_cap_share_pct=cap_share,
        margin_rank=margin_rank,
        growth_rank=growth_rank,
        relative_position=position,  # type: ignore
    )


# ─────────────────────────────────────────────────────────────────────────────
# MACRO
# ─────────────────────────────────────────────────────────────────────────────


def calc_macro(sector: Optional[str]) -> MacroFacts:
    """VIX level, dollar index 3m change, and sector cyclicality."""
    vix_hist = fetch_market_history("^VIX", period="5d")
    vix_level: Optional[float] = None
    if vix_hist is not None and not vix_hist.empty and "Close" in vix_hist.columns:
        try:
            vix_level = float(vix_hist["Close"].iloc[-1])
        except Exception:
            pass

    dxy_hist = fetch_market_history("DX-Y.NYB", period="6mo") or fetch_market_history("UUP", period="6mo")
    dxy_3m = _period_return(dxy_hist, 63)

    cyclicality = _CYCLICALITY.get(sector, "unknown") if sector else "unknown"

    return MacroFacts(
        vix_level=vix_level,
        dollar_index_3m_change_pct=dxy_3m,
        cyclicality=cyclicality,  # type: ignore
    )


# ─────────────────────────────────────────────────────────────────────────────
# FACT PACK ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────


def build_fact_pack(ticker: str, use_cache: bool = True) -> FactPack:
    """Gather every deterministic fact about the ticker into a FactPack."""
    ticker = ticker.upper()
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    info = bundle.info
    sector = info.get("sector")

    sector_facts = calc_sector_outlook(ticker, sector)
    macro = calc_macro(sector)
    moat_proxies = calc_moat_proxies(bundle)
    peer_comparison = calc_peer_comparison(ticker)

    sources_succeeded = list(bundle.sources_succeeded)
    sources_failed = list(bundle.sources_failed)
    if peer_comparison is not None:
        sources_succeeded.append("peers")
    if macro.vix_level is not None:
        sources_succeeded.append("vix")
    if macro.dollar_index_3m_change_pct is not None:
        sources_succeeded.append("dxy")
    if sector_facts.sector_etf_return_3m_pct is not None:
        sources_succeeded.append("sector_etf")

    return FactPack(
        ticker=ticker,
        company_name=info.get("longName") or info.get("shortName"),
        sector=sector,
        industry=info.get("industry"),
        business_summary=info.get("longBusinessSummary") or info.get("businessSummary"),
        country=info.get("country"),
        employees=info.get("fullTimeEmployees"),
        market_cap=info.get("marketCap"),
        sector_etf=sector_facts.sector_etf,
        sector_etf_return_3m_pct=sector_facts.sector_etf_return_3m_pct,
        sector_etf_return_ytd_pct=sector_facts.sector_etf_return_ytd_pct,
        relative_strength_vs_spy_3m=sector_facts.relative_strength_vs_spy_3m,
        geopolitical_risks=sector_facts.geopolitical_risks,
        vix_level=macro.vix_level,
        dollar_index_3m_change_pct=macro.dollar_index_3m_change_pct,
        cyclicality=macro.cyclicality,
        rsi_14d=bundle.rsi_14d,
        rsi_signal=bundle.rsi_signal,
        price_return_1m_pct=bundle.price_return_1m_pct,
        price_return_3m_pct=bundle.price_return_3m_pct,
        recent_news=bundle.news,
        moat_proxies=moat_proxies,
        peer_comparison=peer_comparison,
        sources_succeeded=sources_succeeded,
        sources_failed=sources_failed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GRANULAR GETTERS
# ─────────────────────────────────────────────────────────────────────────────


def get_moat_proxies(ticker: str, use_cache: bool = True) -> MoatQuantitativeProxies:
    """MOAT quantitative anchors (margin stability, ROIC, R&D intensity, 3y CAGR)."""
    return calc_moat_proxies(fetch_bundle(ticker, use_cache=use_cache))


def get_sector_outlook(ticker: str, use_cache: bool = True) -> SectorOutlookFacts:
    """Sector ETF momentum vs SPY and structural geopolitical risk exposure."""
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    return calc_sector_outlook(ticker, bundle.info.get("sector"))


def get_peer_comparison(ticker: str, use_cache: bool = True) -> Optional[PeerComparison]:
    """Side-by-side peer ranking (market cap, margins, growth, relative position)."""
    return calc_peer_comparison(ticker)


def get_macro(ticker: str, use_cache: bool = True) -> MacroFacts:
    """VIX, dollar index 3m change, and sector cyclicality for the ticker."""
    bundle = fetch_bundle(ticker, use_cache=use_cache)
    return calc_macro(bundle.info.get("sector"))
