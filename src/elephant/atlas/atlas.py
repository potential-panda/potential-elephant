from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

STAGES = ["driver", "prime", "bottleneck", "capacity"]
VALID_COMPANY_STATUSES = {"proposed", "active", "weak", "watch", "dormant", "rejected"}
STAGE_LABELS = {
    "driver": "Driver (Capital & Architecture)",
    "prime": "Prime (Primary Engine)",
    "bottleneck": "Bottleneck (Highest Alpha)",
    "capacity": "Capacity (Real-World Constraints)",
}

# Seed data for `atlas init` — the 4 value_chains from the framework document
FRAMEWORK_VALUE_CHAINS = [
    {
        "id": "ai_infra",
        "name": "AI Infrastructure Supercycle",
        "description": "Hyperscaler CapEx & LLM expansion → compute/storage bottlenecks → power infrastructure",
    },
    {
        "id": "tech_local",
        "name": "Tech Localization & Onshoring",
        "description": "Geopolitical fragmentation, subsidies & tariff mandates → precision tools / foundries → industrial RE & automation",
    },
    {
        "id": "physical_ai",
        "name": "Embodied Physical AI",
        "description": "Edge AI models & automated logistics demand → actuators / gears / vision sensors → fleet fulfillment & smart manufacturing",
    },
    {
        "id": "longevity",
        "name": "Demographic Longevity",
        "description": "Clinical approvals & GLP-1 consumer demand → APIs / auto-injectors / specialized glass → cold-chain logistics & healthcare providers",
    },
]


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    date: str


@dataclass
class Company:
    ticker: str
    stage: str
    name: str = ""
    market: str = "US"
    role: str = ""
    notes: str = ""
    added: str = ""
    source: str = "manual"  # "manual" | "discovery"
    status: str = "active"
    thesis: str = ""
    counterarguments: str = ""
    confidence: str = "medium"
    last_reviewed: str = ""
    next_review_cadence: str = "weekly"
    what_would_change_our_mind: str = ""
    last_human_decision: str = ""
    last_human_decision_date: str = ""
    evidence_refs: list = field(default_factory=list)
    primary_value_chain: bool = True
    peer_group: str = ""
    causal_edge: str = ""
    behind_reason: str = ""
    competitor_tickers: list[str] = field(default_factory=list)
    leader_tickers: list[str] = field(default_factory=list)


@dataclass
class ValueChain:
    id: str
    name: str
    description: str = ""
    status: str = "active"
    companies: list[Company] = field(default_factory=list)


