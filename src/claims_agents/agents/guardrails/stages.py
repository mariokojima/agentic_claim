"""Fábrica dos estágios de guardrail. Na Fase 1 são stubs que sempre permitem.

As regras determinísticas (Fase 2) e os classificadores LLM (Fase 6) entram em
`security.py`, `ethics.py` e `corporate.py`, mantendo esta assinatura de nó.
"""

from __future__ import annotations

from typing import Any, Literal

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

    def node(state: GuardrailGraphState) -> dict[str, Any]:
        reason = "Nenhuma regra disparou" if enabled else "Estágio desativado por configuração"
        return {stage: GuardrailCheck(stage=stage, decision="allow", reason=reason)}

    node.__name__ = stage
    return node
