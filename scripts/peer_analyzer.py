"""
Peer comparison.

Builds a peer snapshot by fetching abbreviated metrics for each peer ticker,
then computes the subject's relative position (leader / challenger / follower
/ laggard) based on market cap share and margin/growth ranks.
"""

from __future__ import annotations

from typing import Literal, Optional

from data_collector import fetch_company_bundle, get_peer_tickers
from report import PeerComparison, PeerSnapshot


def _build_snapshot(ticker: str) -> Optional[PeerSnapshot]:
    """Fetch a lightweight snapshot of a peer."""
    try:
        bundle = fetch_company_bundle(ticker, use_cache=True)
    except Exception:
        return None
    info = bundle.info
    if not info:
        return None
    return PeerSnapshot(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName"),
        market_cap=info.get("marketCap"),
        gross_margin=info.get("grossMargins"),
        operating_margin=info.get("operatingMargins"),
        pe_ratio=info.get("trailingPE"),
        revenue_growth_yoy=info.get("revenueGrowth"),
    )


def _rank_of(value: Optional[float], values: list[Optional[float]], higher_is_better: bool = True) -> Optional[int]:
    """1-indexed rank of `value` within `values`. None if value is None."""
    if value is None:
        return None
    cleaned = [(v, idx) for idx, v in enumerate(values) if v is not None]
    if not cleaned:
        return None
    cleaned.sort(key=lambda x: x[0], reverse=higher_is_better)
    for rank, (v, _idx) in enumerate(cleaned, start=1):
        if v == value:
            return rank
    return None


def _classify_position(
    market_cap_rank: Optional[int],
    margin_rank: Optional[int],
    n_peers: int,
) -> Literal["leader", "challenger", "follower", "laggard", "unknown"]:
    """Synthesize a 4-tier label from the ranks."""
    if market_cap_rank is None and margin_rank is None:
        return "unknown"
    # Average rank if both available; else use whichever is available
    ranks = [r for r in (market_cap_rank, margin_rank) if r is not None]
    avg_rank = sum(ranks) / len(ranks)
    total = n_peers + 1  # +1 because subject is included in ranking
    pct = avg_rank / total
    if pct <= 0.25:
        return "leader"
    if pct <= 0.5:
        return "challenger"
    if pct <= 0.75:
        return "follower"
    return "laggard"


def calc_peer_comparison(ticker: str, sector: Optional[str] = None) -> Optional[PeerComparison]:
    """Build the full peer comparison for the subject ticker."""
    ticker = ticker.upper()
    peer_tickers = get_peer_tickers(ticker, sector)
    if not peer_tickers:
        return None

    # Fetch subject + peers
    subject = _build_snapshot(ticker)
    if subject is None:
        return None
    peer_snapshots = [s for s in (_build_snapshot(p) for p in peer_tickers) if s is not None]

    if not peer_snapshots:
        return None

    # Build the full ranking pool (subject + peers)
    all_snapshots = [subject] + peer_snapshots
    market_caps = [s.market_cap for s in all_snapshots]
    margins = [s.operating_margin for s in all_snapshots]
    growths = [s.revenue_growth_yoy for s in all_snapshots]

    # Subject's ranks (higher = better for all of these)
    market_cap_rank = _rank_of(subject.market_cap, market_caps, higher_is_better=True)
    margin_rank = _rank_of(subject.operating_margin, margins, higher_is_better=True)
    growth_rank = _rank_of(subject.revenue_growth_yoy, growths, higher_is_better=True)

    # Market cap share
    valid_caps = [c for c in market_caps if c is not None]
    market_cap_share_pct: Optional[float] = None
    if subject.market_cap is not None and valid_caps:
        total = sum(valid_caps)
        if total > 0:
            market_cap_share_pct = (subject.market_cap / total) * 100

    relative_position = _classify_position(market_cap_rank, margin_rank, len(peer_snapshots))

    return PeerComparison(
        peers=peer_snapshots,
        market_cap_rank=market_cap_rank,
        market_cap_share_pct=market_cap_share_pct,
        margin_rank=margin_rank,
        growth_rank=growth_rank,
        relative_position=relative_position,
    )
