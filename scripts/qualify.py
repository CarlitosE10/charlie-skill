#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.40",
#     "pandas>=2.0.0",
#     "numpy>=1.24.0",
#     "pydantic>=2.0.0",
#     "anthropic>=0.40.0",
# ]
# ///
"""
Qualitative stock analysis skill — report models, LLM synthesis, CLI.

Two-layer architecture:
  1. Deterministic layer (analysis.py): MOAT proxies, sector ETF momentum,
     peer comparison, macro snapshot, geopolitical risks, RSI, price returns,
     news. Always runs; no API key required.
  2. Synthesis layer (this file): Anthropic API call that takes the FactPack
     and produces qualitative judgments (Buffett 5D, MOAT rating, catalysts,
     risks, growth signal, qualitative score). Skips gracefully if no API key.

Usage (CLI):
    uv run qualify.py analyze AAPL
    uv run qualify.py analyze AAPL --format text
    uv run qualify.py facts NVDA --format text
    uv run qualify.py moat GOOGL --format text
    uv run qualify.py sector XOM --format text
    uv run qualify.py peers MSFT --format text
    uv run qualify.py macro TSLA --format text
    uv run qualify.py news AMZN --format text

Agent import API:
    from qualify import run_analysis
    from analysis import (
        get_moat_proxies, get_sector_outlook,
        get_peer_comparison, get_macro, build_fact_pack,
    )
    from data import get_rsi, get_recent_news, get_price_returns

    report = run_analysis("AAPL")           # QualReport — full synthesis
    moat   = get_moat_proxies("NVDA")       # MoatQuantitativeProxies
    sector = get_sector_outlook("XOM")      # SectorOutlookFacts
    peers  = get_peer_comparison("MSFT")    # Optional[PeerComparison]
    macro  = get_macro("TSLA")              # MacroFacts
    rsi, signal = get_rsi("AAPL")           # (float | None, str | None)
    news   = get_recent_news("AMZN")        # list[str]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from analysis import (
    FactPack,
    GeopoliticalRisk,
    MoatQuantitativeProxies,
    PeerComparison,
    SectorOutlookFacts,
    build_fact_pack,
    calc_macro,
    calc_moat_proxies,
    calc_peer_comparison,
    calc_sector_outlook,
)
from data import fetch_bundle, get_recent_news, get_rsi, get_price_returns

SYNTHESIS_MODEL = "claude-sonnet-4-6"
REFERENCES_DIR = Path(__file__).parent.parent / "references"
SCHEMA_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# REPORT MODELS
# ─────────────────────────────────────────────────────────────────────────────

QualitativeRating = Literal["very_weak", "weak", "neutral", "strong", "very_strong"]
MoatType = Literal[
    "intangible_assets", "switching_costs", "network_effects",
    "cost_advantages", "efficient_scale", "none",
]
OutlookRating = Literal["bearish", "cautious", "neutral", "constructive", "bullish"]
GrowthSignal = Literal["decelerate", "maintain", "accelerate"]
ConcentrationLevel = Literal["very_low", "low", "moderate", "high", "very_high"]


class ProductAnalysis(BaseModel):
    description: str = Field(..., description="Plain-language description of the core business")
    core_products: list[str] = Field(default_factory=list)
    revenue_concentration: Optional[str] = None
    pricing_power: QualitativeRating = "neutral"
    pricing_power_reasoning: str = ""
    substitutability: QualitativeRating = "neutral"
    substitutability_reasoning: str = ""


class SectorOutlookQual(BaseModel):
    sector: Optional[str] = None
    industry: Optional[str] = None
    sector_etf: Optional[str] = None
    sector_etf_return_3m_pct: Optional[float] = None
    sector_etf_return_ytd_pct: Optional[float] = None
    relative_strength_vs_spy_3m: Optional[float] = None
    sector_maturity: Literal["emerging", "growth", "mature", "declining", "unknown"] = "unknown"
    barriers_to_entry: QualitativeRating = "neutral"
    disruption_risk: QualitativeRating = "neutral"
    geopolitical_risks: list[GeopoliticalRisk] = Field(default_factory=list)
    outlook: OutlookRating = "neutral"
    outlook_reasoning: str = ""


class CustomerAnalysis(BaseModel):
    customer_type: Literal["B2B", "B2C", "mixed", "unknown"] = "unknown"
    customer_concentration: ConcentrationLevel = "moderate"
    customer_concentration_reasoning: str = ""
    switching_costs: QualitativeRating = "neutral"
    switching_costs_reasoning: str = ""
    customer_loyalty: QualitativeRating = "neutral"


class SupplierAnalysis(BaseModel):
    supplier_concentration: ConcentrationLevel = "moderate"
    supplier_concentration_reasoning: str = ""
    supplier_negotiating_power: QualitativeRating = "neutral"
    critical_inputs: list[str] = Field(default_factory=list)
    supply_chain_risk: QualitativeRating = "neutral"


class MacroEnvironment(BaseModel):
    interest_rate_sensitivity: QualitativeRating = "neutral"
    interest_rate_reasoning: str = ""
    fx_sensitivity: QualitativeRating = "neutral"
    fx_reasoning: str = ""
    regulatory_environment: QualitativeRating = "neutral"
    regulatory_reasoning: str = ""
    cyclicality: Literal["defensive", "neutral", "cyclical", "highly_cyclical", "unknown"] = "unknown"
    inflation_sensitivity: QualitativeRating = "neutral"
    overall_macro_tailwind: QualitativeRating = "neutral"


class MoatAssessment(BaseModel):
    moat_score: Optional[int] = Field(None, description="1 (none) to 5 (extraordinary)")
    moat_strength: QualitativeRating = "neutral"
    moat_types: list[MoatType] = Field(default_factory=list)
    moat_durability_years: Optional[int] = None
    moat_reasoning: str = ""
    proxies: MoatQuantitativeProxies = Field(default_factory=MoatQuantitativeProxies)


class Catalyst(BaseModel):
    description: str
    horizon: Literal["short", "medium", "long"] = "medium"
    likelihood: QualitativeRating = "neutral"
    impact: QualitativeRating = "neutral"


class QualRisk(BaseModel):
    description: str
    severity: QualitativeRating = "neutral"
    likelihood: QualitativeRating = "neutral"
    category: Literal["regulatory", "competitive", "execution", "macro", "geopolitical", "esg", "other"] = "other"


class GrowthAdjustment(BaseModel):
    signal: GrowthSignal = "maintain"
    suggested_adjustment_pct: Optional[float] = Field(
        None, description="Suggested pp delta to apply to baseline growth assumptions"
    )
    reasoning: str = ""


class DataQuality(BaseModel):
    completeness_pct: float = 100.0
    warnings: list[str] = Field(default_factory=list)
    data_sources_succeeded: list[str] = Field(default_factory=list)
    data_sources_failed: list[str] = Field(default_factory=list)
    synthesis_model: Optional[str] = None


class QualReport(BaseModel):
    """Full qualitative report produced by run_analysis()."""

    schema_version: str = SCHEMA_VERSION
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    fetch_timestamp: datetime = Field(default_factory=datetime.utcnow)

    product_analysis: Optional[ProductAnalysis] = None
    sector_outlook: Optional[SectorOutlookQual] = None
    customer_analysis: Optional[CustomerAnalysis] = None
    supplier_analysis: Optional[SupplierAnalysis] = None
    macro_environment: Optional[MacroEnvironment] = None
    moat: Optional[MoatAssessment] = None
    peer_comparison: Optional[PeerComparison] = None
    catalysts: list[Catalyst] = Field(default_factory=list)
    qualitative_risks: list[QualRisk] = Field(default_factory=list)
    growth_adjustment: Optional[GrowthAdjustment] = None
    qualitative_score: Optional[int] = Field(None, description="0-100, higher = better business quality")
    business_verdict: Optional[Literal["strong", "acceptable", "weak"]] = Field(
        None, description="Overall business quality verdict based on moat + sector + macro"
    )
    data_quality: DataQuality = Field(default_factory=DataQuality)


class _SynthesisOutput(BaseModel):
    product_analysis: ProductAnalysis
    sector_outlook_qualitative: SectorOutlookQual
    customer_analysis: CustomerAnalysis
    supplier_analysis: SupplierAnalysis
    macro_environment: MacroEnvironment
    moat: MoatAssessment
    catalysts: list[Catalyst] = Field(default_factory=list)
    qualitative_risks: list[QualRisk] = Field(default_factory=list)
    growth_adjustment: GrowthAdjustment
    qualitative_score: int = Field(..., ge=0, le=100)
    business_verdict: Literal["strong", "acceptable", "weak"] = "acceptable"


# ─────────────────────────────────────────────────────────────────────────────
# LLM SYNTHESIS
# ─────────────────────────────────────────────────────────────────────────────


def _load_ref(name: str) -> str:
    path = REFERENCES_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _system_prompt() -> str:
    buffett = _load_ref("buffett_5d.md")
    moat = _load_ref("moat_taxonomy.md")
    glossary = _load_ref("qualitative_glossary.md")
    return f"""You are a senior competitive strategist and macro analyst with a background
