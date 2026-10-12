"""Motor de regras determinísticas dos guardrails (configs/guardrails.yaml)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from claims_agents.core.privacy import mask_cpf
from claims_agents.state import GuardrailDecision

Direction = Literal["input", "output"]
PRECEDENCE: list[GuardrailDecision] = ["block", "escalate", "sanitize", "allow"]


@dataclass(frozen=True)
class Rule:
    name: str
    action: GuardrailDecision
    reason: str
    patterns: tuple[re.Pattern[str], ...]
    show_match: bool = True
    mask: str | None = None


@dataclass(frozen=True)
class RuleHit:
    rule: Rule
    match: str


def load_rules(config: dict[str, Any], stage: str, direction: Direction) -> list[Rule]:
    """Regras ativas de um estágio/direção. Estágio ou guardrails desligados → nenhuma regra."""
    stage_cfg = config.get("stages", {}).get(stage, {})
    if not config.get("enabled", True) or not stage_cfg.get("enabled", True):
        return []
    rules_cfg: dict[str, Any] = (stage_cfg.get(direction) or {}).get("rules") or {}
    rules: list[Rule] = []
    for name, cfg in rules_cfg.items():
        if not cfg.get("enabled", True):
            continue
        rules.append(
            Rule(
                name=name,
                action=cfg.get("action", "block"),
                reason=cfg.get("reason", name),
                patterns=tuple(re.compile(p) for p in cfg.get("patterns", [])),
                show_match=cfg.get("show_match", True),
                mask=cfg.get("mask"),
            )
        )
    return rules


def evaluate(rules: list[Rule], text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for rule in rules:
        for pattern in rule.patterns:
            match = pattern.search(text)
            if match:
                hits.append(RuleHit(rule=rule, match=match.group(0)))
                break
    return hits


def strongest(hits: list[RuleHit]) -> GuardrailDecision:
    return min((h.rule.action for h in hits), key=PRECEDENCE.index, default="allow")


def sanitize(text: str, hits: list[RuleHit]) -> str:
    """Aplica as máscaras das regras `sanitize` que dispararam."""
    for hit in hits:
        if hit.rule.action != "sanitize":
            continue
        replacer = _replacer(hit.rule.mask)
        for pattern in hit.rule.patterns:
            text = pattern.sub(replacer, text)
    return text


def describe(hits: list[RuleHit]) -> str:
    parts = []
    for hit in hits:
        snippet = f' (trecho: "{hit.match}")' if hit.rule.show_match else ""
        parts.append(f"[{hit.rule.name}] {hit.rule.reason}{snippet}")
    return "; ".join(parts)


def _replacer(mask: str | None) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        return mask_cpf(match.group(0)) if mask == "cpf" else "[removido]"

    return replace
