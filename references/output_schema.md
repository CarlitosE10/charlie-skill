# QualReport — JSON Schema (v1.0.0)

This document defines the JSON contract produced by `run_analysis(ticker)` and by `uv run qualify.py analyze TICKER`. The schema version is `"1.0.0"`.

---

## Top-level structure

```json
{
  "schema_version": "1.0.0",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "fetch_timestamp": "2026-05-08T15:30:00",

  "product_analysis": { ... },
  "sector_outlook": { ... },
  "customer_analysis": { ... },
  "supplier_analysis": { ... },
  "macro_environment": { ... },

  "moat": { ... },
  "peer_comparison": { ... },

  "catalysts": [ ... ],
  "qualitative_risks": [ ... ],

  "growth_adjustment": { ... },
  "qualitative_score": 78,

  "data_quality": { ... }
}
```

---

## Block-by-block

### `product_analysis`

```json
{
  "description": "Designs and sells consumer electronics, software, and services...",
  "core_products": ["iPhone", "Mac", "iPad", "Wearables", "Services"],
  "revenue_concentration": "iPhone >50% of product revenue; Services growing fast",
  "pricing_power": "strong",
  "pricing_power_reasoning": "Premium pricing sustained across hardware refresh cycles",
  "substitutability": "weak",
  "substitutability_reasoning": "Ecosystem lock-in via iCloud, Messages, App Store"
}
```

### `sector_outlook`

```json
{
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "sector_etf": "XLK",
  "sector_etf_return_3m_pct": 8.4,
  "sector_etf_return_ytd_pct": 12.1,
  "relative_strength_vs_spy_3m": 2.3,
  "sector_maturity": "mature",
  "barriers_to_entry": "strong",
  "disruption_risk": "neutral",
  "geopolitical_risks": [
    { "event": "Taiwan Strait / TSMC supply chain", "impact": "...", "severity": "strong" }
  ],
  "outlook": "constructive",
  "outlook_reasoning": "Sector leadership; AI capex tailwind despite concentration risk"
}
```

### `customer_analysis`

```json
{
  "customer_type": "B2C",
  "customer_concentration": "very_low",
  "customer_concentration_reasoning": "Hundreds of millions of consumers; no single customer matters",
  "switching_costs": "strong",
  "switching_costs_reasoning": "iCloud, iMessage, App Store create migration friction",
  "customer_loyalty": "very_strong"
}
```

### `supplier_analysis`

```json
{
  "supplier_concentration": "high",
  "supplier_concentration_reasoning": "Heavy dependence on TSMC for advanced silicon",
  "supplier_negotiating_power": "weak",
  "critical_inputs": ["leading-edge silicon wafers", "OLED displays", "lithium-ion cells"],
  "supply_chain_risk": "strong"
}
```

### `macro_environment`

```json
{
  "interest_rate_sensitivity": "neutral",
  "interest_rate_reasoning": "Strong cash position offsets rate sensitivity",
  "fx_sensitivity": "strong",
  "fx_reasoning": "~58% of revenue international",
  "regulatory_environment": "weak",
  "regulatory_reasoning": "Active antitrust scrutiny in US and EU",
  "cyclicality": "neutral",
  "inflation_sensitivity": "weak",
  "overall_macro_tailwind": "neutral"
}
```

### `moat`

```json
{
  "moat_score": 5,
  "moat_strength": "very_strong",
  "moat_types": ["intangible_assets", "switching_costs", "network_effects"],
  "moat_durability_years": 15,
  "moat_reasoning": "Brand premium + ecosystem lock-in + App Store network effects",
  "proxies": {
    "gross_margin_avg": 0.44,
    "gross_margin_stability": 0.05,
    "operating_margin_avg": 0.30,
    "operating_margin_stability": 0.07,
    "roic_avg": 0.42,
    "roic_stability": 0.10,
    "rd_intensity_avg": 0.07,
    "capex_intensity_avg": 0.03,
    "revenue_cagr_3y": 0.08
  }
}
```

`proxies` is computed deterministically by `analysis.py::calc_moat_proxies()` (no LLM). The qualitative fields (`moat_strength`, `moat_types`, `moat_durability_years`, `moat_reasoning`) are produced by the synthesizer using the proxies as anchors.

### `peer_comparison`

```json
{
  "peers": [
    {
      "ticker": "MSFT",
      "name": "Microsoft Corporation",
      "market_cap": 3000000000000,
      "gross_margin": 0.69,
      "operating_margin": 0.42,
      "pe_ratio": 35.1,
      "revenue_growth_yoy": 0.16
    }
  ],
  "market_cap_rank": 1,
  "market_cap_share_pct": 28.4,
  "margin_rank": 3,
  "growth_rank": 4,
  "relative_position": "leader"
}
```

