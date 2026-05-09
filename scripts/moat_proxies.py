"""
MOAT quantitative proxies.

Computes the numerical "fingerprints" that anchor the qualitative MOAT
assessment. The synthesizer reads these alongside the business description
to decide MOAT strength and type:

- Gross margin level + stability    → pricing power, intangibles
- Operating margin level + stability → operational moat (cost advantages)
- ROIC (return on invested capital)  → capital efficiency moat
- R&D intensity                      → intangible-asset reinvestment
- CAPEX intensity                    → infrastructure / efficient scale
- Revenue 3y CAGR                    → moat translates to growth?

Stability is measured as coefficient of variation (std / mean) — lower means
more stable, which suggests durable competitive positioning.
"""

from __future__ import annotations

import statistics
from typing import Optional

from data_collector import CompanyBundle, safe_get_series
from report import MoatQuantitativeProxies


def _cv(values: list[float]) -> Optional[float]:
    """Coefficient of variation: std / mean. Lower = more stable."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    m = statistics.mean(clean)
    if m == 0:
        return None
    try:
        sd = statistics.stdev(clean)
    except statistics.StatisticsError:
        return None
    return abs(sd / m)


def _avg(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _pairwise_ratios(num: list[float], den: list[float]) -> list[float]:
    """Element-wise ratio for matching positions. Skips zeros and length mismatches."""
    out = []
    n = min(len(num), len(den))
    for i in range(n):
        if den[i] != 0:
            out.append(num[i] / den[i])
    return out


def calc_moat_proxies(bundle: CompanyBundle) -> MoatQuantitativeProxies:
    """Compute every quantitative MOAT proxy from the company's financials."""

    fin = bundle.financials
    bs = bundle.balance_sheet
    cf = bundle.cashflow

    # Pull series (most-recent first, going back ~4 years)
    revenue = safe_get_series(fin, "Total Revenue")
    gross_profit = safe_get_series(fin, "Gross Profit")
    operating_income = safe_get_series(fin, "Operating Income")
    net_income = safe_get_series(fin, "Net Income")
    rd = safe_get_series(fin, "Research And Development")
    capex_series = safe_get_series(cf, "Capital Expenditure")

    # Equity for ROIC
    equity = safe_get_series(bs, "Stockholders Equity") or safe_get_series(bs, "Total Stockholder Equity")
    total_debt = safe_get_series(bs, "Total Debt") or safe_get_series(bs, "Long Term Debt")

    # ── Margins ──
    gross_margins = _pairwise_ratios(gross_profit, revenue)
    operating_margins = _pairwise_ratios(operating_income, revenue)

    gross_margin_avg = _avg(gross_margins)
    gross_margin_stability = _cv(gross_margins)
    operating_margin_avg = _avg(operating_margins)
    operating_margin_stability = _cv(operating_margins)

    # ── ROIC = NOPAT / Invested Capital
    # Approximation: Net Income / (Equity + Total Debt) — assumes effective tax in net income
    roic_series: list[float] = []
    n = min(len(net_income), len(equity), len(total_debt) if total_debt else len(equity))
    for i in range(n):
        invested = equity[i] + (total_debt[i] if total_debt and i < len(total_debt) else 0)
        if invested > 0:
            roic_series.append(net_income[i] / invested)

    roic_avg = _avg(roic_series)
    roic_stability = _cv(roic_series)

    # ── R&D intensity
    rd_intensity = _pairwise_ratios(rd, revenue) if rd else []
    rd_intensity_avg = _avg(rd_intensity)

    # ── CAPEX intensity (CAPEX is reported negative in yfinance cashflow → take abs)
    capex_abs = [abs(c) for c in capex_series] if capex_series else []
    capex_intensity = _pairwise_ratios(capex_abs, revenue)
    capex_intensity_avg = _avg(capex_intensity)

    # ── Revenue CAGR (3y)
    revenue_cagr_3y: Optional[float] = None
    if len(revenue) >= 4:
        # yfinance returns most-recent first. CAGR = (most_recent / 3y_ago)^(1/3) - 1
        try:
            most_recent = revenue[0]
            three_years_ago = revenue[3]
            if three_years_ago > 0 and most_recent > 0:
                revenue_cagr_3y = (most_recent / three_years_ago) ** (1 / 3) - 1
        except Exception:
            pass

    return MoatQuantitativeProxies(
        gross_margin_avg=gross_margin_avg,
        gross_margin_stability=gross_margin_stability,
        operating_margin_avg=operating_margin_avg,
        operating_margin_stability=operating_margin_stability,
        roic_avg=roic_avg,
        roic_stability=roic_stability,
        rd_intensity_avg=rd_intensity_avg,
        capex_intensity_avg=capex_intensity_avg,
        revenue_cagr_3y=revenue_cagr_3y,
    )
