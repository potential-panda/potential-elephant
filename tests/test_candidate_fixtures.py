"""
Regression fixtures for candidate queue classification.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from elephant.candidates import CandidateMetrics
from elephant.candidates import _safe_float
from elephant.scoring import score_d5


def score(**kwargs):
    defaults = dict(
        is_jp=True, bbs_rank=None, is_today_bbs=False, speed_trend=None,
        speed_latest=None, has_yahoo_jp_bbs=None,
        bull_pct=None, return_1m=None, return_1y=None, value_chain_id=None,
        laggard_gap=None, has_tdnet=False, has_minkabu=False,
    )
    defaults.update(kwargs)
    return CandidateMetrics._score_legacy(**defaults)


class TestQueueAssignment:
    def test_3350_no_value_chain_fit_is_crowd_heat(self):
        # 3350.T = Metaplanet: JP, high BBS heat, no value_chain fit → C
        s, q, _ = score(is_jp=True, bbs_rank=3, is_today_bbs=True, speed_trend="accel",
                        speed_latest=15.0, bull_pct=55, return_1m=-8, value_chain_id=None)
        assert q == "C", f"3350.T should be queue C, got {q}"

    def test_8136_no_value_chain_crowd_panic_is_crowd_heat(self):
        # 8136.T: JP, huge spike, no value_chain fit → C
        s, q, _ = score(is_jp=True, bbs_rank=1, is_today_bbs=True, speed_trend="accel",
                        speed_latest=88.0, bull_pct=20, return_1m=-15, value_chain_id=None)
        assert q == "C", f"8136.T should be queue C, got {q}"

    def test_jp_value_chain_laggard_is_queue_A(self):
        s, q, _ = score(is_jp=True, bbs_rank=5, is_today_bbs=True, speed_trend="stable",
                        speed_latest=8.0, bull_pct=65, return_1m=-5,
                        value_chain_id="tech_local", laggard_gap=-20.0)
        assert q == "A", f"JP value_chain laggard should be queue A, got {q}"

    def test_jp_value_chain_bbs_hot_today_is_queue_A(self):
        s, q, _ = score(is_jp=True, bbs_rank=10, is_today_bbs=True, speed_trend="stable",
                        speed_latest=12.0, bull_pct=55, return_1m=-2,
                        value_chain_id="ai_infra", laggard_gap=None)
        assert q == "A", f"JP value_chain + BBS today should be queue A, got {q}"

    def test_jp_silent_value_chain_company_gets_penalty(self):
        # JP ticker in atlas but never appeared in BBS → penalty
        s_silent, _, _ = score(is_jp=True, bbs_rank=None, speed_latest=None,
                               value_chain_id="ai_infra", laggard_gap=-15.0)
        s_active, _, _ = score(is_jp=True, bbs_rank=5, is_today_bbs=True,
                               speed_latest=10.0, value_chain_id="ai_infra", laggard_gap=-15.0)
        assert s_silent < s_active, "silent JP should score capacity than active JP"

    def test_holding_signal_is_queue_B(self):
        s, q, _ = score(is_jp=True, bbs_rank=25, is_today_bbs=False, speed_latest=3.0,
                        bull_pct=65, return_1m=-8.0, value_chain_id=None)
        assert q == "B", f"holding signal should be queue B, got {q}"

    def test_5016_jp_materials_candidate(self):
        s, q, r = score(is_jp=True, bbs_rank=15, is_today_bbs=True, speed_trend="stable",
                        speed_latest=6.0, bull_pct=62, return_1m=-11,
                        value_chain_id="tech_local", laggard_gap=-18.0, has_minkabu=True)
        assert q == "A", f"5016.T value_chain candidate should be A, got {q}"
        assert s > 40, f"score should be meaningful, got {s}"

    def test_smci_us_value_chain_laggard_with_momentum(self):
        # SMCI: US, huge laggard gap, 1y still low → true laggard bonus, strong 1m
        s, q, _ = score(is_jp=False, bbs_rank=None, speed_latest=None,
                        has_yahoo_jp_bbs=None, return_1m=42.0, return_1y=6.0,
                        value_chain_id="ai_infra", laggard_gap=-170.0)
        assert q == "A", f"SMCI should be queue A, got {q}"
        assert s >= 55, f"SMCI score should be ≥55 (true laggard), got {s}"

    def test_us_with_bbs_gets_big_bonus(self):
        # US stock with Yahoo JP BBS comments → big bonus vs same stock without
        s_bbs, _, _ = score(is_jp=False, speed_latest=8.0, speed_trend="accel",
                            has_yahoo_jp_bbs=True, return_1m=5.0,
                            value_chain_id="ai_infra", laggard_gap=-20.0)
        s_no_bbs, _, _ = score(is_jp=False, speed_latest=None,
                               has_yahoo_jp_bbs=False, return_1m=5.0,
                               value_chain_id="ai_infra", laggard_gap=-20.0)
        assert s_bbs > s_no_bbs + 15, f"US with BBS ({s_bbs}) should be 15+ pts above no-BBS ({s_no_bbs})"

    def test_score_capped_at_100(self):
        # US stock with all signals maxed:
        # value_chain(15+20+5=40) + heat(15+8+20=43) + sentiment(15) + catalyst(3) = 101 → capped
        s, _, _ = score(is_jp=False, bbs_rank=None, speed_latest=8.0, speed_trend="accel",
                        has_yahoo_jp_bbs=True, bull_pct=90, return_1m=35.0, return_1y=5.0,
                        value_chain_id="ai_infra", laggard_gap=-170.0,
                        has_tdnet=False, has_minkabu=True)
        assert s == 100, f"score must be capped at 100, got {s}"


def test_safe_float_converts_nan_to_default():
    assert _safe_float(float("nan")) == 0.0
    assert _safe_float(None) == 0.0
    assert _safe_float("12.5") == 12.5


def test_us_yahoo_jp_bbs_presence_counts_in_d5():
    # US activity-presence (+1, requires actual recent comments) + prime
    # velocity tier (+2, >= 4.5 comments/hour) = 3.
    assert score_d5(
        [],
        bbs_velocity_latest=9.7,
        bbs_velocity_prev=None,
        has_minkabu=False,
        is_jp_ticker=False,
        has_yahoo_jp_bbs=True,
    ) == 3


def test_jp_bbs_presence_requires_rank_or_velocity_change_for_d5():
    # No rank/today signal, but velocity 9.7 still lands in the JP medium
    # tier (>= 5.0, < 10.0 comments/hour) = 1.
    assert score_d5(
        [],
        bbs_velocity_latest=9.7,
        bbs_velocity_prev=None,
        has_minkabu=False,
        is_jp_ticker=True,
        has_yahoo_jp_bbs=True,
    ) == 1