in investment research. Your role is to give qualitative context to numbers — the "why"
behind the ratios — by evaluating whether a business has durable competitive advantages
and whether the macro environment supports or threatens it.

You output STRICT JSON. You do NOT make BUY/SELL/HOLD recommendations. You DO assess the
quality of the business itself (business_verdict: strong / acceptable / weak).

You must be:
- Grounded: anchor every claim to a specific fact in the fact pack. No generic statements.
- Direct: if the moat is weak, say so. Calibrated does not mean vague.
- Concise: reasoning fields are 1-2 sentences. No padding.
- Scored: moat_score is 1 (no moat) to 5 (extraordinary, durable moat).

────────── BUFFETT 5-DIMENSION FRAMEWORK ──────────
{buffett}

────────── MOAT TAXONOMY ──────────
{moat}

────────── RATING SCALES ──────────
{glossary}
"""


def _user_message(factpack: FactPack) -> str:
    return f"""Below is the fact pack for {factpack.ticker}. Use it to fill out the requested
qualitative assessment.

────────── FACT PACK ──────────
{factpack.model_dump_json(indent=2)}

────────── INSTRUCTIONS ──────────
Produce a JSON object with the following top-level keys:

- product_analysis
- sector_outlook_qualitative   (qualitative fields only: sector_maturity, barriers_to_entry,
                                disruption_risk, outlook, outlook_reasoning; deterministic
                                fields will be merged in afterward)
