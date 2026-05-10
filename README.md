# Qualitative Stock Analysis Skill

> Structured qualitative assessment of stocks. Any agent can use this skill to get MOAT analysis, sector outlook, peer comparison, macro context, geopolitical exposure, and technical signals (RSI, price returns, recent news). Does not make BUY/SELL/HOLD recommendations.

---

## Quick start

```bash
export ANTHROPIC_API_KEY=sk-ant-...

cd scripts/

# Full qualitative report (JSON)
uv run qualify.py analyze AAPL

# Human-readable
uv run qualify.py analyze AAPL --format text

# Deterministic facts only (no LLM, no API key needed)
uv run qualify.py facts NVDA --format text

# Individual blocks
uv run qualify.py moat GOOGL --format text
uv run qualify.py sector XOM --format text
uv run qualify.py peers MSFT --format text
uv run qualify.py macro TSLA --format text
uv run qualify.py news AMZN --format text
```

---

## What it computes

### Buffett 5-Dimension qualitative analysis (requires API key)

| Dimension | Output |
|---|---|
| **Product** | description, core products, revenue concentration, pricing power, substitutability |
| **Sector** | maturity, barriers, disruption risk, ETF momentum, geopolitical risks, outlook |
| **Customer** | type (B2B/B2C), concentration, switching costs, loyalty |
| **Supplier** | concentration, negotiating power, critical inputs, supply-chain risk |
| **Macro** | rate sensitivity, FX, regulatory environment, cyclicality, inflation |

### MOAT assessment (requires API key)

Identifies moat type(s) and rates strength + durability. Five canonical types:
- Intangible assets (brand, patent, license)
- Switching costs (customer pain to leave)
- Network effects (each user adds value)
- Cost advantages (structural cost edge)
- Efficient scale (market fits few players)

Anchored on **quantitative proxies** (always computed, no API key needed):
- Gross margin: average + stability (coefficient of variation)
- Operating margin: average + stability
- ROIC: average + stability
- R&D intensity (R&D / Revenue)
- CAPEX intensity (CAPEX / Revenue)
- Revenue 3y CAGR

### Peer comparison (always computed)

Curated peer map for ~40 tickers. Outputs: market cap rank, share of group, margin rank, growth rank, relative position (leader / challenger / follower / laggard).

### Geopolitical risk exposure (always computed)

Structural exposures by sector and ticker: Taiwan Strait, US–China trade, Middle East, pharma regulation, Big Tech antitrust, energy transition, banking stress. Each risk includes a severity rating.

### Technical context (always computed)

Derived from 1y daily price history — no external APIs:
- **RSI(14)** — Wilder's RSI; signal: overbought (>70) / neutral / oversold (<30)
- **Price returns** — 1-month (~21 sessions) and 3-month (~63 sessions) in %
- **Recent news** — up to 5 headlines from yfinance's news feed

### Macro context (always computed)

- VIX level (fear/volatility proxy)
- Dollar index 3m change (DXY)
- Sector cyclicality (defensive / neutral / cyclical / highly cyclical)

---

## Commands

| Command | Purpose | API key? |
|---|---|---|
| `analyze TICKER` | Full qualitative report | Yes |
| `facts TICKER` | Deterministic fact pack | No |
| `moat TICKER` | MOAT quantitative proxies | No |
| `sector TICKER` | Sector ETF + geopolitical | No |
| `peers TICKER` | Peer comparison | No |
| `macro TICKER` | VIX + DXY + cyclicality | No |
| `news TICKER` | Recent headlines | No |

Flags: `--format json|text` (default `json`), `--no-cache`

---

## Agent import API

```python
from qualify import run_analysis
from analysis import (
    get_moat_proxies,    # MoatQuantitativeProxies
    get_sector_outlook,  # SectorOutlookFacts
    get_peer_comparison, # Optional[PeerComparison]
    get_macro,           # MacroFacts
    build_fact_pack,     # FactPack (all deterministic facts)
)
from data import (
    get_rsi,             # (float | None, str | None)
    get_recent_news,     # list[str]
    get_price_returns,   # (1m_pct, 3m_pct)
)

# Full report with LLM synthesis
report = run_analysis("AAPL")
print(report.moat.moat_strength)       # "very_strong"
print(report.qualitative_score)         # 82
print(report.sector_outlook.outlook)    # "constructive"

# Single values — no API key needed
moat   = get_moat_proxies("NVDA")
sector = get_sector_outlook("XOM")
peers  = get_peer_comparison("MSFT")
macro  = get_macro("TSLA")
rsi, signal = get_rsi("AAPL")           # (62.4, "neutral")
news   = get_recent_news("AMZN")        # ["Apple reports...", ...]
ret1m, ret3m = get_price_returns("AAPL")
```

