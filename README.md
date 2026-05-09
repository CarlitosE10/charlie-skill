# Charlie

> **Qualitative analysis agent** — the strategic / business-model half of a three-agent investment pipeline.

Charlie takes a ticker (stock) and produces a structured qualitative report covering MOAT, sector outlook, products, customers, suppliers, macro environment, peer comparison, catalysts, and risks. It does **not** make BUY/SELL/HOLD recommendations — that's Ray's job downstream.

---

## Three-agent architecture

```
        ┌───────────────────────────────────────────┐
        │ INPUTS: ticker (+ optional portfolio,     │
        │ horizon, risk profile)                    │
        └────────────────────┬──────────────────────┘
                             │
                       ┌─────▼─────┐
                       │  Router   │  ← classifies asset type
                       └─────┬─────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌───────────────┐         ┌───────────────┐
        │   Snowball    │         │ ★ Charlie ★   │
        │ (quantitative)│         │ (this skill)  │
        │ • ratios      │         │ • MOAT        │
        │ • technical   │         │ • sector      │
        │ • sentiment   │         │ • competition │
        │ • insider     │         │ • macro env   │
        │ • DCF inputs  │         │ • peers       │
        └───────┬───────┘         └───────┬───────┘
                └────────────┬────────────┘
                             ▼
                       ┌───────────┐
                       │    Ray    │  ← final decision
                       │ • DCF 3sc │
                       │ • target  │
                       │ • sizing  │
                       │ • BUY/SELL│
                       └───────────┘
```

---

## Quick start

```bash
# Set the API key (required for full synthesis)
export ANTHROPIC_API_KEY=sk-ant-...

# Full qualitative analysis (JSON for Ray)
cd scripts/
uv run charlie.py analyze AAPL

# Human-readable
uv run charlie.py analyze AAPL --format text

# Just the deterministic facts (no LLM call)
uv run charlie.py facts NVDA --format text

# Just MOAT proxies
uv run charlie.py moat GOOGL --format text

# Just sector outlook + geopolitical risks
uv run charlie.py sector XOM --format text

# Just peer comparison
uv run charlie.py peers MSFT --format text
```

---

## What Charlie computes

### 1. Buffett 5-Dimension framework

Charlie applies five qualitative lenses (see `references/buffett_5d.md`):

| Dimension | Output fields |
|---|---|
| **Product** | description, core products, revenue concentration, pricing power, substitutability |
| **Sector** | maturity, barriers to entry, disruption risk, ETF momentum, geopolitical risks, outlook |
| **Customer** | type (B2B/B2C), concentration, switching costs, loyalty |
| **Supplier** | concentration, negotiating power, critical inputs, supply-chain risk |
| **Macro** | rate sensitivity, FX exposure, regulatory environment, cyclicality, inflation sensitivity |

### 2. MOAT assessment

The headline qualitative output. Charlie identifies the moat type(s) and rates strength + durability.

**Five canonical types** (see `references/moat_taxonomy.md`):
- Intangible assets (brand, patent, license)
- Switching costs (customer pain to leave)
- Network effects (each user adds value)
- Cost advantages (structural cost edge)
- Efficient scale (market fits few players)

**Quantitative anchors** (computed deterministically from yfinance financials):
- Gross margin: average + stability (coefficient of variation)
- Operating margin: average + stability
- ROIC: average + stability
- R&D intensity (R&D / revenue)
- CAPEX intensity (CAPEX / revenue)
- Revenue 3y CAGR

These anchors are passed to the synthesizer as evidence; the qualitative MOAT verdict is grounded in them.

### 3. Peer comparison

Curated peer set (see `PEER_MAP` in `data_collector.py`). For each ticker, Charlie produces:
- Side-by-side: market cap, gross margin, operating margin, P/E, revenue YoY
- Subject's market cap rank, share %, margin rank, growth rank
- Relative position label: leader / challenger / follower / laggard

### 4. Geopolitical risk map

An always-on (not news-triggered) catalogue of structural geopolitical exposures by sector and ticker (see `references/sector_geopolitical_risk.md`):
- Taiwan Strait / TSMC supply chain
- US–China trade
- Russia–Ukraine
- Middle East
- Pharma drug-pricing reform
- Big Tech antitrust
- Energy transition
- Regional banking stress

Each flagged risk includes a severity rating (5-point scale).

### 5. Catalysts and qualitative risks

Up to 5 forward-looking catalysts and 5 qualitative risks, each with severity / likelihood / impact ratings.

### 6. Growth adjustment hint for Ray

Charlie's signal to Ray on whether to accelerate, maintain, or decelerate Snowball's revenue/FCF growth assumptions, with optional pp delta and reasoning.

### 7. Qualitative score (0–100)

Composite weighted across dimensions:
- Moat: 40
- Sector outlook: 20
- Macro: 15
- Customer: 15
- Supplier: 10

---

## Commands

| Command | Purpose |
|---|---|
| `analyze TICKER` | Full pipeline — JSON for Ray (default) |
| `facts TICKER` | Deterministic fact pack only (no LLM call) |
| `moat TICKER` | MOAT quantitative proxies |
| `sector TICKER` | Sector outlook + geopolitical risks |
| `peers TICKER` | Peer comparison |
| `macro TICKER` | Macro snapshot |

Common flags:
- `--format json|text` (default `json`)
- `--no-cache` to bypass the 1-hour disk cache

