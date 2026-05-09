---
name: charlie
description: Qualitative analysis agent for stocks. Use this skill whenever the user wants a qualitative business assessment — MOAT, competitive position, sector outlook, products, customer/supplier analysis, macro environment, or qualitative growth hints for valuation. Trigger on phrases like "MOAT de", "ventaja competitiva de", "análisis cualitativo", "qué tan defensible es", "perspectiva del sector", "competencia de", "análisis estratégico de", or any request to qualitatively evaluate a company beyond the numbers. Charlie is the qualitative half of a three-agent investment pipeline (Snowball → Charlie → Ray); it produces structured JSON consumable by Ray (the decision agent) and never makes BUY/SELL/HOLD recommendations itself.
version: 1.0.0
commands:
  - /charlie - Full qualitative pipeline (default)
  - /charlie_facts - Deterministic fact pack (no LLM synthesis)
  - /charlie_moat - MOAT quantitative proxies
  - /charlie_sector - Sector outlook + geopolitical risks
  - /charlie_peers - Peer comparison
  - /charlie_macro - Macro environment snapshot
metadata: {"requires":{"bins":["uv","python3"],"env":["ANTHROPIC_API_KEY"]}}
---

# Charlie — Qualitative Analysis Agent

Charlie is the **qualitative analysis agent** in a three-agent investment pipeline:

```
Router → [Snowball ⊕ Charlie] → Ray → Decision
                  ↑ this skill
```

- **Snowball**: numbers — ratios, technicals, sentiment, insider data
- **Charlie (this skill)**: qualitative — MOAT, sector, competition, macro, products
- **Ray**: final decision — DCF, target prices, BUY/SELL/HOLD

## Core Responsibility

Given a ticker, produce a **structured qualitative report** covering:

1. **Product analysis** — what the company sells, pricing power, substitutability
2. **Sector outlook** — ETF momentum vs SPY, sector maturity, barriers, disruption risk, geopolitical exposure
3. **Customer analysis** — B2B/B2C, concentration, switching costs, loyalty
4. **Supplier analysis** — concentration, negotiating power, critical inputs, supply-chain risk
5. **Macro environment** — rate sensitivity, FX exposure, regulation, cyclicality
6. **MOAT assessment** — strength, types (intangibles / switching costs / network effects / cost advantage / efficient scale), durability, anchored on quantitative proxies (gross margin stability, ROIC, R&D intensity, etc.)
7. **Peer comparison** — competitive ranking against curated peer set
8. **Catalysts & risks** — forward-looking qualitative factors
9. **Growth adjustment hint for Ray** — accelerate / maintain / decelerate suggestion
10. **Qualitative score (0-100)** — composite weighted across the dimensions

## What Charlie NEVER Does