### `catalysts`

Array of 0–5 forward-looking events that could move the qualitative thesis:

```json
[
  {
    "description": "Vision Pro 2 launch in 2H FY26",
    "horizon": "medium",
    "likelihood": "strong",
    "impact": "neutral"
  }
]
```

### `qualitative_risks`

Array of 0–5 qualitative risks not already captured by `geopolitical_risks`:

```json
[
  {
    "description": "EU DMA enforcement may compress App Store take rate",
    "severity": "neutral",
    "likelihood": "strong",
    "category": "regulatory"
  }
]
```

### `growth_adjustment`

Qualitative signal for consuming agents — whether growth assumptions should be accelerated, maintained, or decelerated:

```json
{
  "signal": "maintain",
  "suggested_adjustment_pct": 0.0,
  "reasoning": "Services momentum offsets hardware maturity; net qualitative outlook is consistent with extrapolating recent CAGR"
}
```

### `qualitative_score`

Integer 0–100, composite weighting (rough):
- Moat: 40
- Sector outlook: 20
- Macro environment: 15
- Customer dimension: 15
- Supplier dimension: 10

Higher = better qualitative business.

### `business_verdict`

Overall quality verdict of the business itself — not a stock price recommendation:

```json
"business_verdict": "strong"
```

| Value | Meaning |
|---|---|
| `"strong"` | Durable moat, favorable sector, manageable macro risks |
| `"acceptable"` | Some competitive advantages, moderate risks, requires monitoring |
| `"weak"` | Weak or no moat, difficult sector, or significant structural headwinds |

`null` if synthesis was skipped (no API key).

### `moat.moat_score`

Integer 1–5 summary of moat strength:
- 1 = no moat (commodity, easily displaced)
- 2 = weak (some advantage but not durable)
- 3 = moderate (real advantage, but under pressure)
- 4 = strong (durable advantage, hard to replicate)
- 5 = extraordinary (structurally dominant, decades of runway)

### `data_quality`

```json
{
  "completeness_pct": 95.0,
  "warnings": [],
  "data_sources_succeeded": ["info", "financials", "balance_sheet", "cashflow", "history_1y", "news", "peers", "vix", "dxy", "sector_etf"],
  "data_sources_failed": [],
  "synthesis_model": "claude-sonnet-4-6"
}
```

`synthesis_model` is `null` if the LLM synthesis was skipped (no API key) — in that case, only the deterministic fields are populated and `completeness_pct` will be ~40.

---

---

## FactPack — deterministic layer output

The `facts` subcommand returns a `FactPack` instead of a full `CharlieReport`. It contains all deterministic facts and is the input to the synthesis layer. Key fields beyond what's in `CharlieReport`:

```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "business_summary": "Apple Inc. designs, manufactures...",
  "rsi_14d": 62.4,
  "rsi_signal": "neutral",
  "price_return_1m_pct": 3.2,
  "price_return_3m_pct": -1.8,
  "recent_news": [
    "Apple reports record Q1 earnings",
    "Apple Vision Pro sales disappoint analysts"
  ],
  "vix_level": 18.2,
  "dollar_index_3m_change_pct": 1.4,
  "moat_proxies": { ... },
  "peer_comparison": { ... }
}
```

**Technical context fields:**
- `rsi_14d` — Wilder's RSI(14) computed from 1y daily price history; `null` if history unavailable
- `rsi_signal` — `"overbought"` (RSI > 70) / `"neutral"` / `"oversold"` (RSI < 30)
- `price_return_1m_pct` — 1-month (~21 sessions) price return in percent
- `price_return_3m_pct` — 3-month (~63 sessions) price return in percent
- `recent_news` — up to 5 headlines from yfinance's news feed

---

## Field nullability

Every block in the report can be `null` if the underlying data isn't available. Check `data_quality.warnings` for the cause.

- `product_analysis`, `customer_analysis`, `supplier_analysis`, `macro_environment` → present only when synthesis succeeded.
- `sector_outlook`, `peer_comparison`, `moat` (with proxies) → present whenever the deterministic data path succeeds, even if synthesis fails.
- `growth_adjustment`, `qualitative_score` → present only when synthesis succeeded.

---

## Versioning

This is **v1.0.0**. Backward-incompatible changes (renaming fields, changing types) require bumping the major version. Adding new optional fields can happen at minor version bumps.
