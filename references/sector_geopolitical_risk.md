# Sector Geopolitical Risk Map

A curated set of always-on geopolitical risk events lives in `scripts/analysis.py` (the `_GEO_RISKS` dict). This document explains the reasoning behind each event, the affected sectors and tickers, and how they are used.

The map is **always-on** — it does not depend on news feeds. The events listed are structural, multi-year exposures that should always be flagged when they apply, not "breaking news" alerts.

---

## How the map is used

When `sector` or `analyze` runs, it iterates over every event in the map. An event is flagged for a ticker if **either**:

1. The ticker is explicitly named in the event's `tickers` list (high specificity), OR
2. The company's yfinance sector matches the event's `sectors` list (broader exposure).

Each flag becomes a `GeopoliticalRisk` entry in the report with three fields: `event`, `impact`, and `severity` (5-point scale).

---

## Events tracked (v1)

### Taiwan Strait / TSMC supply chain
- **Sectors:** Technology, Communication Services
- **Why it matters:** TSMC manufactures roughly 60% of global foundry output and the overwhelming majority of leading-edge nodes (3nm, 5nm). A disruption at TSMC — whether from a geopolitical event, a natural disaster, or even a major operational failure — would propagate through every fabless semiconductor company and every device-maker depending on advanced silicon.
- **Severity baseline:** `strong`. The exposure is structural and the dependency is acknowledged by every affected company in their 10-K risk factors.

### US–China trade
- **Sectors:** Technology, Consumer Cyclical, Consumer Defensive, Industrials
- **Why it matters:** Tariffs, export controls, and outbound investment screening have direct effects on tech supply chains (Apple's manufacturing concentration in China, semiconductor equipment export controls), consumer brands selling into the China market (Starbucks, Nike, Estée Lauder), and industrials (Boeing's China backlog).
- **Severity baseline:** `strong`. Policy direction across both major US parties is for continued decoupling pressure.

### Russia–Ukraine war
- **Sectors:** Energy, Basic Materials
- **Why it matters:** Beyond direct exposure, the war has reshaped European energy markets and global fertilizer / grain pricing.
- **Severity baseline:** `neutral`. The acute price-shock phase has passed; structural effects (European energy sourcing, defense spending) persist but at lower volatility.

### Middle East tensions
- **Sectors:** Energy, Industrials (defense)
- **Why it matters:** The Gulf still supplies a meaningful share of global oil exports. Tensions affecting Iran, Israel, Saudi Arabia, or the Strait of Hormuz translate quickly to oil-price volatility. Defense contractors benefit from elevated procurement.
- **Severity baseline:** `neutral`. The map flags exposure; severity adjustments belong in real-time analysis, not in the always-on baseline.

### Pharma drug-pricing reform
- **Sectors:** Healthcare
- **Why it matters:** The IRA gave Medicare direct negotiation authority over a growing list of drugs. PBM scrutiny is also bipartisan. Top-line erosion on flagship drugs is a real, measurable risk over multi-year horizons for big pharma.
- **Severity baseline:** `neutral`. Already partially priced in for incumbents; uncertainty around scope expansion.

### Big Tech antitrust
- **Sectors:** Technology, Communication Services, Consumer Cyclical (e.g., Amazon)
- **Why it matters:** Active US DOJ cases against Google (search), ongoing FTC scrutiny of Meta and Amazon, EU's Digital Markets Act enforcement against gatekeepers. Outcomes range from fines (priced-in) to forced divestitures or product changes (not priced-in).
- **Severity baseline:** `neutral`. Companies have demonstrated ability to absorb fines; structural remedies remain a tail risk.

### Energy transition / decarbonization
- **Sectors:** Energy, Utilities, Basic Materials, Industrials
- **Why it matters:** Long-cycle structural shift in capital allocation. For oil majors, this is "stranded asset" risk on the 10–20 year horizon. For utilities, it's both opportunity (rate-base growth in renewables) and risk (legacy coal). For autos, it's the EV transition.
- **Severity baseline:** `weak`. Long-cycle, well-known. Already affecting capital allocation decisions.

### Regional banking stress
- **Sectors:** Financial Services
- **Why it matters:** The 2023 regional banking crisis (SVB, First Republic, Signature) revealed structural vulnerability in the regional bank model when held-to-maturity portfolios face mark-to-market pressure from rising rates. The acute phase has passed but the structural vulnerability remains for institutions with significant uninsured deposit bases.
- **Severity baseline:** `weak`. Mostly stabilized; specific names with weak balance sheets remain exposed.

---

## Maintenance guidance

This map should be reviewed and updated periodically — at minimum once a year, more often if a major new event emerges. When updating:

1. **Add events that are structural, not breaking.** A single news item is not enough.
2. **Be conservative on severity.** Default to `neutral` or `weak`. Reserve `strong` for events where the dependency is acknowledged in 10-K risk factors of multiple affected companies.
3. **Specify tickers AND sectors.** Tickers catch the most-exposed names; sectors catch the rest.
4. **Document the *impact*, not just the event.** "China–Taiwan tensions" is too vague; "semiconductor supply chain disruption from advanced-node concentration" is what the report consumer needs.

---

## Structural exposure vs. real-time signals

This map covers **structural geopolitical exposure** — the always-on, multi-year risks that don't change day-to-day but should always be acknowledged in a qualitative report. This is distinct from real-time market sentiment signals (VIX, short interest, breaking news), which operate at a different cadence and belong in a separate layer.
