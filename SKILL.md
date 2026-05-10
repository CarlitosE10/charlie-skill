---
name: qualitative_analysis
description: >
  Qualitative stock analysis skill. Use whenever a qualitative business assessment is needed:
  MOAT, competitive position, sector outlook, products, customers, suppliers, macro environment,
  geopolitical exposure, technical context (RSI, price momentum), or recent news.
  Trigger on: "MOAT de", "ventaja competitiva", "análisis cualitativo", "qué tan defensible",
  "perspectiva del sector", "competencia de", "análisis estratégico", "noticias recientes de",
  or any request to assess a company beyond its financial numbers.
  Does NOT make BUY/SELL/HOLD recommendations. Does NOT compute financial ratios.
version: 1.0.0
commands:
  - /qual_analyze      - Full qualitative report (LLM synthesis + deterministic facts)
  - /qual_facts        - Deterministic fact pack only (no LLM, always free)
  - /qual_moat         - MOAT quantitative proxies
  - /qual_sector       - Sector outlook + geopolitical risks
  - /qual_peers        - Peer comparison
  - /qual_macro        - Macro environment snapshot
  - /qual_news         - Recent news headlines
metadata: {"requires":{"bins":["uv","python3"],"env":["ANTHROPIC_API_KEY"]}}
---

# Qualitative Stock Analysis Skill

Produces a structured qualitative report on a stock ticker. Covers:

1. **Product analysis** — what the company sells, pricing power, substitutability
2. **Sector outlook** — ETF momentum vs SPY, sector maturity, barriers, disruption risk, geopolitical exposure
3. **Customer analysis** — B2B/B2C, concentration, switching costs, loyalty
4. **Supplier analysis** — concentration, negotiating power, critical inputs, supply-chain risk
5. **Macro environment** — rate sensitivity, FX exposure, regulation, cyclicality
6. **MOAT assessment** — strength, type (intangibles / switching costs / network effects / cost advantage / efficient scale), durability, anchored on quantitative proxies
7. **Peer comparison** — ranking against curated peer group
8. **Catalysts & risks** — forward-looking qualitative factors
9. **Growth adjustment signal** — accelerate / maintain / decelerate
10. **Qualitative score (0–100)** — composite across all dimensions
11. **Technical context** — RSI(14), 1m/3m price returns, recent news

## What this skill NEVER does

- Does NOT make BUY/SELL/HOLD recommendations
- Does NOT compute financial ratios (PKT, KTNO, ROE, P/E — use Snowball for those)
- Does NOT run DCF or valuation models
- Does NOT invent facts — every qualitative judgment is grounded in the FactPack

## When to trigger

- "MOAT", "competitive advantage", "defensibility" questions
- Sector outlook, product strategy, competition questions
- "qualitative analysis of [TICKER]", "análisis cualitativo de [TICKER]"
- Geopolitical exposure, macro sensitivity questions
- "noticias de [TICKER]", "RSI de [TICKER]", "rendimiento reciente de"

## Command routing

| User intent | Command |
|---|---|
| Full qualitative analysis | `analyze TICKER` |
| Facts without LLM call | `facts TICKER` |
| MOAT anchors only | `moat TICKER` |
| Sector + geopolitical | `sector TICKER` |
| Peer ranking | `peers TICKER` |
| VIX + dollar + cyclicality | `macro TICKER` |
| Recent headlines | `news TICKER` |

## Execution

```bash
cd scripts/

# Full analysis
uv run qualify.py analyze AAPL
uv run qualify.py analyze AAPL --format text

# Individual blocks
uv run qualify.py facts NVDA --format text
uv run qualify.py moat GOOGL --format text
uv run qualify.py sector XOM --format text
uv run qualify.py peers MSFT --format text
uv run qualify.py macro TSLA --format text
uv run qualify.py news AMZN --format text
```

## Agent import API

```python
from qualify import run_analysis
from analysis import (
    get_moat_proxies, get_sector_outlook,
    get_peer_comparison, get_macro, build_fact_pack,
)
from data import get_rsi, get_recent_news, get_price_returns

# Full report (requires ANTHROPIC_API_KEY for LLM synthesis)
report = run_analysis("AAPL")
print(report.moat.moat_strength)
print(report.qualitative_score)

# Individual getters (no API key needed — deterministic only)
moat   = get_moat_proxies("NVDA")       # MoatQuantitativeProxies
sector = get_sector_outlook("XOM")      # SectorOutlookFacts
peers  = get_peer_comparison("MSFT")    # Optional[PeerComparison]
macro  = get_macro("TSLA")              # MacroFacts
rsi, signal = get_rsi("AAPL")           # (float | None, str | None)
news   = get_recent_news("AMZN")        # list[str]
ret1m, ret3m = get_price_returns("AAPL")
```

## Without an API key

If `ANTHROPIC_API_KEY` is not set, the skill still returns a partial report with:
- Sector ETF momentum + geopolitical risks
- MOAT quantitative proxies
- Peer comparison
- Macro snapshot (VIX, DXY, cyclicality)
- RSI, price returns, recent news
- Warning in `data_quality.warnings`
- `data_quality.completeness_pct` ≈ 40

## Rules

1. Always run `analyze` for comprehensive requests. Use subcommands only for targeted queries.
2. Never invent facts. Every LLM judgment must be anchored in the FactPack.
3. Never say BUY, SELL, or HOLD.
4. Cache: 1 hour in `/tmp/qual_analysis_cache/`. Use `--no-cache` to bypass.
5. Default ratings are "neutral" — use strong/weak only when evidence is clear.
6. v1: stocks only. Crypto, ETFs, and most bank tickers will return partial results.
7. Text output: institutional format, no emojis. Always end with disclaimer.
8. JSON output (default): output ONLY the JSON object.

## Disclaimer

Qualitative analysis for informational purposes only. Not financial advice. Facts sourced from Yahoo Finance. Qualitative synthesis is produced by an LLM grounded in those facts. Investment decisions should be made in consultation with a licensed financial advisor.
