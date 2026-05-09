"""
Qualitative synthesis layer.

Takes the deterministic FactPack and reference frameworks (Buffett 5D, MOAT
taxonomy) and produces the qualitative judgments that fill out CharlieReport.

Uses the Anthropic API. The model receives:
  • The factpack as structured JSON (so it can ground its reasoning)
  • The Buffett 5D framework and MOAT taxonomy as system context
  • A request for a strict JSON output matching a sub-schema

The schema-binding happens via Pydantic on the output side: we parse the
model's response into the matching Pydantic models.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from pydantic import BaseModel, Field

from report import (
    CustomerAnalysis,
    GrowthAdjustment,
    MacroEnvironment,
    MoatAssessment,
    ProductAnalysis,
    QualitativeRisk,
    SectorOutlook,
    SupplierAnalysis,
    Catalyst,
    FactPack,
)


SYNTHESIS_MODEL = "claude-sonnet-4-5-20250929"
REFERENCES_DIR = Path(__file__).parent.parent / "references"


class SynthesisOutput(BaseModel):
    """
    The structured output we ask the LLM to produce. This is one big object so
    we can do a single API call rather than 5 separate ones.
    """

    product_analysis: ProductAnalysis
    sector_outlook_qualitative: SectorOutlook  # we pre-fill the deterministic fields and ask the LLM only for the qualitative ones
    customer_analysis: CustomerAnalysis
    supplier_analysis: SupplierAnalysis
    macro_environment: MacroEnvironment
    moat: MoatAssessment
    catalysts: list[Catalyst] = Field(default_factory=list)
    qualitative_risks: list[QualitativeRisk] = Field(default_factory=list)
    growth_adjustment: GrowthAdjustment
    qualitative_score: int = Field(..., ge=0, le=100)


def _load_reference(name: str) -> str:
    """Read a markdown reference file."""
    path = REFERENCES_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _build_system_prompt() -> str:
    """Assemble the system prompt from the reference docs."""
    buffett = _load_reference("buffett_5d.md")
    moat = _load_reference("moat_taxonomy.md")
    glossary = _load_reference("qualitative_glossary.md")

    return f"""You are Charlie, the qualitative analysis agent in a three-agent investment pipeline.

Your role is to read a structured fact pack about a company and produce a qualitative
assessment using the Buffett 5-Dimension framework and MOAT taxonomy. You output STRICT
JSON matching the requested schema. You do NOT make BUY/SELL/HOLD recommendations — that
is Ray's job.

You must be:
- Grounded: anchor every qualitative claim to a fact in the fact pack
- Calibrated: use the 5-point scale (very_weak / weak / neutral / strong / very_strong)
  conservatively. Most ratings should land near "neutral" unless evidence is strong.
- Concise: reasoning fields should be 1-2 sentences each
- Non-prescriptive: never say "buy", "sell", "hold", "investment opportunity", etc.

────────── BUFFETT 5-DIMENSION FRAMEWORK ──────────
{buffett}

────────── MOAT TAXONOMY ──────────
{moat}

────────── RATING SCALES ──────────
{glossary}
"""


def _build_user_message(factpack: FactPack) -> str:
    """Assemble the user message: fact pack + output instructions."""
    factpack_json = factpack.model_dump_json(indent=2)

    return f"""Below is the fact pack for {factpack.ticker}. Use it to fill out the requested
qualitative assessment.

────────── FACT PACK ──────────
{factpack_json}

────────── INSTRUCTIONS ──────────
Produce a JSON object with the following top-level keys:

- product_analysis
- sector_outlook_qualitative   (only these qualitative fields: sector_maturity, barriers_to_entry,
                                disruption_risk, outlook, outlook_reasoning. The deterministic
                                fields will be merged in afterward.)
- customer_analysis
- supplier_analysis
- macro_environment
- moat   (its quantitative `proxies` field will be merged from the fact pack — leave it as null
          or set proxies to all-null in your output, the pipeline will overwrite it)
- catalysts                    (list of 0-5 forward-looking catalysts)
- qualitative_risks            (list of 0-5 qualitative risks not already captured by geopolitical_risks)
- growth_adjustment            (your hint to Ray)
- qualitative_score            (integer 0-100; weight roughly: moat 40, sector 20, macro 15, customer 15, supplier 10)

Output ONLY the JSON object. No prose before or after. No markdown fences."""


def synthesize(
    factpack: FactPack,
    api_key: Optional[str] = None,
    model: str = SYNTHESIS_MODEL,
) -> Optional[SynthesisOutput]:
    """
    Call the Anthropic API and parse the response into a SynthesisOutput.
    Returns None if the API key is missing or the call fails.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None

    client = Anthropic(api_key=key)

    system = _build_system_prompt()
    user = _build_user_message(factpack)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:
        print(f"[synthesizer] API call failed: {e}")
        return None

    # Extract text content
    text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            text += block.text

    text = text.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[synthesizer] Failed to parse JSON response: {e}")
        print(f"[synthesizer] Raw response (first 500 chars): {text[:500]}")
        return None

    # Build SynthesisOutput. Sector outlook qualitative fields only — deterministic
    # fields will be filled by pipeline.py.
    try:
        # Patch sector_outlook_qualitative to include null deterministic fields so it validates
        sector_qual = data.get("sector_outlook_qualitative", {})
        sector_qual.setdefault("sector", factpack.sector)
        sector_qual.setdefault("industry", factpack.industry)
        sector_qual.setdefault("sector_etf", factpack.sector_etf)
        sector_qual.setdefault("sector_etf_return_3m_pct", factpack.sector_etf_return_3m_pct)
        sector_qual.setdefault("sector_etf_return_ytd_pct", factpack.sector_etf_return_ytd_pct)
        sector_qual.setdefault(
            "relative_strength_vs_spy_3m", factpack.relative_strength_vs_spy_3m
        )
        sector_qual.setdefault(
            "geopolitical_risks", [g.model_dump() for g in factpack.geopolitical_risks]
        )
        data["sector_outlook_qualitative"] = sector_qual

        return SynthesisOutput.model_validate(data)
    except Exception as e:
        print(f"[synthesizer] Pydantic validation failed: {e}")
        return None