class Atlas:
    def __init__(self, path: str):
        self.path = path
        self._value_chains: dict[str, ValueChain] = {}
        self._news: dict[str, list[NewsItem]] = {}
        self._load()

    # --- Value Chains ---

    def add_value_chain(self, id: str, name: str, description: str = "") -> ValueChain:
        if id in self._value_chains:
            raise ValueError(f"Value Chain '{id}' already exists")
        value_chain = ValueChain(id=id, name=name, description=description)
        self._value_chains[id] = value_chain
        self.save()
        return value_chain

    def remove_value_chain(self, value_chain_id: str) -> bool:
        if value_chain_id not in self._value_chains:
            return False
        del self._value_chains[value_chain_id]
        self.save()
        return True

    def get_value_chain(self, value_chain_id: str) -> Optional[ValueChain]:
        return self._value_chains.get(value_chain_id)

    def list_value_chains(self) -> list[ValueChain]:
        return list(self._value_chains.values())

    # --- Companies ---

    def add_company(
        self,
        value_chain_id: str,
        ticker: str,
        stage: str,
        name: str = "",
        market: str = "US",
        role: str = "",
        notes: str = "",
        source: str = "manual",
        peer_group: str = "",
        causal_edge: str = "",
        behind_reason: str = "",
        competitor_tickers: list[str] | None = None,
        leader_tickers: list[str] | None = None,
    ) -> Company:
        value_chain = self._value_chains.get(value_chain_id)
        if not value_chain:
            raise ValueError(f"Value Chain '{value_chain_id}' not found")
        stage = _normalize_stage(stage)
        if stage not in STAGES:
            raise ValueError(f"Stage must be one of {STAGES}")
        if any(company.ticker == ticker for company in value_chain.companies):
            raise ValueError(f"Ticker '{ticker}' already in value_chain '{value_chain_id}'")
        company = Company(
            ticker=ticker,
            stage=stage,
            name=name,
            market=market,
            role=role,
            notes=notes,
            added=datetime.now().strftime("%Y-%m-%d"),
            source=source,
            peer_group=peer_group,
            causal_edge=causal_edge,
            behind_reason=behind_reason,
            competitor_tickers=competitor_tickers or [],
            leader_tickers=leader_tickers or [],
        )
        value_chain.companies.append(company)
        self.save()
        return company

    def update_company(self, value_chain_id: str, ticker: str, **kwargs) -> bool:
        if "stage" in kwargs:
            kwargs["stage"] = _normalize_stage(kwargs["stage"])
        if "status" in kwargs and kwargs["status"] not in VALID_COMPANY_STATUSES:
            raise ValueError(f"status must be one of {VALID_COMPANY_STATUSES}")
        value_chain = self._value_chains.get(value_chain_id)
        if not value_chain:
            return False
        for company in value_chain.companies:
            if company.ticker == ticker:
                for k, v in kwargs.items():
                    if hasattr(company, k):
                        setattr(company, k, v)
                self.save()
                return True
        return False

    def remove_company(self, value_chain_id: str, ticker: str) -> bool:
        value_chain = self._value_chains.get(value_chain_id)
        if not value_chain:
            return False
        before = len(value_chain.companies)
        value_chain.companies = [company for company in value_chain.companies if company.ticker != ticker]
        if len(value_chain.companies) < before:
            self.save()
            return True
        return False

    def find_ticker(self, ticker: str) -> list[tuple[ValueChain, Company]]:
        """Return all (value_chain, company) pairs for a given ticker across all value_chains."""
        return [
            (value_chain, company)
            for value_chain in self._value_chains.values()
            for company in value_chain.companies
            if company.ticker == ticker
        ]

    # --- News ---

    def add_news(self, ticker: str, title: str, url: str, source: str, date: str = None) -> None:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        item = NewsItem(title=title, url=url, source=source, date=date)
        if ticker not in self._news:
            self._news[ticker] = []
        if not any(n.url == url for n in self._news[ticker]):
            self._news[ticker].insert(0, item)
            self._news[ticker] = self._news[ticker][:20]  # keep latest 20
            self.save()

    def get_news(self, ticker: str) -> list[NewsItem]:
        return self._news.get(ticker, [])

    # --- Persistence ---

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            raw_value_chains = data.get("value_chains", data.get("rivers", []))
            for value_chain_data in raw_value_chains:
                companies = [
                    Company(
                        ticker=company_data["ticker"],
                        stage=_normalize_stage(company_data.get("stage", company_data.get("layer", ""))),
                        name=company_data.get("name", ""),
                        market=company_data.get("market", "US"),
                        role=company_data.get("role", ""),
                        notes=company_data.get("notes", ""),
                        added=company_data.get("added", ""),
                        source=company_data.get("source", "manual"),
                        status=company_data.get("status", "active"),
                        thesis=company_data.get("thesis", ""),
                        counterarguments=company_data.get("counterarguments", ""),
                        confidence=company_data.get("confidence", "medium"),
                        last_reviewed=company_data.get("last_reviewed", ""),
                        next_review_cadence=company_data.get("next_review_cadence", "weekly"),
                        what_would_change_our_mind=company_data.get("what_would_change_our_mind", ""),
                        last_human_decision=company_data.get("last_human_decision", ""),
                        last_human_decision_date=company_data.get("last_human_decision_date", ""),
                        evidence_refs=company_data.get("evidence_refs", []),
                        primary_value_chain=company_data.get("primary_value_chain", company_data.get("primary_river", True)),
                        peer_group=company_data.get("peer_group", ""),
                        causal_edge=company_data.get("causal_edge", ""),
                        behind_reason=company_data.get("behind_reason", ""),
                        competitor_tickers=company_data.get("competitor_tickers", []),
                        leader_tickers=company_data.get("leader_tickers", []),
                    )
                    for company_data in value_chain_data.get("companies", value_chain_data.get("nodes", []))
                ]
                value_chain = ValueChain(
                    id=value_chain_data["id"],
                    name=value_chain_data["name"],
                    description=value_chain_data.get("description", ""),
                    status=value_chain_data.get("status", "active"),
                    companies=companies,
                )
                self._value_chains[value_chain.id] = value_chain
            for ticker, items in data.get("news", {}).items():
                self._news[ticker] = [NewsItem(**item) for item in items]
        except Exception as e:
            print(f"Warning: failed to load atlas from {self.path}: {e}")

    def save(self) -> None:
        dirpath = os.path.dirname(self.path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        data = {
            "version": 2,
            "value_chains": [
                {
                    "id": value_chain.id,
                    "name": value_chain.name,
                    "description": value_chain.description,
                    "status": value_chain.status,
                    "companies": [asdict(company) for company in value_chain.companies],
                }
                for value_chain in self._value_chains.values()
            ],
            "news": {
                ticker: [asdict(item) for item in items]
                for ticker, items in self._news.items()
            },
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- Display ---

    def to_display(self, value_chain_id: str = None) -> str:
        value_chains = (
            [self._value_chains[value_chain_id]]
            if value_chain_id and value_chain_id in self._value_chains
            else self._value_chains.values()
        )
        lines = []
        for value_chain in value_chains:
            lines.append(f"\n[{value_chain.id}] {value_chain.name}")
            if value_chain.description:
                lines.append(f"    {value_chain.description}")

            by_stage: dict[str, list[Company]] = {stage: [] for stage in STAGES}
            for company in value_chain.companies:
                if company.stage in by_stage:
                    by_stage[company.stage].append(company)

            for stage in STAGES:
                companies = by_stage[stage]
                label = STAGE_LABELS[stage]
                if companies:
                    lines.append(f"  [{stage.upper()}] {label}")
                    for company in companies:
                        mkt = f" ({company.market})" if company.market else ""
                        nm = f" — {company.name}" if company.name else ""
                        lines.append(f"    * {company.ticker}{mkt}{nm}")
                        if company.role:
                            lines.append(f"      {company.role}")
                        if company.notes:
                            lines.append(f"      note: {company.notes}")
                        if company.peer_group:
                            lines.append(f"      peer group: {company.peer_group}")
                        if company.causal_edge:
                            lines.append(f"      edge: {company.causal_edge}")
                else:
                    lines.append(f"  [{stage.upper()}] {label}  (empty)")

        if not lines:
            lines.append("(no value_chains yet — run `python src/cli.py atlas init`)")
        return "\n".join(lines)


def _normalize_stage(stage: str) -> str:
    return {
        "source": "driver",
        "upper": "prime",
        "middle": "bottleneck",
        "lower": "capacity",
    }.get(str(stage or "").strip(), str(stage or "").strip())
