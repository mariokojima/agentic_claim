"""Conclusão da Triagem (compartilhada pela decisão e pelo subagente de envolvidos)."""

from __future__ import annotations

from typing import Any

from claims_agents.core.messages import Messages
from claims_agents.state import StageResult

PAYLOAD_KEYS = (
    "event_type",
    "event_label",
    "event_description",
    "event_date",
    "has_third_parties",
    "has_injuries",
)


def empathy_once(outcome: dict[str, Any], messages: Messages) -> str:
    """Acolhimento conforme o tipo de sinistro, uma única vez por atendimento ("" se já dito)."""
    if outcome.get("empathy_shown"):
        return ""
    outcome["empathy_shown"] = True
    text = messages.optional(f"triage.empathy.{outcome.get('event_type')}")
    return f"{text}\n\n" if text else ""


def triage_completed(outcome: dict[str, Any], messages: Messages) -> StageResult:
    """Segurado elegível e ocorrido entendido (e envolvidos, quando aplicável)."""
    decision = outcome.get("decision", {})
    urgent = bool(outcome.get("has_injuries"))
    return StageResult(
        status="completed",
        reason="Segurado identificado, elegível e ocorrido entendido",
        payload=decision
        | {k: outcome.get(k) for k in PAYLOAD_KEYS}
        | {"urgency": "alta" if urgent else "normal"},
        user_message=empathy_once(outcome, messages)
        + (messages.get("triage.urgent") + "\n\n" if urgent else "")
        + messages.get(
            "triage.identified",
            event=outcome.get("event_label", "sinistro"),
            policy=decision.get("policy_number"),
            plate=decision.get("vehicle_plate"),
        ),
    )
