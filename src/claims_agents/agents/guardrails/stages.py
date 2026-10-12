"""Estágios de guardrail (segurança, ética, corporativo).

Fase 2: regras determinísticas configuráveis (`rules.py`). Os classificadores LLM (Fase 6)
entram aqui, executando apenas quando nenhuma regra determinística decidiu `block`.
"""

from __future__ import annotations

from typing import Any, Literal

from claims_agents.agents.guardrails.rules import (
    describe,
    evaluate,
    load_rules,
    sanitize,
    strongest,
)
from claims_agents.agents.guardrails.state import GuardrailGraphState
from claims_agents.core.types import NodeFn
from claims_agents.state import GuardrailCheck

StageName = Literal["security", "ethics", "corporate"]


def stage_enabled(config: dict[str, Any], stage: StageName) -> bool:
    return bool(config.get("enabled", True)) and bool(
        config.get("stages", {}).get(stage, {}).get("enabled", True)
    )


def build_stage(stage: StageName, config: dict[str, Any]) -> NodeFn[GuardrailGraphState]:
    enabled = stage_enabled(config, stage)
    rules = {d: load_rules(config, stage, d) for d in ("input", "output")}

    def node(state: GuardrailGraphState) -> dict[str, Any]:
        if not enabled:
            check = GuardrailCheck(
                stage=stage, decision="allow", reason="Estágio desativado por configuração"
            )
            return {stage: check}
        text = state.text
        extra = state.context.get("attachments_text")  # injeção embutida em anexos
        scanned = f"{text}\n{extra}" if extra and state.direction == "input" else text
        hits = evaluate(rules[state.direction], scanned)
        if not hits:
            return {
                stage: GuardrailCheck(
                    stage=stage, decision="allow", reason="Nenhuma regra disparou"
                )
            }
        decision = strongest(hits)
        return {
            stage: GuardrailCheck(
                stage=stage,
                decision=decision,
                reason=describe(hits),
                rule=",".join(h.rule.name for h in hits),
                sanitized_text=sanitize(text, hits) if decision == "sanitize" else None,
            )
        }

    node.__name__ = stage
    return node
