"""Detecção determinística de terceiros e feridos (configs/triage_rules.yaml → parties)."""

from __future__ import annotations

import re
from typing import Any

from claims_agents.agents.triage.subagents.parties.schemas import PartiesExtraction

YES_RE = re.compile(r"(?i)^\s*(sim|s|houve|havia|tinha|teve|positivo|isso)\b")
NO_RE = re.compile(r"(?i)^\s*(n[aã]o|n|nenhum[a]?|negativo|ningu[eé]m)\b")


class PartiesDetector:
    def __init__(self, rules: dict[str, Any]) -> None:
        cfg = rules["parties"]
        self.no_third = [re.compile(p) for p in cfg.get("no_third_parties_patterns", [])]
        self.third = [re.compile(p) for p in cfg.get("third_parties_patterns", [])]
        self.no_injuries = [re.compile(p) for p in cfg.get("no_injuries_patterns", [])]
        self.injuries = [re.compile(p) for p in cfg.get("injuries_patterns", [])]

    def detect(self, text: str) -> PartiesExtraction:
        """Extrai do relato livre (negativas antes das positivas)."""
        return PartiesExtraction(
            has_third_parties=_tri(text, self.no_third, self.third),
            has_injuries=_tri(text, self.no_injuries, self.injuries),
        )

    def from_answer(self, text: str, asked: list[str]) -> PartiesExtraction:
        """Interpreta a resposta à pergunta feita (`asked` ⊂ {third_parties, injuries})."""
        found = self.detect(text)
        values = found.model_dump()
        unknown = [f for f in asked if values[f"has_{f}"] is None]
        if unknown and NO_RE.match(text):
            # "não" curto responde às perguntas ainda não respondidas explicitamente
            for f in unknown:
                values[f"has_{f}"] = False
        elif len(unknown) == 1 and YES_RE.match(text):
            values[f"has_{unknown[0]}"] = True
        return PartiesExtraction.model_validate(values)


def _tri(
    text: str, negatives: list[re.Pattern[str]], positives: list[re.Pattern[str]]
) -> bool | None:
    if any(p.search(text) for p in negatives):
        return False
    if any(p.search(text) for p in positives):
        return True
    return None