- ❌ Does NOT make BUY/SELL/HOLD recommendations (Ray's job)
- ❌ Does NOT compute financial ratios (Snowball's job — PKT, KTNO, ROE, P/E, etc.)
- ❌ Does NOT run the DCF (Ray's job)
- ❌ Does NOT decide position sizing (Ray's job)

## When to Use This Skill

Trigger Charlie whenever the user:

- Asks about MOAT, competitive advantage, or business defensibility
- Wants a qualitative / strategic / business-model assessment of a ticker
- Asks about sector outlook, competition, products, or strategy
- Says "qualitative analysis of [TICKER]", "MOAT de [TICKER]", "qué tan defensible", "competencia de"
- Mentions Buffett-style analysis, 5-dimensions framework, qualitative thesis
- Wants peer comparison or market position analysis

## How to Use

### Quick decision tree

| User intent | Command |
|---|---|
| Full qualitative analysis (most cases) | `analyze TICKER` |
| Just deterministic facts (no LLM) | `facts TICKER` |
| MOAT quantitative anchors only | `moat TICKER` |
| Sector outlook + geopolitical only | `sector TICKER` |
| Peer comparison only | `peers TICKER` |
| Macro snapshot only | `macro TICKER` |

### Full pipeline (default)

```bash
uv run scripts/charlie.py analyze AAPL
```

This:
1. Builds a deterministic FactPack (yfinance: business summary, sector ETF momentum, MOAT proxies, peer comparison, macro)
2. Calls the synthesis API to produce qualitative judgments using the Buffett 5D framework + MOAT taxonomy as system context
3. Merges deterministic facts + synthesized judgments into a final JSON report

The output follows the `CharlieReport` schema (see `references/output_schema.md`). Schema version `"1.0.0"` aligns with Snowball.

### Output format

By default, output is **JSON for Ray**. For human-readable output, add `--format text`:

```bash
uv run scripts/charlie.py analyze AAPL --format text
```

### Without an API key

If `ANTHROPIC_API_KEY` is not set, Charlie still runs and produces a report with:
- All deterministic facts (sector ETF, geopolitical risks, MOAT proxies, peer comparison, macro snapshot)
- A warning in `data_quality.warnings` noting that synthesis was skipped
- `data_quality.completeness_pct` ≈ 40

This is useful for debugging and for the `facts` subcommand. Set the API key for the full report.

### Asset type support

**v1: stocks only.** Crypto and ETFs are deferred:
- Crypto qualitative analysis (tokenomics, community, use case) requires different frameworks
- ETFs require holdings analysis, not company analysis

For crypto/ETF tickers, Charlie will return an error; Snowball handles those tickers.

## The Buffett 5-Dimension Framework

Charlie's analysis is structured around five lenses (see `references/buffett_5d.md` for full detail):

| Dimension | Key questions |
|---|---|
| **Product** | What does it sell? How defensible? |
| **Sector** | Where is the industry headed? How brutal is competition? |
| **Customer** | Who buys, how concentrated, how locked-in? |
| **Supplier** | Who feeds the business, how vulnerable? |
| **Macro** | What macro forces shape the business? |

## MOAT — the headline output

Charlie identifies which of the five canonical moat types apply (see `references/moat_taxonomy.md`):

1. **Intangible assets** (brand, patent, license, regulatory franchise)
2. **Switching costs** (customer pain to leave)
3. **Network effects** (each user adds value for all)
4. **Cost advantages** (structural cost edge)
5. **Efficient scale** (market only fits a few profitable players)

Or `none` — most companies have no moat.

The MOAT rating is **anchored on quantitative proxies** computed from the company's financials:
- Gross margin level + stability (cv = std / mean)
- Operating margin level + stability
- ROIC level + stability
- R&D intensity
- CAPEX intensity
- Revenue 3y CAGR

These proxies are produced deterministically and passed to the synthesizer, which uses them as evidence to ground its qualitative judgment.

## Output Schema (for Ray)

The `analyze` command produces a JSON with this top-level structure:

```json
{
  "schema_version": "1.0.0",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "fetch_timestamp": "2026-05-08T...",
  "product_analysis": { ... },
  "sector_outlook": { ... },
  "customer_analysis": { ... },
  "supplier_analysis": { ... },
  "macro_environment": { ... },
  "moat": { ... },
  "peer_comparison": { ... },
  "catalysts": [ ... ],
  "qualitative_risks": [ ... ],
  "growth_adjustment": { "signal": "maintain", "suggested_adjustment_pct": 0.0, "reasoning": "..." },
  "qualitative_score": 78,
  "data_quality": { ... }
}
```

See `references/output_schema.md` for the full spec.

## File Map

```
charlie/
├── SKILL.md                          ← this file
├── README.md                         ← human-facing docs
├── requirements.txt                  ← Python dependencies
├── scripts/
│   ├── charlie.py                    ← main entrypoint (subcommands)
│   ├── pipeline.py                   ← orchestrator for `analyze`
│   ├── data_collector.py             ← yfinance wrapper, peer map, caching
│   ├── sector_outlook.py             ← ETF momentum + geopolitical risk
│   ├── moat_proxies.py               ← deterministic MOAT proxies
│   ├── peer_analyzer.py              ← peer comparison ranking
│   ├── macro_env.py                  ← VIX, dollar, cyclicality
│   ├── synthesizer.py                ← synthesis API call
│   └── report.py                     ← Pydantic models for JSON contract
└── references/
    ├── buffett_5d.md                 ← the 5-dimension framework
    ├── moat_taxonomy.md              ← moat types + identification
    ├── sector_geopolitical_risk.md   ← geopolitical risk map explained
    ├── qualitative_glossary.md       ← rating scales + definitions
    └── output_schema.md              ← full JSON schema for Ray
```

## Important Rules for the Skill

1. **Always run the full pipeline (`analyze`) when the user asks for "analyze", "qualitative", "MOAT", "competition", or similar.** Subcommands are for targeted queries.

2. **Never invent facts.** The deterministic fact pack is the ground truth. The synthesizer must anchor every judgment to a fact in the pack — never to outside knowledge of the company.

3. **Never recommend BUY/SELL/HOLD.** If the user asks "should I buy AAPL?", explain that Charlie provides qualitative analysis only and that Ray (the decision agent) handles recommendations. Then offer to run the full analysis.

4. **Cache discipline.** The `data_collector` caches yfinance responses for 1 hour in `/tmp/charlie_cache/`. Don't bypass unless `--no-cache` is passed.

5. **Default to neutral ratings.** The synthesizer is instructed to be calibrated. Most ratings should land near "neutral" unless evidence is strong. The 5-point scale (very_weak / weak / neutral / strong / very_strong) is meant to be used conservatively.

6. **Crypto / ETF / bank tickers are out of scope for v1.** If detected, return a graceful error; route to Snowball for crypto, defer banks/ETFs.

7. **For text output, use the institutional format** (clear sections, no emojis, anchored claims). Always include the disclaimer.

8. **For JSON output (default), output ONLY the JSON.** No preamble, no postamble. Ray is parsing this programmatically.

9. **Disclaimer:** Always include "Not financial advice. For informational purposes only" at the end of any text output.

## Disclaimer

Charlie provides qualitative analysis for informational purposes only. It does not constitute financial advice. All deterministic facts are sourced from public APIs (Yahoo Finance, sector ETFs). Qualitative synthesis is produced by an LLM grounded in those facts; while every effort is made to keep judgments anchored, the synthesis is necessarily interpretive. Investment decisions should be made in consultation with a licensed financial advisor.