---

## Two-layer architecture

Charlie has a clear separation between deterministic and LLM-synthesized layers:

### Deterministic layer (always runs)

- `data_collector.py` — yfinance bundle + peer fetching + caching
- `sector_outlook.py` — sector ETF momentum + geopolitical risk lookup
- `moat_proxies.py` — gross margin, op margin, ROIC stats from financials
- `peer_analyzer.py` — peer ranking and relative position
- `macro_env.py` — VIX, dollar index, cyclicality classification

These produce a **FactPack** — a structured JSON of grounded facts.

### Synthesis layer (LLM)

- `synthesizer.py` — calls the Anthropic API with FactPack + Buffett 5D + MOAT taxonomy as system context, produces structured JSON output validated against Pydantic models

### Why this matters

If the API call fails (no key, rate limit, parse error), the deterministic layer still produces a usable report — sector outlook, MOAT proxies, peer comparison, geopolitical risks. The `data_quality.warnings` field surfaces what's missing.

---

## File layout

```
charlie/
├── SKILL.md                       ← skill definition (the "brain")
├── README.md                      ← this file
├── requirements.txt               ← Python dependencies
├── scripts/
│   ├── charlie.py                 ← CLI entrypoint
│   ├── pipeline.py                ← orchestrator
│   ├── data_collector.py          ← yfinance + peer map + cache
│   ├── sector_outlook.py          ← ETF momentum + geopolitical
│   ├── moat_proxies.py            ← deterministic MOAT proxies
│   ├── peer_analyzer.py           ← peer ranking
│   ├── macro_env.py               ← VIX + dollar + cyclicality
│   ├── synthesizer.py             ← Anthropic API call
│   └── report.py                  ← Pydantic models (JSON contract)
└── references/
    ├── buffett_5d.md              ← 5-dimension qualitative framework
    ├── moat_taxonomy.md           ← five moat types + identification
    ├── sector_geopolitical_risk.md← geopolitical risk map explained
    ├── qualitative_glossary.md    ← rating scales + definitions
    └── output_schema.md           ← full JSON contract for Ray
```

---

## Asset type handling

**v1: stocks only.** Crypto and ETFs out of scope:
- Crypto qualitative analysis (tokenomics, community, use case) is a different framework
- ETFs require holdings analysis, not company analysis
- Banks need NIM, NPL, regulatory frameworks (deferred to v2)

For these tickers, Charlie returns an error. Snowball handles crypto.

---

## Output format

Default is **JSON** because Ray consumes it programmatically. Schema is versioned (`schema_version: "1.0.0"`) — see `references/output_schema.md`.

For human review, use `--format text`.

---

## Caching

All yfinance responses cached in `/tmp/charlie_cache/` for **1 hour**. Override with `--no-cache`.

---

## Data sources

| Block | Source |
|---|---|
| Business summary, financials, peers | Yahoo Finance (via `yfinance`) |
| Sector ETF momentum | Yahoo Finance (XLK, XLF, XLV, etc.) |
| VIX | Yahoo Finance (`^VIX`) |
| Dollar index | Yahoo Finance (`DX-Y.NYB`, fallback `UUP`) |
| Geopolitical risk map | Curated, in `sector_outlook.py` |
| Synthesis | Anthropic API (`claude-sonnet-4-5-20250929`) |

All public APIs. The Anthropic API key is the only required credential.

**Known limitations:**
- yfinance provides ~4 years of annual financials — MOAT stability proxies are based on that window
- Peer map is curated; tickers outside the map skip the peer block
- Geopolitical risk map is human-maintained and should be reviewed periodically

---

## What Charlie will NOT do

These rules are enforced in `SKILL.md`:

1. ❌ Will not say BUY, SELL, or HOLD — even if asked directly. Charlie supplies qualitative texture; Ray decides.
2. ❌ Will not invent facts. Synthesis is grounded only in the FactPack.
3. ❌ Will not run the DCF or compute valuations.
4. ❌ Will not analyze quantitative ratios already covered by Snowball (PKT, KTNO, ROE, P/E).

---

## Configuration

```bash
# Required for synthesis
export ANTHROPIC_API_KEY=sk-ant-...

# Optional: change the synthesis model
# (set in synthesizer.py: SYNTHESIS_MODEL = "...")
```

If `ANTHROPIC_API_KEY` is missing, Charlie still produces a report with deterministic facts only.

---

## Disclaimer

Charlie provides qualitative analysis for informational purposes only. It does not constitute financial advice. The deterministic facts are sourced from public APIs; the qualitative synthesis is produced by an LLM grounded in those facts. Investment decisions should be made in consultation with a licensed financial advisor.

---

## Roadmap

**v1 (current):** Stocks only. Single-pass synthesis. JSON contract with Ray.

**v2 (planned):**
- Banks: NIM, LDR, regulatory environment frameworks
- ETFs: holdings analysis, theme assessment
- Crypto qualitative: tokenomics, community, use case, regulation
- Earnings call transcript sentiment integration
- News integration for time-sensitive catalyst detection

**v3 (aspirational):**
- Multi-pass synthesis (initial pass → critique → refine)
- Direct integration with 10-K filings (SEC EDGAR full-text)
- Industry-specific sub-frameworks (Porter's Five Forces deep-dive, Hamilton Helmer's 7 Powers)
