# Initial ticker universe from the Macro Value Chains Tracking & Detailed Tickers Matrix (V1)
# Source: user's Google Doc (1JZ6gh_BVbed4eebauaUuvZw5Qq8AtjTMH0hucFJcUQA)
#
# Stage split rationale (doc uses combined "Prime/Bottleneck Stream"):
#   prime  — core designers, foundational ETFs, large-cap primary engines
#   bottleneck — specialized bottleneck components, highest-alpha niche JP names

SEED_NODES: dict[str, list[dict]] = {
    "ai_infra": [
        # Source
        {"ticker": "MSFT",   "stage": "driver", "market": "US", "name": "Microsoft",       "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "GOOGL",  "stage": "driver", "market": "US", "name": "Alphabet",        "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "AMZN",   "stage": "driver", "market": "US", "name": "Amazon",          "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "META",   "stage": "driver", "market": "US", "name": "Meta Platforms",  "role": "Primary hyperscaler capital deployer for AI CapEx"},
        # Prime stream — core compute designers and broad ETFs
        {"ticker": "NVDA",   "stage": "prime",  "market": "US", "name": "NVIDIA",          "role": "GPU designer and dominant AI compute platform"},
        {"ticker": "AVGO",   "stage": "prime",  "market": "US", "name": "Broadcom",        "role": "AI networking chips and custom ASICs for hyperscalers"},
        {"ticker": "SMH",    "stage": "prime",  "market": "US", "name": "VanEck Semiconductor ETF",        "role": "Broad semiconductor ETF — US lead-lag indicator for JP suppliers"},
        {"ticker": "XSD",    "stage": "prime",  "market": "US", "name": "SPDR S&P Semiconductor ETF",     "role": "Broad semiconductor ETF — US lead-lag indicator for JP suppliers"},
        {"ticker": "6702.T", "stage": "prime",  "market": "JP", "name": "Fujitsu",         "role": "Server hardware and advanced compute company integration"},
        # Bottleneck stream — physical bottlenecks (memory, power semiconductors)
        {"ticker": "MU",     "stage": "bottleneck", "market": "US", "name": "Micron Technology",          "role": "DRAM and HBM memory — key AI compute bottleneck"},
        {"ticker": "6503.T", "stage": "bottleneck", "market": "JP", "name": "Mitsubishi Electric",        "role": "Power semiconductor components and industrial liquid cooling"},
        # Capacity stream — power and grid infrastructure
        {"ticker": "VST",    "stage": "capacity",  "market": "US", "name": "Vistra Corp",                "role": "Independent power producer serving AI data center load"},
        {"ticker": "CEG",    "stage": "capacity",  "market": "US", "name": "Constellation Energy",       "role": "Nuclear baseload for AI infrastructure power demand"},
        {"ticker": "XLU",    "stage": "capacity",  "market": "US", "name": "Utilities Select Sector SPDR", "role": "Broad utilities ETF covering grid capacity plays"},
        {"ticker": "NLR",    "stage": "capacity",  "market": "US", "name": "VanEck Nuclear Energy ETF",  "role": "Nuclear energy ETF"},
        {"ticker": "POWR",   "stage": "capacity",  "market": "US", "name": "US Power Infrastructure ETF", "role": "Power infrastructure ETF"},
        {"ticker": "6501.T", "stage": "capacity",  "market": "JP", "name": "Hitachi",                   "role": "Grid hardware and industrial power transformers"},
        {"ticker": "9501.T", "stage": "capacity",  "market": "JP", "name": "Tokyo Electric Power (TEPCO)", "role": "Local electricity infrastructure provision"},
    ],

    "tech_local": [
        # Source
        {"ticker": "TSM",    "stage": "driver", "market": "US", "name": "Taiwan Semiconductor", "role": "Epicenter of global fabrication localization transition"},
        {"ticker": "INTC",   "stage": "driver", "market": "US", "name": "Intel",               "role": "US domestic chip manufacturing push"},
        # Prime stream — lithography and manufacturing equipment
        {"ticker": "ASML",   "stage": "prime",  "market": "US", "name": "ASML Holding",        "role": "Semiconductor lithography — monopoly on EUV equipment"},
        {"ticker": "LRCX",   "stage": "prime",  "market": "US", "name": "Lam Research",        "role": "Semiconductor etch and deposition equipment"},
        {"ticker": "AMAT",   "stage": "prime",  "market": "US", "name": "Applied Materials",   "role": "Semiconductor manufacturing equipment"},
        # Bottleneck stream — ultra-precision JP bottlenecks
        {"ticker": "6146.T", "stage": "bottleneck", "market": "JP", "name": "Disco Corp",          "role": "Ultra-precision semiconductor dicing and grinding tools"},
        {"ticker": "8035.T", "stage": "bottleneck", "market": "JP", "name": "Tokyo Electron",      "role": "Semiconductor etching and coating systems"},
        {"ticker": "6857.T", "stage": "bottleneck", "market": "JP", "name": "Advantest",           "role": "Specialized chip testing hardware"},
        # Capacity stream — industrial RE and automation
        {"ticker": "PLD",    "stage": "capacity",  "market": "US", "name": "Prologis",            "role": "Heavy industrial real estate for onshored production"},
        {"ticker": "XLI",    "stage": "capacity",  "market": "US", "name": "Industrials Select Sector SPDR", "role": "Broad industrials ETF"},
        {"ticker": "6506.T", "stage": "capacity",  "market": "JP", "name": "Yaskawa Electric",   "role": "Industrial assembly line robotics"},
        {"ticker": "6273.T", "stage": "capacity",  "market": "JP", "name": "SMC Corp",           "role": "Pneumatic automation factory floor inputs"},
    ],

    "physical_ai": [
        # Source
        {"ticker": "TSLA",   "stage": "driver", "market": "US", "name": "Tesla",              "role": "Optimus humanoid robot program — primary capital deployer"},
        {"ticker": "AMZN",   "stage": "driver", "market": "US", "name": "Amazon",             "role": "Fulfillment robotics deployment and automation policy"},
        # Prime stream — broad robotics ETFs
        {"ticker": "ROBO",   "stage": "prime",  "market": "US", "name": "ROBO Global Robotics ETF",       "role": "Broad robotics and automation ETF"},
        {"ticker": "BOTZ",   "stage": "prime",  "market": "US", "name": "Global X Robotics ETF",          "role": "Broad robotics and AI ETF"},
        # Bottleneck stream — precision component bottlenecks
        {"ticker": "6594.T", "stage": "bottleneck", "market": "JP", "name": "Nidec",              "role": "High-efficiency precision miniature motors for robotics"},
        {"ticker": "6324.T", "stage": "bottleneck", "market": "JP", "name": "Harmonic Drive Systems", "role": "Strain wave gears for robotic joints — key bottleneck"},
        {"ticker": "6861.T", "stage": "bottleneck", "market": "JP", "name": "Keyence",            "role": "High-precision vision sensors and inspection systems"},
        # Capacity stream — deployment and logistics
        {"ticker": "ARKQ",   "stage": "capacity",  "market": "US", "name": "ARK Autonomous Technology ETF",  "role": "Autonomous technology and robotics ETF"},
        {"ticker": "6273.T", "stage": "capacity",  "market": "JP", "name": "SMC Corp",           "role": "Heavy floor grid automation inputs"},
        {"ticker": "9020.T", "stage": "capacity",  "market": "JP", "name": "East Japan Railway", "role": "Rail logistics connectivity for autonomous deployment"},
    ],

    "longevity": [
        # Source
        {"ticker": "LLY",    "stage": "driver", "market": "US", "name": "Eli Lilly",          "role": "GLP-1 and metabolic therapy leader — primary capital deployer"},
        {"ticker": "NVO",    "stage": "driver", "market": "US", "name": "Novo Nordisk",       "role": "GLP-1 and metabolic therapy leader — primary capital deployer"},
        # Prime stream — drug delivery components
        {"ticker": "WST",    "stage": "prime",  "market": "US", "name": "West Pharmaceutical Services", "role": "Specialized drug containment and syringe mechanics"},
        # Bottleneck stream — API and biologics bottlenecks
        {"ticker": "4568.T", "stage": "bottleneck", "market": "JP", "name": "Daiichi Sankyo",     "role": "Advanced API synthesis and macromolecule processing"},
        {"ticker": "4519.T", "stage": "bottleneck", "market": "JP", "name": "Chugai Pharmaceutical", "role": "Specialized antibody-based product tracks"},
        # Capacity stream — pharmaceutical logistics
        {"ticker": "CAH",    "stage": "capacity",  "market": "US", "name": "Cardinal Health",    "role": "Large-scale pharmaceutical supply chain management"},
        {"ticker": "MCK",    "stage": "capacity",  "market": "US", "name": "McKesson Corp",      "role": "Large-scale pharmaceutical supply chain management"},
        {"ticker": "9021.T", "stage": "capacity",  "market": "JP", "name": "West Japan Railway", "role": "Specialized clinical cargo routes"},
    ],
}


_RIVER_CAUSAL_EDGES = {
    "ai_infra": "hyperscaler AI CapEx -> compute/networking demand -> component and power bottlenecks",
    "tech_local": "fab localization and policy support -> semiconductor equipment demand -> precision tool/material bottlenecks",
    "physical_ai": "robotics deployment programs -> sensing/actuation demand -> precision component bottlenecks",
    "longevity": "GLP-1 and advanced therapy demand -> drug delivery/API scale-up -> healthcare logistics capacity",
}

_PEER_GROUPS_BY_TICKER = {
    # AI infra
    "MSFT": "hyperscaler_capex",
    "GOOGL": "hyperscaler_capex",
    "AMZN": "hyperscaler_capex",
    "META": "hyperscaler_capex",
    "NVDA": "ai_accelerator_platform",
    "AVGO": "ai_networking_asic",
    "SMH": "semiconductor_etf",
    "XSD": "semiconductor_etf",
    "6702.T": "server_integrator",
    "MU": "hbm_memory",
    "6503.T": "power_semiconductor_cooling",
    "VST": "ai_power_generation",
    "CEG": "ai_power_generation",
    "XLU": "power_infrastructure_etf",
    "NLR": "nuclear_power_etf",
    "POWR": "power_infrastructure_etf",
    "6501.T": "grid_hardware",
    "9501.T": "electric_utility",
    # Tech localization
    "TSM": "foundry_localization",
    "INTC": "foundry_localization",
    "ASML": "lithography_equipment",
    "LRCX": "wafer_fab_equipment",
    "AMAT": "wafer_fab_equipment",
    "6146.T": "precision_wafer_processing",
    "8035.T": "wafer_fab_equipment",
    "6857.T": "semiconductor_test_equipment",
    "PLD": "industrial_real_estate",
    "XLI": "industrial_etf",
    "6506.T": "factory_automation",
    "6273.T": "factory_automation",
    # Physical AI
    "TSLA": "robotics_capex",
    "ROBO": "robotics_etf",
    "BOTZ": "robotics_etf",
    "6594.T": "robotics_motors",
    "6324.T": "robotics_precision_gears",
    "6861.T": "machine_vision_sensors",
    "ARKQ": "autonomous_technology_etf",
    "9020.T": "robotics_logistics_deployment",
    # Longevity
    "LLY": "glp1_therapy_leader",
    "NVO": "glp1_therapy_leader",
    "WST": "drug_delivery_components",
    "4568.T": "advanced_pharma_manufacturing",
    "4519.T": "advanced_pharma_manufacturing",
    "CAH": "pharma_distribution",
    "MCK": "pharma_distribution",
    "9021.T": "clinical_cold_chain_logistics",
}


def _attach_peer_metadata() -> None:
    for value_chain_id, companies in SEED_NODES.items():
        causal_edge = _RIVER_CAUSAL_EDGES.get(value_chain_id, "")
        for company in companies:
            company.setdefault("peer_group", _PEER_GROUPS_BY_TICKER.get(company["ticker"], company["stage"]))
            company.setdefault("causal_edge", causal_edge)
            company.setdefault(
                "behind_reason",
                "Compare against this peer group to separate delayed re-rating from structural weakness.",
            )


_attach_peer_metadata()
