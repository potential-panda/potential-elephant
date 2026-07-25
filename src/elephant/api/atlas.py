from elephant.config import ATLAS_PATH


def get_atlas() -> dict:
    from elephant.atlas.atlas import STAGES, Atlas
    atlas = Atlas(ATLAS_PATH)
    value_chains = []
    for value_chain in atlas.list_value_chains():
        companies = []
        for company in value_chain.companies:
            companies.append({
                "ticker": company.ticker,
                "stage": company.stage,
                "name": company.name,
                "market": company.market,
                "role": company.role,
                "notes": getattr(company, "notes", ""),
                "added": company.added,
                "source": getattr(company, "source", "manual"),
                # lifecycle fields
                "status": company.status,
                "thesis": company.thesis,
                "counterarguments": company.counterarguments,
                "confidence": company.confidence,
                "last_reviewed": company.last_reviewed,
                "next_review_cadence": company.next_review_cadence,
                "what_would_change_our_mind": company.what_would_change_our_mind,
                "last_human_decision": company.last_human_decision,
                "last_human_decision_date": company.last_human_decision_date,
                "evidence_refs": company.evidence_refs,
                "primary_value_chain": company.primary_value_chain,
                "peer_group": company.peer_group,
                "causal_edge": company.causal_edge,
                "behind_reason": company.behind_reason,
                "competitor_tickers": company.competitor_tickers,
                "leader_tickers": company.leader_tickers,
            })
        value_chains.append({
            "id": value_chain.id,
            "name": value_chain.name,
            "description": getattr(value_chain, "description", ""),
            "status": getattr(value_chain, "status", "active"),
            "companies": companies,
        })
    return {"value_chains": value_chains, "stages": STAGES, "file": ATLAS_PATH}
