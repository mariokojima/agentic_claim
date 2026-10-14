"""Classificação determinística do ocorrido por palavras-chave (configs/triage_rules.yaml)."""

from __future__ import annotations

import re
from typing import Any

from claims_agents.agents.triage.subagents.event_classification.schemas import EventClassification


class EventClassifier:
    def __init__(self, rules: dict[str, Any]) -> None:
        cfg = rules["event_classification"]
        self.priority: list[str] = list(cfg["priority"])
        self.labels: dict[str, str] = dict(cfg.get("labels", {}))
        self.patterns = {
            category: [re.compile(p) for p in cfg["patterns"].get(category, [])]
            for category in self.priority
        }
        self.injuries = [re.compile(p) for p in cfg.get("injuries_patterns", [])]

    def classify(self, text: str) -> EventClassification:
        has_injuries = any(p.search(text) for p in self.injuries)
        for category in self.priority:
            for pattern in self.patterns[category]:
                if match := pattern.search(text):
                    return EventClassification(
                        event_type=category,
                        label=self.labels.get(category, category),
                        matched=match.group(0),
                        has_injuries=has_injuries,
                    )
        return EventClassification(event_type=None, has_injuries=has_injuries)
