"""Agregador de guardrails: precedência block > escalate > sanitize > allow.

Combina as checagens determinísticas dos três estágios e, quando elas não bloqueiam, as do
classificador LLM (se habilitado).
"""

from typing import Any, Literal

from claims_agents.agents.guardrails.llm_classifier import GuardrailLLMClassifier
from claims_agents.agents.guardrails.state import GuardrailGraphState
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import GuardrailCheck, GuardrailDecision, GuardrailVerdict

PRECEDENCE: list[GuardrailDecision] = ["block", "escalate", "sanitize", "allow"]


def aggregate(
    direction: Literal["input", "output"], text: str, checks: list[GuardrailCheck]
) -> GuardrailVerdict:
    decision: GuardrailDecision = min(
        (c.decision for c in checks), key=PRECEDENCE.index, default="allow"
    )
    decisive = [c for c in checks if c.decision == decision]
    final_text = text
    if decision == "sanitize":
        for c in decisive:
            final_text = c.sanitized_text or final_text
    reason = "; ".join(f"{c.stage}: {c.reason}" for c in decisive) or "Sem checagens"
    return GuardrailVerdict(
        direction=direction,
        decision=decision,
        reason=reason,
        checks=checks,
        text=final_text,
    )


def build_aggregator(
    classifier: GuardrailLLMClassifier | None = None,
) -> NodeFn[GuardrailGraphState]:
    async def aggregator(state: GuardrailGraphState) -> dict[str, Any]:
        checks = [c for c in (state.security, state.ethics, state.corporate) if c is not None]
        rules_verdict = aggregate(state.direction, state.text, checks)
        layers = ["regras"]
        # checagem de contexto ao fim da Triagem é só por regras (o texto já passou pela entrada)
        rechecking = bool(state.context.get("checkpoint"))
        if classifier is not None and rules_verdict.decision != "block" and not rechecking:
            scanned = state.text
            extra = state.context.get("attachments_text")
            if extra and state.direction == "input":
                scanned = f"{scanned}\n[anexos] {extra}"
            if classifier.applies(state.direction, scanned):
                checks = checks + await classifier.classify(state.direction, scanned)
                layers.append("llm")
        verdict = aggregate(state.direction, state.text, checks)
        emit(
            "guardrail_verdict",
            subagent="aggregator",
            status="completed" if verdict.decision == "allow" else "warning",
            details=f"{verdict.direction}: {verdict.decision} — {verdict.reason}",
            data={
                "direction": verdict.direction,
                "decision": verdict.decision,
                "layers": layers,
                "checks": [c.model_dump() for c in checks],
            },
        )
        return {"verdict": verdict}

    return aggregator


# compatibilidade: agregador só com regras
aggregator = build_aggregator()
