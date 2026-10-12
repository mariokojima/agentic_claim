"""Subagente de decisão: aplica as regras de elegibilidade (configs/triage_rules.yaml)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.decision.schemas import EligibilityDecision
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "decision"


def decide(
    policies: list[dict[str, Any]], rules: dict[str, Any], event_date: date
) -> EligibilityDecision:
    """Escolhe a primeira apólice elegível; senão, devolve o motivo mais específico."""
    elig = rules["eligibility"]
    if not policies:
        return EligibilityDecision(eligible=False, reason="customer_not_found")
    reasons: list[str] = []
    for p in policies:
        if p["status"] != elig["required_policy_status"]:
            reasons.append("policy_not_active")
            continue
        start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        if elig.get("event_must_be_within_policy_term") and not start <= event_date <= end:
            reasons.append("outside_policy_term")
            continue
        if elig["required_coverage"] not in p["coverages"]:
            reasons.append("no_coverage")
            continue
        return EligibilityDecision(
            eligible=True,
            reason="eligible",
            policy_number=p["number"],
            vehicle_plate=p["vehicle_plate"],
        )
    priority = ["no_coverage", "outside_policy_term", "policy_not_active"]
    return EligibilityDecision(eligible=False, reason=next(r for r in priority if r in reasons))


def build(
    rules: dict[str, Any], messages: Messages, today: Callable[[], date] = date.today
) -> NodeFn[TriageGraphState]:
    def decision(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        result = decide(sub.outcome.get("policies", []), rules, today())
        sub.step = "done"
        sub.outcome["decision"] = result.model_dump()
        emit(
            "eligibility_decision",
            subagent=NAME,
            status="completed" if result.eligible else "warning",
            details=f"Elegível: {'sim' if result.eligible else 'não'} ({result.reason})",
            data=result.model_dump(),
        )
        if not result.eligible:
            return {
                "sub": sub,
                "result": StageResult(
                    status="rejected",
                    reason=result.reason,
                    payload={"rejection": result.reason},
                    user_message=rules["rejection_messages"][result.reason],
                ),
            }
        customer = (
            state.customer.model_copy(
                update={
                    "policy_number": result.policy_number,
                    "vehicle_plate": result.vehicle_plate,
                }
            )
            if state.customer
            else None
        )
        return {
            "sub": sub,
            "customer": customer,
            "result": StageResult(
                status="completed",
                reason="Segurado identificado e elegível",
                payload=result.model_dump(),
                user_message=messages.get(
                    "triage.identified",
                    name=customer.name.split()[0] if customer else "",
                    policy=result.policy_number,
                    plate=result.vehicle_plate,
                ),
            ),
        }

    return decision