- customer_analysis
- supplier_analysis
- macro_environment
- moat                         (include moat_score 1-5; leave proxies null — merged after)
- catalysts                    (list of 0-5 forward-looking catalysts)
- qualitative_risks            (list of 0-5 qualitative risks)
- growth_adjustment            (qualitative growth signal for consuming agents)
- qualitative_score            (integer 0-100; weight: moat 40, sector 20, macro 15, customer 15, supplier 10)
- business_verdict             ("strong" | "acceptable" | "weak" — overall business quality,
                                NOT a stock recommendation; based on moat durability + sector + macro)

Output ONLY the JSON object. No prose before or after. No markdown fences."""


def _synthesize(factpack: FactPack, api_key: Optional[str], model: str) -> Optional[_SynthesisOutput]:
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None

    try:
        resp = Anthropic(api_key=key).messages.create(
            model=model,
            max_tokens=4096,
            system=_system_prompt(),
            messages=[{"role": "user", "content": _user_message(factpack)}],
        )
    except Exception as e:
        print(f"[qualify] API call failed: {e}", file=sys.stderr)
        return None

    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().removesuffix("```").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[qualify] JSON parse failed: {e}\nRaw (500): {text[:500]}", file=sys.stderr)
        return None

    try:
        sq = data.get("sector_outlook_qualitative", {})
        sq.setdefault("sector", factpack.sector)
        sq.setdefault("industry", factpack.industry)
        sq.setdefault("sector_etf", factpack.sector_etf)
        sq.setdefault("sector_etf_return_3m_pct", factpack.sector_etf_return_3m_pct)
        sq.setdefault("sector_etf_return_ytd_pct", factpack.sector_etf_return_ytd_pct)
        sq.setdefault("relative_strength_vs_spy_3m", factpack.relative_strength_vs_spy_3m)
        sq.setdefault("geopolitical_risks", [g.model_dump() for g in factpack.geopolitical_risks])
        data["sector_outlook_qualitative"] = sq
        return _SynthesisOutput.model_validate(data)
    except Exception as e:
        print(f"[qualify] Pydantic validation failed: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────


def run_analysis(
    ticker: str,
    use_cache: bool = True,
    api_key: Optional[str] = None,
    model: str = SYNTHESIS_MODEL,
) -> QualReport:
    """
    Full qualitative analysis of a stock ticker. Returns a QualReport.

    Without ANTHROPIC_API_KEY, returns a partial report with deterministic
    facts only (sector outlook, MOAT proxies, peer comparison, macro, RSI, news).

    Examples:
        report = run_analysis("AAPL")
        print(report.moat.moat_strength)       # "very_strong"
        print(report.qualitative_score)         # 82
        print(report.sector_outlook.outlook)    # "constructive"
        print(report.data_quality.completeness_pct)
    """
    factpack = build_fact_pack(ticker, use_cache=use_cache)

    deterministic_sector = SectorOutlookQual(
        sector=factpack.sector,
        industry=factpack.industry,
        sector_etf=factpack.sector_etf,
        sector_etf_return_3m_pct=factpack.sector_etf_return_3m_pct,
        sector_etf_return_ytd_pct=factpack.sector_etf_return_ytd_pct,
        relative_strength_vs_spy_3m=factpack.relative_strength_vs_spy_3m,
        geopolitical_risks=factpack.geopolitical_risks,
    )

    synthesis = _synthesize(factpack, api_key=api_key, model=model)
    warnings: list[str] = []

    if synthesis is None:
        warnings.append(
            "LLM synthesis unavailable — qualitative judgments not produced. "
            "Set ANTHROPIC_API_KEY and rerun. Deterministic facts are still present."
        )
        return QualReport(
            ticker=factpack.ticker,
            company_name=factpack.company_name,
            sector=factpack.sector,
            industry=factpack.industry,
            sector_outlook=deterministic_sector,
            moat=MoatAssessment(proxies=factpack.moat_proxies),
            peer_comparison=factpack.peer_comparison,
            data_quality=DataQuality(
                completeness_pct=40.0,
                warnings=warnings,
                data_sources_succeeded=factpack.sources_succeeded,
                data_sources_failed=factpack.sources_failed,
            ),
        )

    moat_final = synthesis.moat.model_copy(update={
        "proxies": factpack.moat_proxies,
        "moat_score": synthesis.moat.moat_score,
    })

    completeness = 100.0
    if not factpack.sector_etf:
        completeness -= 5
    if factpack.peer_comparison is None:
        completeness -= 10
        warnings.append("No peers in curated map — peer comparison skipped.")
    if factpack.vix_level is None:
        completeness -= 3
    if factpack.business_summary is None:
        completeness -= 5
        warnings.append("No business summary — narrative judgments are weaker.")
    if factpack.moat_proxies.gross_margin_avg is None:
        completeness -= 10
        warnings.append("Gross margin history missing — MOAT proxies are partial.")

    return QualReport(
        ticker=factpack.ticker,
        company_name=factpack.company_name,
        sector=factpack.sector,
        industry=factpack.industry,
        product_analysis=synthesis.product_analysis,
        sector_outlook=synthesis.sector_outlook_qualitative,
        customer_analysis=synthesis.customer_analysis,
        supplier_analysis=synthesis.supplier_analysis,
        macro_environment=synthesis.macro_environment,
        moat=moat_final,
        peer_comparison=factpack.peer_comparison,
        catalysts=synthesis.catalysts,
        qualitative_risks=synthesis.qualitative_risks,
        growth_adjustment=synthesis.growth_adjustment,
        qualitative_score=synthesis.qualitative_score,
        business_verdict=synthesis.business_verdict,
        data_quality=DataQuality(
            completeness_pct=round(completeness, 1),
            warnings=warnings,
            data_sources_succeeded=factpack.sources_succeeded,
            data_sources_failed=factpack.sources_failed,
            synthesis_model=model,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEXT RENDERING
# ─────────────────────────────────────────────────────────────────────────────


def _fp(x, d=1):
    if x is None:
        return "—"
    return f"{x * 100:.{d}f}%" if abs(x) < 5 else f"{x:.{d}f}%"


def _fn(x, d=2):
    return "—" if x is None else f"{x:.{d}f}"


def _fm(x):
    if x is None:
        return "—"
    if abs(x) >= 1e12:
        return f"${x/1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x/1e9:.2f}B"
    return f"${x/1e6:.2f}M"


def _hr(w=70):
    return "─" * w


def _render(report: QualReport) -> None:
    print(f"QUALITATIVE ANALYSIS: {report.ticker}")
    print(_hr())
    print(f"  Company:    {report.company_name or '—'}")
    print(f"  Sector:     {report.sector or '—'}")
    print(f"  Industry:   {report.industry or '—'}")
    if report.qualitative_score is not None:
        print(f"  Score:      {report.qualitative_score}/100")
    if report.business_verdict is not None:
        print(f"  Verdict:    {report.business_verdict.upper()}")
    print()

    if report.product_analysis:
        pa = report.product_analysis
        print("─ PRODUCT ─")
        print(f"  {pa.description}")
        if pa.core_products:
            print(f"  Products: {', '.join(pa.core_products)}")
        print(f"  Pricing power:    {pa.pricing_power}  ({pa.pricing_power_reasoning})")
        print(f"  Substitutability: {pa.substitutability}  ({pa.substitutability_reasoning})")
        print()

    if report.sector_outlook:
        so = report.sector_outlook
        print("─ SECTOR ─")
        print(f"  ETF: {so.sector_etf or '—'}  |  3m: {_fn(so.sector_etf_return_3m_pct, 1)}%  YTD: {_fn(so.sector_etf_return_ytd_pct, 1)}%")
        if so.relative_strength_vs_spy_3m is not None:
            print(f"  Rel. vs SPY (3m): {so.relative_strength_vs_spy_3m:+.1f}pp")
        print(f"  Maturity: {so.sector_maturity}  |  Barriers: {so.barriers_to_entry}  |  Disruption: {so.disruption_risk}")
        print(f"  Outlook: {so.outlook.upper()}  — {so.outlook_reasoning}")
        if so.geopolitical_risks:
            print("  Geopolitical risks:")
            for g in so.geopolitical_risks:
                print(f"    • [{g.severity}] {g.event} — {g.impact}")
        print()

    if report.moat:
        m = report.moat
        print("─ MOAT ─")
        if m.moat_score is not None:
            print(f"  Score:      {m.moat_score}/5")
        print(f"  Strength:   {m.moat_strength}")
        if m.moat_types:
            print(f"  Types:      {', '.join(m.moat_types)}")
        if m.moat_durability_years:
            print(f"  Durability: ~{m.moat_durability_years} years")
        print(f"  Reasoning:  {m.moat_reasoning}")
        p = m.proxies
        print(f"  Anchors:")
        print(f"    Gross margin avg/cv:  {_fp(p.gross_margin_avg)} / {_fn(p.gross_margin_stability, 3)}")
        print(f"    Op. margin avg/cv:    {_fp(p.operating_margin_avg)} / {_fn(p.operating_margin_stability, 3)}")
        print(f"    ROIC avg/cv:          {_fp(p.roic_avg)} / {_fn(p.roic_stability, 3)}")
        print(f"    R&D intensity:        {_fp(p.rd_intensity_avg)}")
        print(f"    Revenue 3y CAGR:      {_fp(p.revenue_cagr_3y)}")
        print()

    if report.customer_analysis:
        ca = report.customer_analysis
        print("─ CUSTOMER ─")
        print(f"  Type: {ca.customer_type}  |  Concentration: {ca.customer_concentration}")
        print(f"  Switching costs: {ca.switching_costs} — {ca.switching_costs_reasoning}")
        print()

    if report.supplier_analysis:
        sa = report.supplier_analysis
        print("─ SUPPLIER ─")
        print(f"  Concentration: {sa.supplier_concentration}  |  Power: {sa.supplier_negotiating_power}")
        if sa.critical_inputs:
            print(f"  Critical inputs: {', '.join(sa.critical_inputs)}")
        print()

    if report.macro_environment:
        me = report.macro_environment
        print("─ MACRO ─")
        print(f"  Cyclicality:      {me.cyclicality}")
        print(f"  Rate sensitivity: {me.interest_rate_sensitivity} — {me.interest_rate_reasoning}")
        print(f"  FX sensitivity:   {me.fx_sensitivity}")
        print(f"  Regulatory env:   {me.regulatory_environment}")
        print()

    if report.peer_comparison:
        pc = report.peer_comparison
        print("─ PEERS ─")
        print(f"  Position: {pc.relative_position.upper()}")
        if pc.market_cap_rank is not None:
            print(f"  Cap rank: #{pc.market_cap_rank}  ({_fn(pc.market_cap_share_pct, 1)}% of group)")
        print(f"  {'Ticker':<8} {'Mkt Cap':>10} {'Op Mgn':>8} {'P/E':>8} {'Rev YoY':>10}")
        for peer in pc.peers:
            print(f"  {peer.ticker:<8} {_fm(peer.market_cap):>10} {_fp(peer.operating_margin):>8} {_fn(peer.pe_ratio, 1):>8} {_fp(peer.revenue_growth_yoy):>10}")
        print()

    if report.catalysts:
        print("─ CATALYSTS ─")
        for c in report.catalysts:
            print(f"  • [{c.horizon}] {c.description}")
        print()

    if report.qualitative_risks:
        print("─ RISKS ─")
        for r in report.qualitative_risks:
            print(f"  • [{r.category} | {r.severity}] {r.description}")
        print()

    if report.growth_adjustment:
        ga = report.growth_adjustment
        delta = f" ({ga.suggested_adjustment_pct:+.1f}pp)" if ga.suggested_adjustment_pct is not None else ""
        print(f"─ GROWTH SIGNAL ─")
        print(f"  {ga.signal.upper()}{delta} — {ga.reasoning}")
        print()

    if report.data_quality.warnings:
        print("─ DATA QUALITY ─")
        for w in report.data_quality.warnings:
            print(f"  ! {w}")
        print(f"  Completeness: {report.data_quality.completeness_pct}%")
        print()

    print("Not financial advice. For informational purposes only.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _emit(obj: Any) -> None:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, list):
        data = [o.model_dump() if hasattr(o, "model_dump") else o for o in obj]
    else:
        data = obj
    print(json.dumps(data, indent=2, default=str))


def _cmd_analyze(args):
    report = run_analysis(args.ticker, use_cache=not args.no_cache)
    _emit(report) if args.format == "json" else _render(report)


def _cmd_facts(args):
    fp = build_fact_pack(args.ticker, use_cache=not args.no_cache)
    if args.format == "json":
        _emit(fp)
        return
    print(f"FACT PACK — {fp.ticker}")
    print(_hr())
    print(f"  Company:  {fp.company_name or '—'}  ({fp.sector or '—'} / {fp.industry or '—'})")
    print(f"  Country:  {fp.country or '—'}  |  Employees: {fp.employees or '—'}")
    print(f"  Mkt Cap:  {_fm(fp.market_cap)}")
    if fp.business_summary:
        s = fp.business_summary[:400] + ("…" if len(fp.business_summary) > 400 else "")
        print(f"\n  {s}")
    print(f"\n  RSI(14): {fp.rsi_14d or '—'}  ({fp.rsi_signal or '—'})")
    print(f"  1m return: {_fn(fp.price_return_1m_pct, 1)}%  |  3m: {_fn(fp.price_return_3m_pct, 1)}%")
    if fp.recent_news:
        print("\n  Recent news:")
        for h in fp.recent_news:
            print(f"    • {h}")
    print(f"\n  Sector ETF: {fp.sector_etf or '—'}  3m: {_fn(fp.sector_etf_return_3m_pct, 1)}%  YTD: {_fn(fp.sector_etf_return_ytd_pct, 1)}%")
    if fp.relative_strength_vs_spy_3m is not None:
        print(f"  Rel. vs SPY (3m): {fp.relative_strength_vs_spy_3m:+.1f}pp")
    print(f"  VIX: {_fn(fp.vix_level, 1)}  |  DXY 3m: {_fn(fp.dollar_index_3m_change_pct, 1)}%  |  Cyclicality: {fp.cyclicality}")
    if fp.geopolitical_risks:
        print("\n  Geopolitical risks:")
        for g in fp.geopolitical_risks:
            print(f"    • [{g.severity}] {g.event}")
    p = fp.moat_proxies
    print(f"\n  MOAT proxies:")
    print(f"    Gross margin:   {_fp(p.gross_margin_avg)} avg / cv={_fn(p.gross_margin_stability, 3)}")
    print(f"    Op. margin:     {_fp(p.operating_margin_avg)} avg / cv={_fn(p.operating_margin_stability, 3)}")
    print(f"    ROIC:           {_fp(p.roic_avg)} avg / cv={_fn(p.roic_stability, 3)}")
    print(f"    Revenue 3y CAGR: {_fp(p.revenue_cagr_3y)}")


def _cmd_moat(args):
    bundle = fetch_bundle(args.ticker, use_cache=not args.no_cache)
    p = calc_moat_proxies(bundle)
    if args.format == "json":
        _emit(p)
        return
    print(f"MOAT PROXIES — {args.ticker.upper()}")
    print(_hr(40))
    print(f"  Gross margin avg / cv:  {_fp(p.gross_margin_avg)} / {_fn(p.gross_margin_stability, 3)}")
    print(f"  Op. margin avg / cv:    {_fp(p.operating_margin_avg)} / {_fn(p.operating_margin_stability, 3)}")
    print(f"  ROIC avg / cv:          {_fp(p.roic_avg)} / {_fn(p.roic_stability, 3)}")
    print(f"  R&D intensity:          {_fp(p.rd_intensity_avg)}")
    print(f"  CAPEX intensity:        {_fp(p.capex_intensity_avg)}")
    print(f"  Revenue 3y CAGR:        {_fp(p.revenue_cagr_3y)}")
    print("\nNote: MOAT qualitative rating requires synthesis. Use 'analyze' for the full assessment.")


def _cmd_sector(args):
    bundle = fetch_bundle(args.ticker, use_cache=not args.no_cache)
    facts = calc_sector_outlook(args.ticker, bundle.info.get("sector"))
    if args.format == "json":
        _emit(facts)
        return
    print(f"SECTOR OUTLOOK — {args.ticker.upper()}  ({facts.sector or 'unknown'})")
    print(_hr())
    print(f"  ETF: {facts.sector_etf or '—'}  3m: {_fn(facts.sector_etf_return_3m_pct, 1)}%  YTD: {_fn(facts.sector_etf_return_ytd_pct, 1)}%")
    if facts.relative_strength_vs_spy_3m is not None:
        print(f"  Rel. vs SPY (3m): {facts.relative_strength_vs_spy_3m:+.1f}pp")
    if facts.geopolitical_risks:
        print("\n  Geopolitical risks:")
        for g in facts.geopolitical_risks:
            print(f"    • [{g.severity}] {g.event}\n      → {g.impact}")
    else:
        print("\n  No baseline geopolitical risks flagged.")


def _cmd_peers(args):
    pc = calc_peer_comparison(args.ticker)
    if args.format == "json":
        _emit(pc)
        return
    if pc is None:
        print(f"No curated peers for {args.ticker.upper()}.")
        return
    print(f"PEER COMPARISON — {args.ticker.upper()}")
    print(_hr())
    print(f"  Position: {pc.relative_position.upper()}")
    if pc.market_cap_rank is not None:
        print(f"  Cap rank: #{pc.market_cap_rank}  ({_fn(pc.market_cap_share_pct, 1)}% of group)")
    print(f"  {'Ticker':<8} {'Mkt Cap':>10} {'Gross':>8} {'Op Mgn':>8} {'P/E':>8} {'Rev YoY':>10}")
    for p in pc.peers:
        print(f"  {p.ticker:<8} {_fm(p.market_cap):>10} {_fp(p.gross_margin):>8} {_fp(p.operating_margin):>8} {_fn(p.pe_ratio, 1):>8} {_fp(p.revenue_growth_yoy):>10}")


def _cmd_macro(args):
    bundle = fetch_bundle(args.ticker, use_cache=not args.no_cache)
    facts = calc_macro(bundle.info.get("sector"))
    if args.format == "json":
        _emit(facts)
        return
    print(f"MACRO — {args.ticker.upper()}  ({bundle.info.get('sector') or 'unknown'})")
    print(_hr(40))
    print(f"  VIX:              {_fn(facts.vix_level, 1)}")
    print(f"  Dollar index 3m:  {_fn(facts.dollar_index_3m_change_pct, 1)}%")
    print(f"  Cyclicality:      {facts.cyclicality}")


def _cmd_news(args):
    news = get_recent_news(args.ticker, use_cache=not args.no_cache)
    if args.format == "json":
        print(json.dumps(news, indent=2))
        return
    print(f"RECENT NEWS — {args.ticker.upper()}")
    if not news:
        print("  No headlines available.")
        return
    for i, h in enumerate(news, 1):
        print(f"  {i}. {h}")


def main():
    p = argparse.ArgumentParser(prog="qualify", description="Qualitative stock analysis skill")
    sub = p.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["json", "text"], default="json")
    common.add_argument("--no-cache", action="store_true", help="Bypass the 1h disk cache")

    for cmd, help_text, handler in [
        ("analyze", "Full qualitative report", _cmd_analyze),
        ("facts", "Deterministic fact pack (no LLM)", _cmd_facts),
        ("moat", "MOAT quantitative proxies", _cmd_moat),
        ("sector", "Sector outlook + geopolitical risks", _cmd_sector),
        ("peers", "Peer comparison", _cmd_peers),
        ("macro", "Macro environment snapshot", _cmd_macro),
        ("news", "Recent news headlines", _cmd_news),
    ]:
        sp = sub.add_parser(cmd, parents=[common], help=help_text)
        sp.add_argument("ticker")
        sp.set_defaults(func=handler)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
