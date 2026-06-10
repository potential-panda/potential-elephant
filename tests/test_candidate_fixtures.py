"""
Regression fixtures for candidate queue classification.

These verify the scoring logic behaves correctly for known reference cases
without requiring live data — all inputs are injected directly into _score().
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from elephant.candidates import CandidateMetrics


def score(**kwargs):
    defaults = dict(
        bbs_rank=None, is_today_bbs=False, speed_trend=None,
        bull_pct=None, return_1m=None, river_id=None,
        laggard_gap=None, has_tdnet=False, has_minkabu=False,
    )
    defaults.update(kwargs)
    return CandidateMetrics._score(**defaults)


class TestQueueAssignment:
    def test_3350_no_river_fit_is_crowd_heat(self):
        # 3350.T = Metaplanet: high BBS heat, no river fit → must be C
        s, q, _ = score(bbs_rank=3, is_today_bbs=True, speed_trend="accel",
                        bull_pct=55, return_1m=-8, river_id=None)
        assert q == "C", f"3350.T should be queue C (crowd heat), got {q}"

    def test_8136_no_river_crowd_panic_is_crowd_heat(self):
        # 8136.T: huge comment spike, negative sentiment, no river fit → C
        s, q, _ = score(bbs_rank=1, is_today_bbs=True, speed_trend="accel",
                        bull_pct=20, return_1m=-15, river_id=None)
        assert q == "C", f"8136.T should be queue C (crowd heat), got {q}"

    def test_river_laggard_is_queue_A(self):
        # A river node that is lagging ≤-10% vs layer → A
        s, q, _ = score(bbs_rank=5, is_today_bbs=True, speed_trend="stable",
                        bull_pct=65, return_1m=-5, river_id="tech_local",
                        laggard_gap=-20.0)
        assert q == "A", f"river laggard should be queue A, got {q}"

    def test_river_bbs_hot_today_is_queue_A(self):
        # River node, BBS rank ≤30 today → A even without laggard gap
        s, q, _ = score(bbs_rank=10, is_today_bbs=True, speed_trend="stable",
                        bull_pct=55, return_1m=-2, river_id="ai_infra",
                        laggard_gap=None)
        assert q == "A", f"river + BBS today should be queue A, got {q}"

    def test_holding_signal_is_queue_B(self):
        # Price down > 5%, bull still strong, no river fit → B
        s, q, _ = score(bbs_rank=25, is_today_bbs=False, bull_pct=65,
                        return_1m=-8.0, river_id=None)
        assert q == "B", f"holding signal should be queue B, got {q}"

    def test_5016_possible_materials_candidate(self):
        # 5016.T is a semiconductor materials supplier. Once classified
        # into a river with a laggard gap it should reach queue A.
        s, q, r = score(bbs_rank=15, is_today_bbs=True, speed_trend="stable",
                        bull_pct=62, return_1m=-11, river_id="tech_local",
                        laggard_gap=-18.0, has_minkabu=True)
        assert q == "A", f"5016.T river candidate should be A, got {q}"
        assert s > 40, f"score should be meaningful, got {s}"

    def test_score_capped_at_100(self):
        # bbs_rank=0 gives max(0,20-0)=20 BBS pts; total exceeds 100 before cap
        s, _, _ = score(bbs_rank=0, is_today_bbs=True, speed_trend="accel",
                        bull_pct=90, return_1m=-20, river_id="ai_infra",
                        laggard_gap=-30.0, has_tdnet=True, has_minkabu=True)
        assert s == 100, f"score must be capped at 100, got {s}"
