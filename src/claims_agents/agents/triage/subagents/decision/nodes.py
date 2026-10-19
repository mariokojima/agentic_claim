"""Subagente de decisão: aplica as regras de elegibilidade (configs/triage_rules.yaml)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from claims_agents.agents.triage.completion import triage_completed
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.decision.schemas import EligibilityDecision
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "decision"


def decide(
    policies: list[dict[str, Any]],
    rules: dict[str, Any],
    event_date: date,
    event_type: str | None,
    claim_types: dict[str, Any],
) -> EligibilityDecision:
    """Escolhe a primeira apólice elegível; senão, devolve o motivo mais específico.

    Ordem: cliente inexistente → ocorrido que não abre aviso → regras da apólice (status,
    vigência pela data do evento, cobertura exigida para o tipo — configs/claim_types.yaml).
    """
    elig = rules["eligibility"]
    if not policies:
        return EligibilityDecision(eligible=False, reason="customer_not_found")
    if event_type not in claim_types:
        return EligibilityDecision(eligible=False, reason=f"event_type_{event_type}")
    required_coverage = claim_types[event_type]["coverage"]
    reasons: list[str] = []
    for p in policies:
        if p["status"] != elig["required_policy_status"]:
            reasons.append("policy_not_active")
            continue
        start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        if elig.get("event_must_be_within_policy_term") and not start <= event_date <= end:
            reasons.append("outside_policy_term")
            continue
        if required_coverage not in p["coverages"]:
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
    rules: dict[str, Any],
    messages: Messages,
    claim_types: dict[str, Any],
    today: Callable[[], date] = date.today,
) -> NodeFn[TriageGraphState]:
    def decision(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        event_type = sub.outcome.get("event_type")
        # vigência checada pela data do acidente, quando informada (senão, hoje)
        known_date = sub.outcome.get("event_date")
        event_date = date.fromisoformat(known_date) if known_date else today()
        result = decide(sub.outcome.get("policies", []), rules, event_date, event_type, claim_types)
        sub.step = "done"  # rejeitado; se elegível, vira "parties" abaixo
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
                    user_message=rules["rejection_messages"]
                    .get(result.reason, rules["rejection_messages"]["event_type_out_of_scope"])
                    .format(
                        event=claim_types.get(event_type or "", {}).get("label", "este evento")
                    ),
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
        # elegível: colisão pergunta envolvidos/feridos; os demais tipos concluem aqui
        if claim_types[str(event_type)].get("parties", False):
            sub.step = "parties"
            return {"sub": sub, "customer": customer}
        return {"sub": sub, "customer": customer, "result": triage_completed(sub.outcome, messages)}

    return decision
