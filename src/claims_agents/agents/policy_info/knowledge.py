"""Base de conhecimento (data/knowledge/faq.yaml) e regras de tópicos (configs/policy_info.yaml)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from claims_agents.core.settings import PROJECT_ROOT

PERSONAL_RE = re.compile(r"(?i)\b(minha|meu|minhas|meus|eu\s+tenho|tenho|meu\s+seguro)\b")
# perguntas hipotéticas ("se eu emprestar o carro...") não recebem resposta automática de cobertura
HYPOTHETICAL_RE = re.compile(r"(?i)(^\s*(e\s+)?se\s+|\bse\s+(eu|ele|ela|meu|minha|algu[eé]m)\b)")


@dataclass(frozen=True)
class FaqEntry:
    id: str
    title: str
    patterns: tuple[re.Pattern[str], ...]
    answer: str


class PolicyKnowledge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.topics: dict[str, list[re.Pattern[str]]] = {
            str(topic): [re.compile(p) for p in patterns]
            for topic, patterns in (config.get("topics") or {}).items()
        }
        self.coverage_keywords: dict[str, re.Pattern[str]] = {
            str(cov): re.compile(p) for cov, p in (config.get("coverage_keywords") or {}).items()
        }
        path = PROJECT_ROOT / str(config.get("knowledge_base", "data/knowledge/faq.yaml"))
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.faq = [
            FaqEntry(
                id=e["id"],
                title=e["title"],
                patterns=tuple(re.compile(p) for p in e.get("patterns", [])),
                answer=e["answer"],
            )
            for e in data.get("entries", [])
        ]

    def match_faq(self, text: str) -> FaqEntry | None:
        return next((e for e in self.faq if any(p.search(text) for p in e.patterns)), None)

    def match_topic(self, text: str) -> str | None:
        for topic, patterns in self.topics.items():
            if any(p.search(text) for p in patterns):
                return topic
        return None

    def coverage_asked(self, text: str) -> str | None:
        return next((c for c, p in self.coverage_keywords.items() if p.search(text)), None)

    def classify(self, text: str) -> tuple[str | None, str | None]:
        """(tópico, id da FAQ). Perguntas pessoais ("minha apólice...") priorizam a apólice."""
        personal = bool(PERSONAL_RE.search(text))
        topic, faq = self.match_topic(text), self.match_faq(text)
        if HYPOTHETICAL_RE.search(text) and topic == "coberturas":
            return None, None  # resposta livre (LLM restrito à base) ou orientação ao corretor
        if personal and topic:
            return topic, None
        if faq:
            return "faq", faq.id
        return topic, None

    def kb_context(self) -> str:
        return "\n".join(f"- {e.title}: {e.answer}" for e in self.faq)