Each getter internally calls `fetch_bundle` (1h cache), so multiple calls on the same ticker within one hour are free.

---

## File layout

```
├── SKILL.md                     ← skill definition (trigger conditions, rules)
├── README.md                    ← this file
├── requirements.txt             ← Python dependencies
├── scripts/
│   ├── data.py                  ← yfinance fetching, caching, RSI/returns/news
│   │                               getters: get_rsi, get_recent_news, get_price_returns
│   ├── analysis.py              ← MOAT proxies, sector outlook, peers, macro, FactPack
│   │                               getters: get_moat_proxies, get_sector_outlook,
│   │                                        get_peer_comparison, get_macro, build_fact_pack
│   └── qualify.py               ← QualReport models, LLM synthesis, run_analysis(), CLI
│                                   (PEP 723 inline deps — uv run qualify.py ...)
└── references/
    ├── buffett_5d.md            ← 5-dimension qualitative framework (used in synthesis)
    ├── moat_taxonomy.md         ← moat types + identification guide (used in synthesis)
    ├── sector_geopolitical_risk.md ← geopolitical risk map explained
    ├── qualitative_glossary.md  ← rating scales + definitions (used in synthesis)
    └── output_schema.md         ← full JSON contract for QualReport
```

---

## Two-layer architecture

```
fetch_bundle(ticker)          ← data.py: yfinance, 1h cache, RSI, news
        ↓
build_fact_pack(ticker)       ← analysis.py: MOAT proxies, sector, peers, macro
        ↓ FactPack (JSON)
_synthesize(factpack)         ← qualify.py: Anthropic API + Buffett 5D + MOAT taxonomy
        ↓
run_analysis(ticker)          ← qualify.py: merges deterministic + synthesized → QualReport
```

The deterministic layer always runs. If `ANTHROPIC_API_KEY` is missing or the API call fails, the skill returns a partial report (`completeness_pct ≈ 40`) with only the deterministic blocks filled.

---

## Caching

All yfinance responses cached in `/tmp/qual_analysis_cache/` for **1 hour**. Override with `--no-cache` or `use_cache=False`.

---

## Data sources

| Data | Source |
|---|---|
| Financials, price history, company info | Yahoo Finance (`yfinance`) |
| RSI(14), price returns | Computed from yfinance daily history |
| Recent news | `yf.Ticker.news` |
| Sector ETF momentum | Yahoo Finance (XLK, XLF, XLV, etc.) |
| VIX | Yahoo Finance (`^VIX`) |
| Dollar index | Yahoo Finance (`DX-Y.NYB`, fallback `UUP`) |
| Geopolitical risk map | Curated in `analysis.py` |
| Qualitative synthesis | Anthropic API (`claude-sonnet-4-6`) |

No API keys required except `ANTHROPIC_API_KEY` for synthesis.

**Known limitations:**
- ~4 years of annual financials from yfinance — MOAT stability proxies are based on that window
- Peer map is curated; tickers outside the map skip the peer block
- Geopolitical risk map is static and should be reviewed periodically
- v1: stocks only — crypto, ETFs, and most bank tickers return partial results

---

## What this skill will NOT do

1. BUY / SELL / HOLD recommendations
2. Invent facts outside the FactPack
3. Run DCF or compute valuations
4. Compute quantitative financial ratios (use Snowball for PKT, KTNO, ROE, P/E, etc.)

---

## Disclaimer

Qualitative analysis for informational purposes only. Not financial advice. Facts sourced from Yahoo Finance (public data). Qualitative synthesis is produced by an LLM grounded in those facts. Investment decisions should be made in consultation with a licensed financial advisor.
