#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.40",
#     "pandas>=2.0.0",
#     "numpy>=1.24.0",
#     "pydantic>=2.0.0",
#     "anthropic>=0.40.0",
# ]
# ///
"""
Charlie — Qualitative Analysis Agent (entrypoint)

Subcommands:
    analyze      Run the full pipeline (output for Ray)
    facts        Just the deterministic fact pack — no LLM synthesis
    moat         MOAT assessment focus (proxies + synthesized rating)
    sector       Sector outlook only (ETF momentum + geopolitical risks)
    peers        Peer comparison only
    macro        Macro environment only

Output is JSON by default (consumable by Ray). Pass --format text for human-readable.

Examples:
    uv run charlie.py analyze AAPL
    uv run charlie.py facts NVDA --format text
    uv run charlie.py moat GOOGL
    uv run charlie.py sector XOM --format text
    uv run charlie.py peers MSFT
"""

import argparse
import json
import sys
from typing import Any

# Make sibling modules importable when run directly
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from data_collector import fetch_company_bundle
from macro_env import calc_macro_facts
from moat_proxies import calc_moat_proxies
from peer_analyzer import calc_peer_comparison
from pipeline import build_fact_pack, run_full_pipeline
from sector_outlook import calc_sector_outlook_facts


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def emit_json(obj: Any) -> None:
    """Emit a Pydantic object or dict as pretty JSON."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, list):
        data = [o.model_dump() if hasattr(o, "model_dump") else o for o in obj]
    else:
        data = obj
    print(json.dumps(data, indent=2, default=str))


def fmt_pct(x, digits=1):
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}%" if abs(x) < 5 else f"{x:.{digits}f}%"


def fmt_num(x, digits=2):
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def fmt_money(x):
    if x is None:
        return "—"
    if abs(x) >= 1e12:
        return f"${x/1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:,.0f}"


def hr(width=70):
    return "─" * width


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────


def cmd_analyze(args):
    report = run_full_pipeline(args.ticker, use_cache=not args.no_cache)
    if args.format == "json":
        emit_json(report)
        return

    # Human-readable rendering
    print(f"CHARLIE — Qualitative Analysis: {report.ticker}")
    print(hr())
    print(f"  Company:      {report.company_name or '—'}")
    print(f"  Sector:       {report.sector or '—'}")
    print(f"  Industry:     {report.industry or '—'}")
    if report.qualitative_score is not None:
        print(f"  Qual. Score:  {report.qualitative_score}/100")
    print()

    if report.product_analysis:
        pa = report.product_analysis
        print("─ PRODUCT ─")
        print(f"  {pa.description}")
        if pa.core_products:
            print(f"  Core products: {', '.join(pa.core_products)}")
        print(f"  Pricing power:    {pa.pricing_power}  ({pa.pricing_power_reasoning})")
        print(f"  Substitutability: {pa.substitutability}  ({pa.substitutability_reasoning})")
        print()

    if report.sector_outlook:
        so = report.sector_outlook
        print("─ SECTOR ─")
        print(f"  ETF: {so.sector_etf or '—'}  |  3m: {fmt_num(so.sector_etf_return_3m_pct, 1)}%  YTD: {fmt_num(so.sector_etf_return_ytd_pct, 1)}%")
        if so.relative_strength_vs_spy_3m is not None:
            print(f"  Rel. strength vs SPY (3m): {so.relative_strength_vs_spy_3m:+.1f}pp")
        print(f"  Maturity: {so.sector_maturity}  |  Barriers: {so.barriers_to_entry}  |  Disruption: {so.disruption_risk}")
        print(f"  Outlook: {so.outlook.upper()}  — {so.outlook_reasoning}")
        if so.geopolitical_risks:
            print("  Geopolitical risks:")
            for g in so.geopolitical_risks:
                print(f"    • [{g.severity}] {g.event} — {g.impact}")
        print()

    if report.moat:
        m = report.moat
        print("─ MOAT ─")
        print(f"  Strength:   {m.moat_strength}")
        if m.moat_types:
            print(f"  Types:      {', '.join(m.moat_types)}")
        if m.moat_durability_years:
            print(f"  Durability: ~{m.moat_durability_years} years")
        print(f"  Reasoning:  {m.moat_reasoning}")
        print(f"  Quantitative anchors:")
        print(f"    Gross margin avg/stability: {fmt_pct(m.proxies.gross_margin_avg)} / cv={fmt_num(m.proxies.gross_margin_stability, 3)}")
        print(f"    Op. margin avg/stability:   {fmt_pct(m.proxies.operating_margin_avg)} / cv={fmt_num(m.proxies.operating_margin_stability, 3)}")
        print(f"    ROIC avg/stability:         {fmt_pct(m.proxies.roic_avg)} / cv={fmt_num(m.proxies.roic_stability, 3)}")
        print(f"    R&D intensity (avg):        {fmt_pct(m.proxies.rd_intensity_avg)}")
        print(f"    CAPEX intensity (avg):      {fmt_pct(m.proxies.capex_intensity_avg)}")
        print(f"    Revenue 3y CAGR:            {fmt_pct(m.proxies.revenue_cagr_3y)}")
        print()

    if report.customer_analysis:
        ca = report.customer_analysis
        print("─ CUSTOMER ─")
        print(f"  Type: {ca.customer_type}  |  Concentration: {ca.customer_concentration}")
        print(f"  Switching costs: {ca.switching_costs} — {ca.switching_costs_reasoning}")
        print(f"  Loyalty: {ca.customer_loyalty}")
        print()

    if report.supplier_analysis:
        sa = report.supplier_analysis
        print("─ SUPPLIER ─")
        print(f"  Concentration: {sa.supplier_concentration}  |  Negotiating power: {sa.supplier_negotiating_power}")
        print(f"  Supply-chain risk: {sa.supply_chain_risk}")
        if sa.critical_inputs:
            print(f"  Critical inputs: {', '.join(sa.critical_inputs)}")
        print()

    if report.macro_environment:
        me = report.macro_environment
        print("─ MACRO ─")
        print(f"  Cyclicality:         {me.cyclicality}")
        print(f"  Rate sensitivity:    {me.interest_rate_sensitivity} — {me.interest_rate_reasoning}")
        print(f"  FX sensitivity:      {me.fx_sensitivity}")
        print(f"  Regulatory env:      {me.regulatory_environment}")
        print(f"  Overall tailwind:    {me.overall_macro_tailwind}")
        print()

    if report.peer_comparison:
        pc = report.peer_comparison
        print("─ PEERS ─")
        print(f"  Position: {pc.relative_position.upper()}")
        if pc.market_cap_rank is not None:
            print(f"  Market cap rank: #{pc.market_cap_rank}  ({fmt_num(pc.market_cap_share_pct, 1)}% of group)")
        print(f"  Margin rank: #{pc.margin_rank or '—'}    Growth rank: #{pc.growth_rank or '—'}")
        print(f"  {'Ticker':<8} {'Mkt Cap':>10} {'Op Mgn':>8} {'P/E':>8} {'Rev YoY':>10}")
        for p in pc.peers:
            print(
                f"  {p.ticker:<8} "
                f"{fmt_money(p.market_cap):>10} "
                f"{fmt_pct(p.operating_margin):>8} "
                f"{fmt_num(p.pe_ratio, 1):>8} "
                f"{fmt_pct(p.revenue_growth_yoy):>10}"
            )
        print()

    if report.catalysts:
        print("─ CATALYSTS ─")
        for c in report.catalysts:
            print(f"  • [{c.horizon}] {c.description}  (likelihood: {c.likelihood}, impact: {c.impact})")
        print()

    if report.qualitative_risks:
        print("─ RISKS ─")
        for r in report.qualitative_risks:
            print(f"  • [{r.category} | {r.severity}] {r.description}")
        print()

    if report.growth_adjustment:
        ga = report.growth_adjustment
        delta_str = (
            f" ({ga.suggested_adjustment_pct:+.1f}pp)" if ga.suggested_adjustment_pct is not None else ""
        )
        print(f"─ HINT FOR RAY ─")
        print(f"  Growth signal: {ga.signal.upper()}{delta_str}")
        print(f"  Reasoning: {ga.reasoning}")
        print()

    if report.data_quality.warnings:
        print("─ DATA QUALITY ─")
        for w in report.data_quality.warnings:
            print(f"  ⚠ {w}")
        print(f"  Completeness: {report.data_quality.completeness_pct}%")
        print()

    print("Not financial advice. For informational purposes only.")


def cmd_facts(args):
    """Just the deterministic fact pack."""
    factpack = build_fact_pack(args.ticker, use_cache=not args.no_cache)
    if args.format == "json":
        emit_json(factpack)
        return
    print(f"FACT PACK — {factpack.ticker}")
    print(hr())
    print(f"  Company: {factpack.company_name or '—'}")
    print(f"  Sector / Industry: {factpack.sector or '—'} / {factpack.industry or '—'}")
    print(f"  Country: {factpack.country or '—'}  Employees: {factpack.employees or '—'}")
    print(f"  Market cap: {fmt_money(factpack.market_cap)}")
    if factpack.business_summary:
        summary = factpack.business_summary[:500] + ("…" if len(factpack.business_summary) > 500 else "")
        print(f"\n  Summary: {summary}\n")
    print(f"  Sector ETF: {factpack.sector_etf or '—'}")
    print(f"    3m return: {fmt_num(factpack.sector_etf_return_3m_pct, 1)}%")
    print(f"    YTD:       {fmt_num(factpack.sector_etf_return_ytd_pct, 1)}%")
    print(f"    Rel. vs SPY (3m): {fmt_num(factpack.relative_strength_vs_spy_3m, 1)}pp")
    print(f"  VIX: {fmt_num(factpack.vix_level, 1)}  |  DXY 3m: {fmt_num(factpack.dollar_index_3m_change_pct, 1)}%")
    if factpack.geopolitical_risks:
        print(f"\n  Geopolitical risks:")
        for g in factpack.geopolitical_risks:
            print(f"    • [{g.severity}] {g.event}")
    p = factpack.moat_proxies
    print(f"\n  MOAT proxies:")
    print(f"    Gross margin avg / stability:  {fmt_pct(p.gross_margin_avg)} / cv={fmt_num(p.gross_margin_stability, 3)}")
    print(f"    Op. margin avg / stability:    {fmt_pct(p.operating_margin_avg)} / cv={fmt_num(p.operating_margin_stability, 3)}")
    print(f"    ROIC avg / stability:          {fmt_pct(p.roic_avg)} / cv={fmt_num(p.roic_stability, 3)}")
    print(f"    R&D intensity:                 {fmt_pct(p.rd_intensity_avg)}")
    print(f"    CAPEX intensity:               {fmt_pct(p.capex_intensity_avg)}")
    print(f"    Revenue 3y CAGR:               {fmt_pct(p.revenue_cagr_3y)}")


def cmd_moat(args):
    bundle = fetch_company_bundle(args.ticker, use_cache=not args.no_cache)
    proxies = calc_moat_proxies(bundle)
    if args.format == "json":
        emit_json(proxies)
        return
    print(f"MOAT PROXIES — {args.ticker.upper()}")
    print(hr(40))
    print(f"  Gross margin avg:        {fmt_pct(proxies.gross_margin_avg)}")
    print(f"  Gross margin stability:  cv={fmt_num(proxies.gross_margin_stability, 3)}")
    print(f"  Op. margin avg:          {fmt_pct(proxies.operating_margin_avg)}")
    print(f"  Op. margin stability:    cv={fmt_num(proxies.operating_margin_stability, 3)}")
    print(f"  ROIC avg:                {fmt_pct(proxies.roic_avg)}")
    print(f"  ROIC stability:          cv={fmt_num(proxies.roic_stability, 3)}")
    print(f"  R&D intensity:           {fmt_pct(proxies.rd_intensity_avg)}")
    print(f"  CAPEX intensity:         {fmt_pct(proxies.capex_intensity_avg)}")
    print(f"  Revenue 3y CAGR:         {fmt_pct(proxies.revenue_cagr_3y)}")
    print()
    print("Note: MOAT rating itself requires synthesis. Use `analyze` for the full assessment.")


def cmd_sector(args):
    bundle = fetch_company_bundle(args.ticker, use_cache=not args.no_cache)
    sector = bundle.info.get("sector")
    facts = calc_sector_outlook_facts(sector, args.ticker)
    if args.format == "json":
        emit_json(facts)
        return
    print(f"SECTOR OUTLOOK — {args.ticker.upper()}  ({sector or 'unknown sector'})")
    print(hr())
    print(f"  Sector ETF:        {facts.get('sector_etf') or '—'}")
    print(f"  3m return:         {fmt_num(facts.get('sector_etf_return_3m_pct'), 1)}%")
    print(f"  YTD return:        {fmt_num(facts.get('sector_etf_return_ytd_pct'), 1)}%")
    rs = facts.get("relative_strength_vs_spy_3m")
    if rs is not None:
        print(f"  Rel. vs SPY (3m):  {rs:+.1f}pp")
    risks = facts.get("geopolitical_risks", [])
    if risks:
        print(f"\n  Geopolitical risks:")
        for g in risks:
            print(f"    • [{g.severity}] {g.event}")
            print(f"      → {g.impact}")
    else:
        print(f"\n  No baseline geopolitical risks flagged.")


def cmd_peers(args):
    bundle = fetch_company_bundle(args.ticker, use_cache=not args.no_cache)
    sector = bundle.info.get("sector")
    pc = calc_peer_comparison(args.ticker, sector)
    if args.format == "json":
        emit_json(pc)
        return
    if pc is None:
        print(f"No curated peers for {args.ticker.upper()}.")
        return
    print(f"PEER COMPARISON — {args.ticker.upper()}")
    print(hr())
    print(f"  Position:           {pc.relative_position.upper()}")
    print(f"  Market cap rank:    #{pc.market_cap_rank or '—'}  ({fmt_num(pc.market_cap_share_pct, 1)}% of group)")
    print(f"  Margin rank:        #{pc.margin_rank or '—'}")
    print(f"  Growth rank:        #{pc.growth_rank or '—'}")
    print()
    print(f"  {'Ticker':<8} {'Mkt Cap':>10} {'Gross':>8} {'Op Mgn':>8} {'P/E':>8} {'Rev YoY':>10}")
    for p in pc.peers:
        print(
            f"  {p.ticker:<8} "
            f"{fmt_money(p.market_cap):>10} "
            f"{fmt_pct(p.gross_margin):>8} "
            f"{fmt_pct(p.operating_margin):>8} "
            f"{fmt_num(p.pe_ratio, 1):>8} "
            f"{fmt_pct(p.revenue_growth_yoy):>10}"
        )


def cmd_macro(args):
    bundle = fetch_company_bundle(args.ticker, use_cache=not args.no_cache)
    sector = bundle.info.get("sector")
    facts = calc_macro_facts(sector)
    if args.format == "json":
        emit_json(facts)
        return
    print(f"MACRO ENVIRONMENT — {args.ticker.upper()}  ({sector or 'unknown sector'})")
    print(hr(40))
    print(f"  VIX level:               {fmt_num(facts.get('vix_level'), 1)}")
    print(f"  Dollar index 3m change:  {fmt_num(facts.get('dollar_index_3m_change_pct'), 1)}%")
    print(f"  Sector cyclicality:      {facts.get('cyclicality')}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(prog="charlie", description="Charlie qualitative analysis agent")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["json", "text"], default="json", help="Output format (default: json)")
    common.add_argument("--no-cache", action="store_true", help="Bypass the 1h disk cache")

    p_an = sub.add_parser("analyze", parents=[common], help="Full pipeline (output for Ray)")
    p_an.add_argument("ticker")
    p_an.set_defaults(func=cmd_analyze)

    p_fa = sub.add_parser("facts", parents=[common], help="Deterministic fact pack (no LLM synthesis)")
    p_fa.add_argument("ticker")
    p_fa.set_defaults(func=cmd_facts)

    p_mt = sub.add_parser("moat", parents=[common], help="MOAT quantitative proxies")
    p_mt.add_argument("ticker")
    p_mt.set_defaults(func=cmd_moat)

    p_se = sub.add_parser("sector", parents=[common], help="Sector outlook (ETF momentum + geopolitical)")
    p_se.add_argument("ticker")
    p_se.set_defaults(func=cmd_sector)

    p_pe = sub.add_parser("peers", parents=[common], help="Peer comparison")
    p_pe.add_argument("ticker")
    p_pe.set_defaults(func=cmd_peers)

    p_ma = sub.add_parser("macro", parents=[common], help="Macro environment snapshot")
    p_ma.add_argument("ticker")
    p_ma.set_defaults(func=cmd_macro)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
