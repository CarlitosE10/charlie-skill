"""
Pipeline orchestrator for Charlie.

Flow:
  1. Fetch the company bundle (yfinance: info, financials, balance, cashflow)
  2. Build deterministic facts:
       - sector outlook facts (ETF momentum, geopolitical risks)
       - macro facts (VIX, dollar)
       - MOAT quantitative proxies (margin stability, ROIC, R&D %, etc.)
       - peer comparison
  3. Pack them into a FactPack
  4. Call the synthesizer (LLM) → SynthesisOutput
  5. Merge deterministic facts + synthesized judgments into CharlieReport
  6. Compute data quality summary

The pipeline is robust to partial failures: if the synthesizer fails (no API
key or parse error), it returns a CharlieReport with only the deterministic
fields filled in plus a warning in data_quality.
"""

from __future__ import annotations

from typing import Optional

from data_collector import fetch_company_bundle
from macro_env import calc_macro_facts
from moat_proxies import calc_moat_proxies
from peer_analyzer import calc_peer_comparison
from report import (
    CharlieReport,
    DataQuality,
    FactPack,
    MoatAssessment,
    SectorOutlook,
)
from sector_outlook import calc_sector_outlook_facts
from synthesizer import SYNTHESIS_MODEL, synthesize


def build_fact_pack(ticker: str, use_cache: bool = True) -> FactPack:
    """Gather every deterministic fact about the ticker."""
    ticker = ticker.upper()
    bundle = fetch_company_bundle(ticker, use_cache=use_cache)
    info = bundle.info

    sector = info.get("sector")
    industry = info.get("industry")

    # 1. Sector outlook facts (ETF momentum, geopolitical risks)
    sector_facts = calc_sector_outlook_facts(sector, ticker)

    # 2. Macro facts (VIX, dollar index, cyclicality)
    macro_facts = calc_macro_facts(sector)

    # 3. MOAT proxies (margin stability, ROIC, R&D %, etc.)
    moat_proxies = calc_moat_proxies(bundle)

    # 4. Peer comparison
    peer_comparison = calc_peer_comparison(ticker, sector)

    sources_succeeded = list(bundle.sources_succeeded)
    sources_failed = list(bundle.sources_failed)
    if peer_comparison is not None:
        sources_succeeded.append("peers")
    if macro_facts.get("vix_level") is not None:
        sources_succeeded.append("vix")
    if macro_facts.get("dollar_index_3m_change_pct") is not None:
        sources_succeeded.append("dxy")
    if sector_facts.get("sector_etf_return_3m_pct") is not None:
        sources_succeeded.append("sector_etf")

    return FactPack(
        ticker=ticker,
        company_name=info.get("longName") or info.get("shortName"),
        sector=sector,
        industry=industry,
        business_summary=info.get("longBusinessSummary") or info.get("businessSummary"),
        country=info.get("country"),
        employees=info.get("fullTimeEmployees"),
        market_cap=info.get("marketCap"),
        sector_etf=sector_facts.get("sector_etf"),
        sector_etf_return_3m_pct=sector_facts.get("sector_etf_return_3m_pct"),
        sector_etf_return_ytd_pct=sector_facts.get("sector_etf_return_ytd_pct"),
        relative_strength_vs_spy_3m=sector_facts.get("relative_strength_vs_spy_3m"),
        geopolitical_risks=sector_facts.get("geopolitical_risks", []),
        vix_level=macro_facts.get("vix_level"),
        dollar_index_3m_change_pct=macro_facts.get("dollar_index_3m_change_pct"),
        moat_proxies=moat_proxies,
        peer_comparison=peer_comparison,
        sources_succeeded=sources_succeeded,
        sources_failed=sources_failed,
    )


def run_full_pipeline(
    ticker: str,
    use_cache: bool = True,
    api_key: Optional[str] = None,
    model: str = SYNTHESIS_MODEL,
) -> CharlieReport:
    """Run the full Charlie pipeline and return a CharlieReport."""

    factpack = build_fact_pack(ticker, use_cache=use_cache)

    # Compute deterministic-only sector outlook (fallback if synthesis fails)
    deterministic_sector = SectorOutlook(
        sector=factpack.sector,
        industry=factpack.industry,
        sector_etf=factpack.sector_etf,
        sector_etf_return_3m_pct=factpack.sector_etf_return_3m_pct,
        sector_etf_return_ytd_pct=factpack.sector_etf_return_ytd_pct,
        relative_strength_vs_spy_3m=factpack.relative_strength_vs_spy_3m,
        geopolitical_risks=factpack.geopolitical_risks,
    )

    # Call the synthesizer (may return None if API key missing or call fails)
    synthesis = synthesize(factpack, api_key=api_key, model=model)

    warnings: list[str] = []

    if synthesis is None:
        warnings.append(
            "LLM synthesis unavailable — qualitative judgments not produced. "
            "Check ANTHROPIC_API_KEY or rerun. Deterministic facts are still in this report."
        )
        # Build a partial MOAT assessment with only proxies
        moat = MoatAssessment(proxies=factpack.moat_proxies)
        report = CharlieReport(
            ticker=factpack.ticker,
            company_name=factpack.company_name,
            sector=factpack.sector,
            industry=factpack.industry,
            sector_outlook=deterministic_sector,
            moat=moat,
            peer_comparison=factpack.peer_comparison,
            data_quality=DataQuality(
                completeness_pct=40.0,
                warnings=warnings,
                data_sources_succeeded=factpack.sources_succeeded,
                data_sources_failed=factpack.sources_failed,
                synthesis_model=None,
            ),
        )
        return report

    # Merge deterministic + synthesized
    # Sector outlook: synthesizer fills qualitative fields, we already pre-filled deterministic ones
    merged_sector = synthesis.sector_outlook_qualitative

    # MOAT: overwrite proxies with the deterministic ones
    moat_final = synthesis.moat.model_copy(update={"proxies": factpack.moat_proxies})

    # Data quality
    completeness_pct = 100.0
    if not factpack.sector_etf:
        completeness_pct -= 5
    if factpack.peer_comparison is None:
        completeness_pct -= 10
        warnings.append("No peers found in curated map — peer comparison skipped.")
    if factpack.vix_level is None:
        completeness_pct -= 3
    if factpack.business_summary is None:
        completeness_pct -= 5
        warnings.append("No business summary from yfinance — narrative judgments are weaker.")
    if factpack.moat_proxies.gross_margin_avg is None:
        completeness_pct -= 10
        warnings.append("Gross margin history missing — MOAT proxies are partial.")

    return CharlieReport(
        ticker=factpack.ticker,
        company_name=factpack.company_name,
        sector=factpack.sector,
        industry=factpack.industry,
        product_analysis=synthesis.product_analysis,
        sector_outlook=merged_sector,
        customer_analysis=synthesis.customer_analysis,
        supplier_analysis=synthesis.supplier_analysis,
        macro_environment=synthesis.macro_environment,
        moat=moat_final,
        peer_comparison=factpack.peer_comparison,
        catalysts=synthesis.catalysts,
        qualitative_risks=synthesis.qualitative_risks,
        growth_adjustment=synthesis.growth_adjustment,
        qualitative_score=synthesis.qualitative_score,
        data_quality=DataQuality(
            completeness_pct=round(completeness_pct, 1),
            warnings=warnings,
            data_sources_succeeded=factpack.sources_succeeded,
            data_sources_failed=factpack.sources_failed,
            synthesis_model=model,
        ),
    )
