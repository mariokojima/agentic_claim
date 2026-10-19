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
        user_message=(messages.get("triage.urgent") + "\n\n" if urgent else "")
        + messages.get(
            "triage.identified",
            event=outcome.get("event_label", "sinistro"),
            policy=decision.get("policy_number"),
            plate=decision.get("vehicle_plate"),
        ),
    )
