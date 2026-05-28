from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

LAYERS = ["source", "upper", "middle", "lower"]
LAYER_LABELS = {
    "source": "Source (Capital & Architecture)",
    "upper": "Upper Stream (Primary Engine)",
    "middle": "Middle Stream (Bottlenecks — highest alpha)",
    "lower": "Lower Stream (Capacity Constraints)",
}

# Seed data for `tree init` — the 4 rivers from the framework document
FRAMEWORK_RIVERS = [
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
class Node:
    ticker: str
    layer: str
    name: str = ""
    market: str = "US"
    role: str = ""
    notes: str = ""
    added: str = ""
    source: str = "manual"  # "manual" | "discovery"


@dataclass
class River:
    id: str
    name: str
    description: str = ""
    nodes: list[Node] = field(default_factory=list)


class RiverTree:
    def __init__(self, path: str):
        self.path = path
        self._rivers: dict[str, River] = {}
        self._news: dict[str, list[NewsItem]] = {}
        self._load()

    # --- Rivers ---

    def add_river(self, id: str, name: str, description: str = "") -> River:
        if id in self._rivers:
            raise ValueError(f"River '{id}' already exists")
        river = River(id=id, name=name, description=description)
        self._rivers[id] = river
        self.save()
        return river

    def remove_river(self, river_id: str) -> bool:
        if river_id not in self._rivers:
            return False
        del self._rivers[river_id]
        self.save()
        return True

    def get_river(self, river_id: str) -> Optional[River]:
        return self._rivers.get(river_id)

    def list_rivers(self) -> list[River]:
        return list(self._rivers.values())

    # --- Nodes ---

    def add_node(
        self,
        river_id: str,
        ticker: str,
        layer: str,
        name: str = "",
        market: str = "US",
        role: str = "",
        notes: str = "",
        source: str = "manual",
    ) -> Node:
        river = self._rivers.get(river_id)
        if not river:
            raise ValueError(f"River '{river_id}' not found")
        if layer not in LAYERS:
            raise ValueError(f"Layer must be one of {LAYERS}")
        if any(n.ticker == ticker for n in river.nodes):
            raise ValueError(f"Ticker '{ticker}' already in river '{river_id}'")
        node = Node(
            ticker=ticker,
            layer=layer,
            name=name,
            market=market,
            role=role,
            notes=notes,
            added=datetime.now().strftime("%Y-%m-%d"),
            source=source,
        )
        river.nodes.append(node)
        self.save()
        return node

    def update_node(self, river_id: str, ticker: str, **kwargs) -> bool:
        river = self._rivers.get(river_id)
        if not river:
            return False
        for node in river.nodes:
            if node.ticker == ticker:
                for k, v in kwargs.items():
                    if hasattr(node, k):
                        setattr(node, k, v)
                self.save()
                return True
        return False

    def remove_node(self, river_id: str, ticker: str) -> bool:
        river = self._rivers.get(river_id)
        if not river:
            return False
        before = len(river.nodes)
        river.nodes = [n for n in river.nodes if n.ticker != ticker]
        if len(river.nodes) < before:
            self.save()
            return True
        return False

    def find_ticker(self, ticker: str) -> list[tuple[River, Node]]:
        """Return all (river, node) pairs for a given ticker across all rivers."""
        return [
            (river, node)
            for river in self._rivers.values()
            for node in river.nodes
            if node.ticker == ticker
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
            for r in data.get("rivers", []):
                nodes = [Node(**n) for n in r.get("nodes", [])]
                river = River(id=r["id"], name=r["name"], description=r.get("description", ""), nodes=nodes)
                self._rivers[river.id] = river
            for ticker, items in data.get("news", {}).items():
                self._news[ticker] = [NewsItem(**item) for item in items]
        except Exception as e:
            print(f"Warning: failed to load river tree from {self.path}: {e}")

    def save(self) -> None:
        dirpath = os.path.dirname(self.path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        data = {
            "version": 1,
            "rivers": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "nodes": [asdict(n) for n in r.nodes],
                }
                for r in self._rivers.values()
            ],
            "news": {
                ticker: [asdict(item) for item in items]
                for ticker, items in self._news.items()
            },
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- Display ---

    def to_display(self, river_id: str = None) -> str:
        rivers = (
            [self._rivers[river_id]]
            if river_id and river_id in self._rivers
            else self._rivers.values()
        )
        lines = []
        for river in rivers:
            lines.append(f"\n[{river.id}] {river.name}")
            if river.description:
                lines.append(f"    {river.description}")

            by_layer: dict[str, list[Node]] = {layer: [] for layer in LAYERS}
            for node in river.nodes:
                if node.layer in by_layer:
                    by_layer[node.layer].append(node)

            for layer in LAYERS:
                nodes = by_layer[layer]
                label = LAYER_LABELS[layer]
                if nodes:
                    lines.append(f"  [{layer.upper()}] {label}")
                    for node in nodes:
                        mkt = f" ({node.market})" if node.market else ""
                        nm = f" — {node.name}" if node.name else ""
                        lines.append(f"    * {node.ticker}{mkt}{nm}")
                        if node.role:
                            lines.append(f"      {node.role}")
                        if node.notes:
                            lines.append(f"      note: {node.notes}")
                else:
                    lines.append(f"  [{layer.upper()}] {label}  (empty)")

        if not lines:
            lines.append("(no rivers yet — run `python src/cli.py tree init`)")
        return "\n".join(lines)
