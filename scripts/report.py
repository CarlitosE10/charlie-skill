"""
Pydantic models defining the CharlieReport JSON contract.

Charlie is the qualitative half of the three-agent pipeline. Its output is
consumed by Ray (the decision agent), so the schema is strict and versioned.

Schema version 1.0.0 — must align with Snowball's schema_version for Ray.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# RATING SCALES (kept simple and ordered so Ray can compare across reports)
# ─────────────────────────────────────────────────────────────────────────────

# 5-point scale used everywhere a qualitative judgment is made
QualitativeRating = Literal[
    "very_weak",
    "weak",
    "neutral",
    "strong",
    "very_strong",
]

MoatType = Literal[
    "intangible_assets",
    "switching_costs",
    "network_effects",
    "cost_advantages",
    "efficient_scale",
    "none",
]

OutlookRating = Literal["bearish", "cautious", "neutral", "constructive", "bullish"]

GrowthSignal = Literal["decelerate", "maintain", "accelerate"]

ConcentrationLevel = Literal["very_low", "low", "moderate", "high", "very_high"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. PRODUCT ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────


class ProductAnalysis(BaseModel):
    """What does the company sell? How defensible is it?"""

    description: str = Field(..., description="Plain-language description of the core business")
    core_products: list[str] = Field(default_factory=list, description="Main product/service lines")
    revenue_concentration: Optional[str] = Field(
        None, description="Whether revenue is concentrated in one product or diversified"
    )
    pricing_power: QualitativeRating = "neutral"
    pricing_power_reasoning: str = ""
    substitutability: QualitativeRating = "neutral"
    substitutability_reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 2. SECTOR OUTLOOK
# ─────────────────────────────────────────────────────────────────────────────


class GeopoliticalRisk(BaseModel):
    event: str
    impact: str
    severity: QualitativeRating


class SectorOutlook(BaseModel):
    """Where is the sector headed?"""

    sector: Optional[str] = None
    industry: Optional[str] = None
    sector_etf: Optional[str] = None
    sector_etf_return_3m_pct: Optional[float] = None
    sector_etf_return_ytd_pct: Optional[float] = None
    relative_strength_vs_spy_3m: Optional[float] = Field(
        None, description="Sector ETF return − SPY return (3m), in pct points"
    )
    sector_maturity: Literal["emerging", "growth", "mature", "declining", "unknown"] = "unknown"
    barriers_to_entry: QualitativeRating = "neutral"
    disruption_risk: QualitativeRating = "neutral"
    geopolitical_risks: list[GeopoliticalRisk] = Field(default_factory=list)
    outlook: OutlookRating = "neutral"
    outlook_reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 3. CUSTOMER ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────


class CustomerAnalysis(BaseModel):
    """Who buys, and how locked-in are they?"""

    customer_type: Literal["B2B", "B2C", "mixed", "unknown"] = "unknown"
    customer_concentration: ConcentrationLevel = "moderate"
    customer_concentration_reasoning: str = ""
    switching_costs: QualitativeRating = "neutral"
    switching_costs_reasoning: str = ""
    customer_loyalty: QualitativeRating = "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# 4. SUPPLIER ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────


class SupplierAnalysis(BaseModel):
    """Who feeds the business, and how vulnerable is the chain?"""

    supplier_concentration: ConcentrationLevel = "moderate"
    supplier_concentration_reasoning: str = ""
    supplier_negotiating_power: QualitativeRating = "neutral"
    critical_inputs: list[str] = Field(
        default_factory=list, description="Inputs whose availability/price is critical (e.g., 'cobalt', 'cloud capacity')"
    )
    supply_chain_risk: QualitativeRating = "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# 5. MACRO ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────


class MacroEnvironment(BaseModel):
    """Macro tailwinds and headwinds."""

    interest_rate_sensitivity: QualitativeRating = "neutral"
    interest_rate_reasoning: str = ""
    fx_sensitivity: QualitativeRating = "neutral"
    fx_reasoning: str = ""
    regulatory_environment: QualitativeRating = "neutral"
    regulatory_reasoning: str = ""
    cyclicality: Literal["defensive", "neutral", "cyclical", "highly_cyclical", "unknown"] = "unknown"
    inflation_sensitivity: QualitativeRating = "neutral"
    overall_macro_tailwind: QualitativeRating = "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# 6. MOAT
# ─────────────────────────────────────────────────────────────────────────────


class MoatQuantitativeProxies(BaseModel):
    """
    Numerical fingerprints we use to anchor the MOAT assessment.
    Computed by moat_proxies.py from yfinance financials.
    """

    gross_margin_avg: Optional[float] = Field(None, description="Average gross margin (last 4y)")
    gross_margin_stability: Optional[float] = Field(
        None,
        description="Coefficient of variation of gross margin — lower = more stable",
    )
    operating_margin_avg: Optional[float] = None
    operating_margin_stability: Optional[float] = None
    roic_avg: Optional[float] = Field(None, description="Average return on invested capital")
    roic_stability: Optional[float] = None
    rd_intensity_avg: Optional[float] = Field(None, description="R&D / Revenue")
    capex_intensity_avg: Optional[float] = Field(None, description="CAPEX / Revenue")
    revenue_cagr_3y: Optional[float] = None


class MoatAssessment(BaseModel):
    """The synthesized moat verdict."""

    moat_strength: QualitativeRating = "neutral"
    moat_types: list[MoatType] = Field(default_factory=list)
    moat_durability_years: Optional[int] = Field(
        None, description="Estimated years the moat is expected to remain effective"
    )
    moat_reasoning: str = ""
    proxies: MoatQuantitativeProxies = Field(default_factory=MoatQuantitativeProxies)


# ─────────────────────────────────────────────────────────────────────────────
# 7. PEER COMPARISON
# ─────────────────────────────────────────────────────────────────────────────


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
    market_cap_share_pct: Optional[float] = Field(
        None, description="Subject's market cap / total market cap of peer group"
    )
    margin_rank: Optional[int] = None
    growth_rank: Optional[int] = None
    relative_position: Literal["leader", "challenger", "follower", "laggard", "unknown"] = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# 8. CATALYSTS & RISKS
# ─────────────────────────────────────────────────────────────────────────────


class Catalyst(BaseModel):
    description: str
    horizon: Literal["short", "medium", "long"] = "medium"
    likelihood: QualitativeRating = "neutral"
    impact: QualitativeRating = "neutral"


class QualitativeRisk(BaseModel):
    description: str
    severity: QualitativeRating = "neutral"
    likelihood: QualitativeRating = "neutral"
    category: Literal["regulatory", "competitive", "execution", "macro", "geopolitical", "esg", "other"] = "other"


# ─────────────────────────────────────────────────────────────────────────────
# 9. RAY HINT — qualitative growth adjustment
# ─────────────────────────────────────────────────────────────────────────────


class GrowthAdjustment(BaseModel):
    """Hint from Charlie to Ray on whether the quantitative growth implied by
    Snowball's CAGRs should be accelerated, maintained, or decelerated based
    on qualitative factors."""

    signal: GrowthSignal = "maintain"
    suggested_adjustment_pct: Optional[float] = Field(
        None,
        description="Suggested delta to apply to base case revenue/FCF growth (in pct points). "
        "Example: -1.5 means subtract 1.5pp from Snowball's growth assumptions.",
    )
    reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY
# ─────────────────────────────────────────────────────────────────────────────


class DataQuality(BaseModel):
    completeness_pct: float = 100.0
    warnings: list[str] = Field(default_factory=list)
    data_sources_succeeded: list[str] = Field(default_factory=list)
    data_sources_failed: list[str] = Field(default_factory=list)
    synthesis_model: Optional[str] = Field(None, description="LLM model used for synthesis, if any")


# ─────────────────────────────────────────────────────────────────────────────
# TOP-LEVEL REPORT
# ─────────────────────────────────────────────────────────────────────────────


class CharlieReport(BaseModel):
    """The full qualitative report consumed by Ray."""

    schema_version: str = SCHEMA_VERSION
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    fetch_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # The 5 Buffett dimensions
    product_analysis: Optional[ProductAnalysis] = None
    sector_outlook: Optional[SectorOutlook] = None
    customer_analysis: Optional[CustomerAnalysis] = None
    supplier_analysis: Optional[SupplierAnalysis] = None
    macro_environment: Optional[MacroEnvironment] = None

    # MOAT (the headline qualitative output)
    moat: Optional[MoatAssessment] = None

    # Peer comparison
    peer_comparison: Optional[PeerComparison] = None

    # Catalysts & risks
    catalysts: list[Catalyst] = Field(default_factory=list)
    qualitative_risks: list[QualitativeRisk] = Field(default_factory=list)

    # Hint for Ray
    growth_adjustment: Optional[GrowthAdjustment] = None

    # Aggregate qualitative score (0-100)
    qualitative_score: Optional[int] = Field(
        None, description="Composite qualitative score, 0-100 — higher = better business"
    )

    # Data provenance
    data_quality: DataQuality = Field(default_factory=DataQuality)


# ─────────────────────────────────────────────────────────────────────────────
# FACT PACK (intermediate structure passed to the synthesizer)
# ─────────────────────────────────────────────────────────────────────────────


class FactPack(BaseModel):
    """
    The structured collection of deterministic facts gathered before LLM
    synthesis. The synthesizer reads this + reference frameworks and produces
    the qualitative judgments in CharlieReport.
    """

    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    business_summary: Optional[str] = None
    country: Optional[str] = None
    employees: Optional[int] = None
    market_cap: Optional[float] = None

    # Sector facts
    sector_etf: Optional[str] = None
    sector_etf_return_3m_pct: Optional[float] = None
    sector_etf_return_ytd_pct: Optional[float] = None
    relative_strength_vs_spy_3m: Optional[float] = None

    # Geopolitical
    geopolitical_risks: list[GeopoliticalRisk] = Field(default_factory=list)

    # Macro snapshot
    vix_level: Optional[float] = None
    dollar_index_3m_change_pct: Optional[float] = None

    # MOAT proxies (the quantitative anchors)
    moat_proxies: MoatQuantitativeProxies = Field(default_factory=MoatQuantitativeProxies)

    # Peers
    peer_comparison: Optional[PeerComparison] = None

    # Provenance
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
