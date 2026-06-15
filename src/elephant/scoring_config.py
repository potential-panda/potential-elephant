# v1 scoring constants — all values are calibration targets, not permanent product truth.

# D1 river_fit_score point table
D1_APPROVED_PRIMARY = 25
D1_APPROVED_SECONDARY = 20
D1_PROPOSED_WITH_EVIDENCE = 18
D1_MINKABU_THEME_MATCH = 15
D1_KEYWORD_ROUTING = 8

# D2 layer_alpha_score additive conditions
D2_PEER_MOMENTUM_PTS = 8      # >= 2 active/weak peers up >= 7% in 4w
D2_PEER_MOMENTUM_MIN_COUNT = 2
D2_PEER_MOMENTUM_THRESHOLD = 7.0  # percent
D2_THIN_LAYER_PTS = 5         # layer has < 3 active/weak nodes
D2_THIN_LAYER_THRESHOLD = 3
D2_NOT_CROWDED_PTS = 2        # v1 proxy: no Minkabu coverage
D2_MAX = 15

# D3 relative_laggard_score
D3_MIN_PEER_COUNT = 3
D3_POINTS_4W_MULT = 1.5
D3_POINTS_4W_CAP = 15
D3_POINTS_12W_MULT = 0.5
D3_POINTS_12W_CAP = 5
D3_MAX = 20

# D4 catalyst_score
D4_MAX = 20
D4_FRESHNESS_DAYS = 14

# Raw event points (v1 defaults)
D4_RAW_TDNET_MAJOR = 18
D4_RAW_TDNET_MINOR = 10
D4_RAW_POLICY_SECTOR = 14
D4_RAW_THIRD_PARTY_REPORTING = 12
D4_RAW_IR_PIVOT = 12

# Source tier multipliers
SOURCE_TIER_MULTIPLIERS = {1: 1.0, 2: 1.0, 3: 0.7, 4: 0.5, 5: 0.0, 6: 0.0}

# TDnet major disclosure keywords (Japanese) — v1 defaults, calibration targets
MAJOR_DISCLOSURE_KEYWORDS = [
    "決算", "合併", "買収", "資本業務提携", "重要な契約", "株式交換",
    "株式分割", "自己株式", "規制当局", "承認", "行政処分", "公開買付",
    "第三者割当", "事業譲渡",
]

# D5 attention_change_score
D5_BBS_RANK_IMPROVE_PTS = 4   # 3 consecutive improving days
D5_BBS_RANK_IMPROVE_DAYS = 3
D5_BBS_VELOCITY_PTS = 2       # >20% wow velocity increase
D5_BBS_VELOCITY_THRESHOLD = 0.20
D5_MINKABU_NEW_PTS = 3
D5_ANALYST_NEW_PTS = 3        # not yet implementable in v1; scored as 0
D5_BBS_CAP = 6                # BBS rank+velocity combined cap
D5_MAX = 10

# D6 coverage_gap_score (v1: freshness proxy)
D6_NO_COVERAGE_PTS = 10
D6_STALE_COVERAGE_PTS = 5
D6_SPARSE_COVERAGE_PTS = 2
D6_STALE_THRESHOLD_DAYS = 90
D6_ACTIVE_THRESHOLD_DAYS = 30

# Noise penalty (most-negative wins)
NOISE_PENALTY_BBS_TOP10_FALLING = -20  # BBS top 10 + falling price + no catalyst
NOISE_PENALTY_BBS_TOP20_NO_CATALYST = -15  # BBS top 20 + no catalyst + no minkabu
NOISE_PENALTY_PRIOR_PUMP = -10
NOISE_PENALTY_GENERIC_TAG = -8
NOISE_PENALTY_SYNDICATED_ONLY = -5

NOISE_BBS_TOP20_THRESHOLD = 20
NOISE_BBS_TOP10_THRESHOLD = 10
NOISE_PUMP_PRICE_DROP_PCT = 20.0  # % drop from 28d high

# Decision memory suppression windows (days)
SUPPRESSION_DAYS_1_PASS = 28
SUPPRESSION_DAYS_2_PASS = 42
SUPPRESSION_DAYS_3_PLUS = 84

# Decision memory penalties
DM_PENALTY_1_PASS = -10
DM_PENALTY_2_PASS = -20
DM_PENALTY_3_PLUS = -25

# Queue score thresholds
QUEUE_A_THRESHOLD = 70
QUEUE_B_THRESHOLD = 40
QUEUE_C_THRESHOLD = 10
