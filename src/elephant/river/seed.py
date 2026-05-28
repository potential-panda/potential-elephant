# Initial ticker universe from the Macro Rivers Tracking & Detailed Tickers Matrix (V1)
# Source: user's Google Doc (1JZ6gh_BVbed4eebauaUuvZw5Qq8AtjTMH0hucFJcUQA)
#
# Layer split rationale (doc uses combined "Upper/Middle Stream"):
#   upper  — core designers, foundational ETFs, large-cap primary engines
#   middle — specialized bottleneck components, highest-alpha niche JP names

SEED_NODES: dict[str, list[dict]] = {
    "ai_infra": [
        # Source
        {"ticker": "MSFT",   "layer": "source", "market": "US", "name": "Microsoft",       "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "GOOGL",  "layer": "source", "market": "US", "name": "Alphabet",        "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "AMZN",   "layer": "source", "market": "US", "name": "Amazon",          "role": "Primary hyperscaler capital deployer for AI CapEx"},
        {"ticker": "META",   "layer": "source", "market": "US", "name": "Meta Platforms",  "role": "Primary hyperscaler capital deployer for AI CapEx"},
        # Upper stream — core compute designers and broad ETFs
        {"ticker": "NVDA",   "layer": "upper",  "market": "US", "name": "NVIDIA",          "role": "GPU designer and dominant AI compute platform"},
        {"ticker": "AVGO",   "layer": "upper",  "market": "US", "name": "Broadcom",        "role": "AI networking chips and custom ASICs for hyperscalers"},
        {"ticker": "SMH",    "layer": "upper",  "market": "US", "name": "VanEck Semiconductor ETF",        "role": "Broad semiconductor ETF — US lead-lag indicator for JP suppliers"},
        {"ticker": "XSD",    "layer": "upper",  "market": "US", "name": "SPDR S&P Semiconductor ETF",     "role": "Broad semiconductor ETF — US lead-lag indicator for JP suppliers"},
        {"ticker": "6702.T", "layer": "upper",  "market": "JP", "name": "Fujitsu",         "role": "Server hardware and advanced compute node integration"},
        # Middle stream — physical bottlenecks (memory, power semiconductors)
        {"ticker": "MU",     "layer": "middle", "market": "US", "name": "Micron Technology",          "role": "DRAM and HBM memory — key AI compute bottleneck"},
        {"ticker": "6503.T", "layer": "middle", "market": "JP", "name": "Mitsubishi Electric",        "role": "Power semiconductor components and industrial liquid cooling"},
        # Lower stream — power and grid infrastructure
        {"ticker": "VST",    "layer": "lower",  "market": "US", "name": "Vistra Corp",                "role": "Independent power producer serving AI data center load"},
        {"ticker": "CEG",    "layer": "lower",  "market": "US", "name": "Constellation Energy",       "role": "Nuclear baseload for AI infrastructure power demand"},
        {"ticker": "XLU",    "layer": "lower",  "market": "US", "name": "Utilities Select Sector SPDR", "role": "Broad utilities ETF covering grid capacity plays"},
        {"ticker": "NLR",    "layer": "lower",  "market": "US", "name": "VanEck Nuclear Energy ETF",  "role": "Nuclear energy ETF"},
        {"ticker": "POWR",   "layer": "lower",  "market": "US", "name": "US Power Infrastructure ETF", "role": "Power infrastructure ETF"},
        {"ticker": "6501.T", "layer": "lower",  "market": "JP", "name": "Hitachi",                   "role": "Grid hardware and industrial power transformers"},
        {"ticker": "9501.T", "layer": "lower",  "market": "JP", "name": "Tokyo Electric Power (TEPCO)", "role": "Local electricity infrastructure provision"},
    ],

    "tech_local": [
        # Source
        {"ticker": "TSM",    "layer": "source", "market": "US", "name": "Taiwan Semiconductor", "role": "Epicenter of global fabrication localization transition"},
        {"ticker": "INTC",   "layer": "source", "market": "US", "name": "Intel",               "role": "US domestic chip manufacturing push"},
        # Upper stream — lithography and manufacturing equipment
        {"ticker": "ASML",   "layer": "upper",  "market": "US", "name": "ASML Holding",        "role": "Semiconductor lithography — monopoly on EUV equipment"},
        {"ticker": "LRCX",   "layer": "upper",  "market": "US", "name": "Lam Research",        "role": "Semiconductor etch and deposition equipment"},
        {"ticker": "AMAT",   "layer": "upper",  "market": "US", "name": "Applied Materials",   "role": "Semiconductor manufacturing equipment"},
        # Middle stream — ultra-precision JP bottlenecks
        {"ticker": "6146.T", "layer": "middle", "market": "JP", "name": "Disco Corp",          "role": "Ultra-precision semiconductor dicing and grinding tools"},
        {"ticker": "8035.T", "layer": "middle", "market": "JP", "name": "Tokyo Electron",      "role": "Semiconductor etching and coating systems"},
        {"ticker": "6857.T", "layer": "middle", "market": "JP", "name": "Advantest",           "role": "Specialized chip testing hardware"},
        # Lower stream — industrial RE and automation
        {"ticker": "PLD",    "layer": "lower",  "market": "US", "name": "Prologis",            "role": "Heavy industrial real estate for onshored production"},
        {"ticker": "XLI",    "layer": "lower",  "market": "US", "name": "Industrials Select Sector SPDR", "role": "Broad industrials ETF"},
        {"ticker": "6506.T", "layer": "lower",  "market": "JP", "name": "Yaskawa Electric",   "role": "Industrial assembly line robotics"},
        {"ticker": "6273.T", "layer": "lower",  "market": "JP", "name": "SMC Corp",           "role": "Pneumatic automation factory floor inputs"},
    ],

    "physical_ai": [
        # Source
        {"ticker": "TSLA",   "layer": "source", "market": "US", "name": "Tesla",              "role": "Optimus humanoid robot program — primary capital deployer"},
        {"ticker": "AMZN",   "layer": "source", "market": "US", "name": "Amazon",             "role": "Fulfillment robotics deployment and automation policy"},
        # Upper stream — broad robotics ETFs
        {"ticker": "ROBO",   "layer": "upper",  "market": "US", "name": "ROBO Global Robotics ETF",       "role": "Broad robotics and automation ETF"},
        {"ticker": "BOTZ",   "layer": "upper",  "market": "US", "name": "Global X Robotics ETF",          "role": "Broad robotics and AI ETF"},
        # Middle stream — precision component bottlenecks
        {"ticker": "6594.T", "layer": "middle", "market": "JP", "name": "Nidec",              "role": "High-efficiency precision miniature motors for robotics"},
        {"ticker": "6324.T", "layer": "middle", "market": "JP", "name": "Harmonic Drive Systems", "role": "Strain wave gears for robotic joints — key bottleneck"},
        {"ticker": "6861.T", "layer": "middle", "market": "JP", "name": "Keyence",            "role": "High-precision vision sensors and inspection systems"},
        # Lower stream — deployment and logistics
        {"ticker": "ARKQ",   "layer": "lower",  "market": "US", "name": "ARK Autonomous Technology ETF",  "role": "Autonomous technology and robotics ETF"},
        {"ticker": "6273.T", "layer": "lower",  "market": "JP", "name": "SMC Corp",           "role": "Heavy floor grid automation inputs"},
        {"ticker": "9020.T", "layer": "lower",  "market": "JP", "name": "East Japan Railway", "role": "Rail logistics connectivity for autonomous deployment"},
    ],

    "longevity": [
        # Source
        {"ticker": "LLY",    "layer": "source", "market": "US", "name": "Eli Lilly",          "role": "GLP-1 and metabolic therapy leader — primary capital deployer"},
        {"ticker": "NVO",    "layer": "source", "market": "US", "name": "Novo Nordisk",       "role": "GLP-1 and metabolic therapy leader — primary capital deployer"},
        # Upper stream — drug delivery components
        {"ticker": "WST",    "layer": "upper",  "market": "US", "name": "West Pharmaceutical Services", "role": "Specialized drug containment and syringe mechanics"},
        # Middle stream — API and biologics bottlenecks
        {"ticker": "4568.T", "layer": "middle", "market": "JP", "name": "Daiichi Sankyo",     "role": "Advanced API synthesis and macromolecule processing"},
        {"ticker": "4519.T", "layer": "middle", "market": "JP", "name": "Chugai Pharmaceutical", "role": "Specialized antibody-based product tracks"},
        # Lower stream — pharmaceutical logistics
        {"ticker": "CAH",    "layer": "lower",  "market": "US", "name": "Cardinal Health",    "role": "Large-scale pharmaceutical supply chain management"},
        {"ticker": "MCK",    "layer": "lower",  "market": "US", "name": "McKesson Corp",      "role": "Large-scale pharmaceutical supply chain management"},
        {"ticker": "9021.T", "layer": "lower",  "market": "JP", "name": "West Japan Railway", "role": "Specialized clinical cargo routes"},
    ],
}
