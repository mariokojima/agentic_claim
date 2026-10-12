"""Agregador de guardrails: precedência block > escalate > sanitize > allow."""

from typing import Any, Literal

from claims_agents.agents.guardrails.state import GuardrailGraphState
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


def aggregator(state: GuardrailGraphState) -> dict[str, Any]:
    checks = [c for c in (state.security, state.ethics, state.corporate) if c is not None]
    verdict = aggregate(state.direction, state.text, checks)
    emit(
        "guardrail_verdict",
        subagent="aggregator",
        status="completed" if verdict.decision == "allow" else "warning",
        details=f"{verdict.direction}: {verdict.decision} — {verdict.reason}",
        data={
            "direction": verdict.direction,
            "decision": verdict.decision,
            "checks": [c.model_dump() for c in checks],
        },
    )
    return {"verdict": verdict}
