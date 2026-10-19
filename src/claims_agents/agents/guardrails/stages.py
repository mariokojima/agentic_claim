"""Estágios de guardrail (segurança, ética, corporativo).

Fase 2: regras determinísticas configuráveis (`rules.py`). Os classificadores LLM (Fase 6)
entram aqui, executando apenas quando nenhuma regra determinística decidiu `block`.
"""

from __future__ import annotations

from datetime import date
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
    context_rules: dict[str, Any] = (
        config.get("stages", {}).get(stage, {}).get("context_rules") or {}
    )

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
        context_check = _context_rules(context_rules, state.context)
        if context_check is not None and not hits:
            return {stage: context_check.model_copy(update={"stage": stage})}
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


def _context_rules(rules: dict[str, Any], context: dict[str, Any]) -> GuardrailCheck | None:
    """Regras que dependem do contexto do segurado (ex.: apólice muito recente)."""
    late = rules.get("late_notice") or {}
    event_date, today = context.get("event_date"), context.get("today")
    if late.get("enabled", False) and event_date and today:
        delay = (date.fromisoformat(str(today)) - date.fromisoformat(str(event_date))).days
        if delay > int(late.get("max_days", 30)):
            return GuardrailCheck(
                stage="corporate",
                decision=late.get("action", "escalate"),
                reason=f"[late_notice] {late.get('reason', '')} ({delay} dias)",
                rule="late_notice",
            )
    recent = rules.get("recent_policy") or {}
    start, event = context.get("policy_start_date"), context.get("event_date")
    if recent.get("enabled", False) and start and event:
        days = (date.fromisoformat(str(event)) - date.fromisoformat(str(start))).days
        if 0 <= days <= int(recent.get("max_days", 7)):
            return GuardrailCheck(
                stage="corporate",
                decision=recent.get("action", "escalate"),
                reason=f"[recent_policy] {recent.get('reason', '')} ({days} dia(s))",
                rule="recent_policy",
            )
    return None
