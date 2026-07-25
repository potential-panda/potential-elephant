"""
D1-D6 research-worthiness scoring model.

Scores rank research attention, not investment merit.
High score = "you should look at this company today."
High score does NOT mean buy/sell/hold.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from elephant.scoring_config import (
    D1_APPROVED_PRIMARY, D1_APPROVED_SECONDARY, D1_PROPOSED_WITH_EVIDENCE,
    D1_MINKABU_THEME_MATCH, D1_KEYWORD_ROUTING,
    D2_PEER_MOMENTUM_PTS, D2_PEER_MOMENTUM_MIN_COUNT, D2_PEER_MOMENTUM_THRESHOLD,
    D2_THIN_STAGE_PTS, D2_THIN_STAGE_THRESHOLD, D2_NOT_CROWDED_PTS, D2_MAX,
    D3_MIN_PEER_COUNT, D3_POINTS_4W_MULT, D3_POINTS_4W_CAP,
    D3_POINTS_12W_MULT, D3_POINTS_12W_CAP, D3_MAX,
    D4_MAX, D4_FRESHNESS_DAYS, D4_RAW_TDNET_MAJOR, D4_RAW_TDNET_MINOR,
    D4_RAW_POLICY_SECTOR, D4_RAW_THIRD_PARTY_REPORTING, D4_RAW_IR_PIVOT,
    SOURCE_TIER_MULTIPLIERS, MAJOR_DISCLOSURE_KEYWORDS,
    D5_JP_BBS_TOP_RANK_PTS, D5_JP_BBS_TOP_RANK_THRESHOLD,
    D5_JP_BBS_VELOCITY_MED_PTS, D5_JP_BBS_VELOCITY_MED_THRESHOLD,
    D5_JP_BBS_VELOCITY_HIGH_PTS, D5_JP_BBS_VELOCITY_HIGH_THRESHOLD,
    D5_US_BBS_VELOCITY_MED_PTS, D5_US_BBS_VELOCITY_ACTIVE_THRESHOLD,
    D5_US_BBS_VELOCITY_HIGH_PTS, D5_US_BBS_VELOCITY_UPPER_THRESHOLD,
    D5_BBS_WOW_CHANGE_PTS, D5_BBS_WOW_CHANGE_THRESHOLD,
    D5_BBS_ACCEL_PTS, D5_BBS_ACCEL_RATIO_THRESHOLD,
    D5_US_BBS_ACTIVITY_PRESENCE_PTS, D5_US_BBS_ACTIVITY_PRESENCE_THRESHOLD,
    D5_MINKABU_NEW_PTS, D5_BBS_CAP, D5_MAX,
    D6_NO_COVERAGE_PTS, D6_STALE_COVERAGE_PTS, D6_SPARSE_COVERAGE_PTS,
    D6_STALE_THRESHOLD_DAYS, D6_ACTIVE_THRESHOLD_DAYS,
    NOISE_PENALTY_BBS_TOP10_FALLING, NOISE_PENALTY_BBS_TOP20_NO_CATALYST,
    NOISE_PENALTY_PRIOR_PUMP, NOISE_PENALTY_GENERIC_TAG, NOISE_PENALTY_SYNDICATED_ONLY,
    NOISE_BBS_TOP20_THRESHOLD, NOISE_BBS_TOP10_THRESHOLD, NOISE_PUMP_PRICE_DROP_PCT,
    DM_PENALTY_1_PASS, DM_PENALTY_2_PASS, DM_PENALTY_3_PLUS,
)


def score_d1(
    company_status: Optional[str],
    is_primary_value_chain: bool = True,
    has_proposed_evidence: bool = False,
    has_minkabu_theme: bool = False,
    has_keyword_routing: bool = False,
) -> int:
    """Value Chain fit score (0-25). Use highest applicable tier only, do not sum."""
    if company_status in ("active", "weak", "watch"):
        return D1_APPROVED_PRIMARY if is_primary_value_chain else D1_APPROVED_SECONDARY
    if company_status == "proposed" and has_proposed_evidence:
        return D1_PROPOSED_WITH_EVIDENCE
    if has_minkabu_theme:
        return D1_MINKABU_THEME_MATCH
    if has_keyword_routing:
        return D1_KEYWORD_ROUTING
    return 0


def score_d2(
    peer_4w_returns: list[float],
    active_weak_company_count: int,
    has_minkabu: bool,
) -> int:
    """Stage alpha score (0-15, additive)."""
    pts = 0
    # +8 if >= 2 active/weak peers up >= threshold in 4w
    peers_up = sum(1 for r in peer_4w_returns if r is not None and r >= D2_PEER_MOMENTUM_THRESHOLD)
    if peers_up >= D2_PEER_MOMENTUM_MIN_COUNT:
        pts += D2_PEER_MOMENTUM_PTS
    # +5 if stage has < 3 active/weak companies (thin stage bonus)
    if active_weak_company_count < D2_THIN_STAGE_THRESHOLD:
        pts += D2_THIN_STAGE_PTS
    # +2 if not crowded (v1 proxy: no Minkabu coverage)
    if not has_minkabu:
        pts += D2_NOT_CROWDED_PTS
    return min(pts, D2_MAX)


def score_d3(
    candidate_4w: Optional[float],
    candidate_12w: Optional[float],
    peer_avg_4w: Optional[float],
    peer_avg_12w: Optional[float],
    valid_peer_count: int,
) -> tuple[int, bool]:
    """
    Relative laggard score (0-20).
    Returns (score, weak_peer_set).
    weak_peer_set=True when < D3_MIN_PEER_COUNT valid peers.
    """
    if valid_peer_count < D3_MIN_PEER_COUNT:
        return 0, True
    if candidate_4w is None or peer_avg_4w is None:
        return 0, False

    laggard_gap_4w = peer_avg_4w - candidate_4w
    points_4w = min(D3_POINTS_4W_CAP, max(0.0, laggard_gap_4w * D3_POINTS_4W_MULT))

    points_12w = 0.0
    if candidate_12w is not None and peer_avg_12w is not None:
        laggard_gap_12w = peer_avg_12w - candidate_12w
        points_12w = min(D3_POINTS_12W_CAP, max(0.0, laggard_gap_12w * D3_POINTS_12W_MULT))

    return int(min(D3_MAX, points_4w + points_12w)), False


def _classify_tdnet_title(title: str) -> int:
    """Returns raw points for a TDnet disclosure based on title keyword match."""
    lowercase_title = title.lower()
    for keyword in MAJOR_DISCLOSURE_KEYWORDS:
        if keyword in title:
            return D4_RAW_TDNET_MAJOR
    return D4_RAW_TDNET_MINOR


def score_d4(evidence_items: list[dict]) -> tuple[float, int]:
    """
    Catalyst score (0-20).
    Returns (score, best_tier) where best_tier is the lowest tier number used.
    Multiple events: take max, not sum.
    Deduplication: same deduplication_id uses only highest-tier source.
    """
    if not evidence_items:
        return 0.0, 6

    # Deduplicate: for each deduplication_id group, keep only highest tier (lowest number)
    deduped: dict[str, dict] = {}
    no_dedup_id = []
    for item in evidence_items:
        if item.get("role") != "catalyst":
            continue
        ded_id = item.get("deduplication_id")
        if ded_id:
            existing = deduped.get(ded_id)
            if existing is None or item.get("source_tier", 6) < existing.get("source_tier", 6):
                deduped[ded_id] = item
        else:
            no_dedup_id.append(item)

    catalyst_items = list(deduped.values()) + no_dedup_id

    best_contribution = 0.0
    best_tier = 6
    for item in catalyst_items:
        tier = item.get("source_tier", 6)
        tier_mult = SOURCE_TIER_MULTIPLIERS.get(tier, 0.0)
        if tier_mult == 0.0:
            continue
        raw_pts = item.get("raw_points", 0)
        days_old = item.get("freshness_days", 0)
        freshness = max(0.0, 1.0 - days_old / D4_FRESHNESS_DAYS)
        contribution = raw_pts * tier_mult * freshness
        if contribution > best_contribution:
            best_contribution = contribution
            best_tier = tier

    return round(min(D4_MAX, best_contribution), 2), best_tier


def score_d5(
    bbs_rank_history: list[dict],
    bbs_velocity_latest: Optional[float],
    bbs_velocity_prev: Optional[float],
    has_minkabu: bool,
    minkabu_is_new: bool = False,
    *,
    is_jp_ticker: bool = True,
    has_yahoo_jp_bbs: Optional[bool] = None,
    bbs_rank: Optional[int] = None,
    bbs_is_today: bool = False,
    bbs_speed_history_recent: Optional[list[float]] = None,
) -> int:
    """Attention change score (0-10, additive, BBS points capped at 6).

    `bbs_rank_history` is unused — the v1 rank-improvement signal required
    rank history that the harvester does not populate. Kept as a parameter
    for call-site compatibility.
    """
    bbs_pts = 0
    speeds = bbs_speed_history_recent or []

    # Presence/rank signal. JP attention is read off today's BBS rank; Yahoo
    # JP BBS structurally under-covers US tickers, so a US ticker instead
    # needs an actual recent comment, not just a page, to earn this point.
    if is_jp_ticker:
        if bbs_rank is not None and bbs_is_today and bbs_rank <= D5_JP_BBS_TOP_RANK_THRESHOLD:
            bbs_pts += D5_JP_BBS_TOP_RANK_PTS
    else:
        if (has_yahoo_jp_bbs is True and bbs_velocity_latest is not None
                and bbs_velocity_latest >= D5_US_BBS_ACTIVITY_PRESENCE_THRESHOLD):
            bbs_pts += D5_US_BBS_ACTIVITY_PRESENCE_PTS

    # Current velocity level, tiered separately per market since observed US
    # comment volume is structurally lower than JP.
    if bbs_velocity_latest is not None:
        if is_jp_ticker:
            if bbs_velocity_latest >= D5_JP_BBS_VELOCITY_HIGH_THRESHOLD:
                bbs_pts += D5_JP_BBS_VELOCITY_HIGH_PTS
            elif bbs_velocity_latest >= D5_JP_BBS_VELOCITY_MED_THRESHOLD:
                bbs_pts += D5_JP_BBS_VELOCITY_MED_PTS
        else:
            if bbs_velocity_latest >= D5_US_BBS_VELOCITY_UPPER_THRESHOLD:
                bbs_pts += D5_US_BBS_VELOCITY_HIGH_PTS
            elif bbs_velocity_latest >= D5_US_BBS_VELOCITY_ACTIVE_THRESHOLD:
                bbs_pts += D5_US_BBS_VELOCITY_MED_PTS

    # One-step latest-vs-prev velocity change (week over week).
    if (bbs_velocity_latest is not None and bbs_velocity_prev is not None
            and bbs_velocity_prev > 0):
        wow_change = (bbs_velocity_latest - bbs_velocity_prev) / bbs_velocity_prev
        if wow_change >= D5_BBS_WOW_CHANGE_THRESHOLD:
            bbs_pts += D5_BBS_WOW_CHANGE_PTS

    # Multi-point acceleration: change-of-velocity distinct from the one-step
    # check above — two consecutive increases, not just one comparison.
    if len(speeds) >= 3 and speeds[1] > 0 and speeds[2] > 0:
        if (speeds[0] / speeds[1] >= D5_BBS_ACCEL_RATIO_THRESHOLD
                and speeds[1] / speeds[2] >= D5_BBS_ACCEL_RATIO_THRESHOLD):
            bbs_pts += D5_BBS_ACCEL_PTS

    bbs_pts = min(bbs_pts, D5_BBS_CAP)

    analyst_pts = 0
    # +3 if Minkabu coverage newly initiated (v1 proxy: has_minkabu and flagged as new)
    if has_minkabu and minkabu_is_new:
        analyst_pts += D5_MINKABU_NEW_PTS
    # +3 for independent analyst coverage initiated — not yet implementable in v1

    return min(bbs_pts + analyst_pts, D5_MAX)


def score_d6(
    minkabu_scraped_at: Optional[datetime],
    d1: int,
) -> int:
    """Coverage gap score (0-10). Only awarded when D1 > 0."""
    if d1 == 0:
        return 0
    if minkabu_scraped_at is None:
        return D6_NO_COVERAGE_PTS
    age_days = (datetime.now() - minkabu_scraped_at).days
    if age_days > D6_STALE_THRESHOLD_DAYS:
        return D6_NO_COVERAGE_PTS
    if age_days > D6_ACTIVE_THRESHOLD_DAYS:
        return D6_STALE_COVERAGE_PTS
    return D6_SPARSE_COVERAGE_PTS


def compute_noise_penalty(
    bbs_rank: Optional[int],
    price_falling: bool,
    has_catalyst_tier1_4: bool,
    has_minkabu_support: bool,
    prior_pump_pattern: bool,
    generic_tag_only: bool,
    has_company_specific_evidence: bool,
    syndicated_only: bool,
) -> int:
    """Most-negative-wins semantics: apply only the single worst applicable penalty."""
    candidates = []
    if bbs_rank is not None and bbs_rank <= NOISE_BBS_TOP10_THRESHOLD and price_falling and not has_catalyst_tier1_4:
        candidates.append(NOISE_PENALTY_BBS_TOP10_FALLING)
    if bbs_rank is not None and bbs_rank <= NOISE_BBS_TOP20_THRESHOLD and not has_catalyst_tier1_4 and not has_minkabu_support:
        candidates.append(NOISE_PENALTY_BBS_TOP20_NO_CATALYST)
    if prior_pump_pattern:
        candidates.append(NOISE_PENALTY_PRIOR_PUMP)
    if generic_tag_only and not has_company_specific_evidence:
        candidates.append(NOISE_PENALTY_GENERIC_TAG)
    if syndicated_only:
        candidates.append(NOISE_PENALTY_SYNDICATED_ONLY)
    return min(candidates, default=0)


def compute_decision_memory_adjustment(pass_count: int) -> int:
    """Returns a negative score adjustment based on how many times a name was passed."""
    if pass_count <= 0:
        return 0
    if pass_count == 1:
        return DM_PENALTY_1_PASS
    if pass_count == 2:
        return DM_PENALTY_2_PASS
    return DM_PENALTY_3_PLUS


def compute_final_score(
    d1: int, d2: int, d3: int, d4: float, d5: int, d6: int,
    decision_memory_adjustment: int,
    noise_penalty: int,
) -> int:
    raw = d1 + d2 + d3 + d4 + d5 + d6
    final = raw + decision_memory_adjustment + noise_penalty
    return int(max(0, min(100, final)))
