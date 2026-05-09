# Qualitative Glossary

Calibration anchors and definitions for every rating scale Charlie uses.

---

## 5-point qualitative scale

Used for almost every rating field (pricing power, switching costs, moat strength, etc.).

| Rating | Meaning | When to use |
|---|---|---|
| `very_weak` | Severe negative on this dimension | Reserve for unambiguous structural disadvantages |
| `weak` | Below-average; clear negatives | Visible competitive pressure or vulnerability |
| `neutral` | Average / unclear / mixed | Default when evidence is balanced or thin |
| `strong` | Above-average; clear positives | Documented competitive advantage |
| `very_strong` | Best-in-class | Reserve for textbook examples (Coca-Cola brand, Visa network) |

**Default to neutral.** Most companies are average on most dimensions. Reserve the extremes for cases where the evidence is overwhelming.

---

## Outlook rating (sectors)

| Rating | Meaning |
|---|---|
| `bearish` | Sector facing structural decline or major disruption |
| `cautious` | Visible headwinds; reasonable to expect underperformance |
| `neutral` | Mixed signals; performing roughly in-line |
| `constructive` | Tailwinds in place; sector should perform well |
| `bullish` | Multiple structural tailwinds; sector well-positioned |

Anchor on the deterministic sector ETF return + geopolitical risks. If the sector ETF is up ≥10pp vs SPY in 3m AND has no flagged geopolitical risks, "constructive" or "bullish" is defensible.

---

## Concentration level

| Level | Quantitative anchor (when known) |
|---|---|
| `very_low` | Top 10 customers/suppliers <10% of revenue/COGS |
| `low` | Top 10 customers/suppliers 10–25% |
| `moderate` | Top 10 customers/suppliers 25–50% |
| `high` | Top 10 customers/suppliers 50–75% |
| `very_high` | Top 10 customers/suppliers >75%, or single counterparty >25% |

When concentration data isn't disclosed, infer from business model: pure consumer brands tend `very_low`/`low`; defense contractors, specialized B2B, certain semiconductor suppliers tend `high`/`very_high`.

---

## MOAT types

See `moat_taxonomy.md` for full detail. Quick reference:

- `intangible_assets` — brand, patent, license, regulatory franchise
- `switching_costs` — customers pay real cost to leave
- `network_effects` — each user adds value for all users
- `cost_advantages` — structural cost edge (scale, location, process)
- `efficient_scale` — market only fits a few profitable players
- `none` — no identifiable structural advantage

Multiple moat types can apply to one company; list all that fit.

---

## Cyclicality

| Label | Sectors |
|---|---|
| `defensive` | Consumer Defensive, Healthcare, Utilities |
| `neutral` | Technology, Communication Services |
| `cyclical` | Consumer Cyclical, Industrials, Basic Materials, Financial Services, Real Estate |
| `highly_cyclical` | Energy |

This is auto-classified from the sector. The synthesizer should accept the auto-classification unless the specific business profile diverges (e.g., a defensive subsegment within a cyclical sector).

---

## Growth signal (hint to Ray)

Charlie's hint to Ray on whether to adjust Snowball's revenue/FCF growth assumptions:

| Signal | Meaning |
|---|---|
| `decelerate` | Qualitative factors suggest growth is harder to sustain than the historical CAGR implies. Reduce Ray's base case growth. |
| `maintain` | Qualitative factors are consistent with extrapolating recent growth. |
| `accelerate` | Qualitative tailwinds (new product, secular driver, market expansion) suggest growth could be higher than the historical CAGR. |

Optional `suggested_adjustment_pct`: a numeric pp delta. Example: -1.5 means "subtract 1.5 percentage points from Snowball's base-case growth assumption."

Use this conservatively. Default to `maintain` unless there is a clear qualitative reason to deviate.

---

## Categories for qualitative risks

| Category | Examples |
|---|---|
| `regulatory` | Antitrust, drug pricing reform, energy transition policy |
| `competitive` | New entrant, disruptive substitute, pricing pressure |
| `execution` | Management transition, M&A integration, product launch risk |
| `macro` | Recession exposure, FX mismatch, rate sensitivity |
| `geopolitical` | Trade war, sanctions, regional conflict (overlaps with sector_outlook.geopolitical_risks) |
| `esg` | Environmental liability, social license, governance issues |
| `other` | Use sparingly; prefer one of the above |

---

## Calibration philosophy

1. **Anchor every claim to a fact.** Reasoning fields should reference something concrete from the fact pack.
2. **Be sparing.** A short, well-grounded report beats a long speculative one.
3. **Don't make recommendations.** Charlie supplies texture; Ray decides.
4. **Think across the cycle.** The qualitative score should reflect how the business will perform across multiple scenarios, not how it's performing right now.
