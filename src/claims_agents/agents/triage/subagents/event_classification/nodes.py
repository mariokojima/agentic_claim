"""Subagente de classificação do ocorrido: entende se o relato é um sinistro (e de que tipo)
antes de qualquer menção à abertura de aviso.

Se a primeira mensagem do cliente já descreve o ocorrido, ela é aproveitada; senão, pergunta.
"""

from __future__ import annotations

from typing import Any

from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.event_classification.classifier import EventClassifier
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "event_classification"


def build(rules: dict[str, Any], messages: Messages, max_attempts: int) -> NodeFn[TriageGraphState]:
    classifier = EventClassifier(rules)

    def event_classification(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        first_name = state.customer.name.split()[0] if state.customer else ""

        if sub.step == "classify":
            # Recém-identificado: aproveita o relato inicial, se houver.
            initial = str(sub.outcome.get("initial_text", ""))
            result = classifier.classify(initial) if initial else None
            if result is None or result.event_type is None:
                sub.step = "await_event"
                return _ask(
                    sub, messages.get("triage.ask_event", name=first_name), "Ocorrido solicitado"
                )
            text = initial
        else:  # await_event
            text = state.text
            result = classifier.classify(text)
            if result.event_type is None:
                attempts = sub.attempts.get("event", 0) + 1
                sub.attempts["event"] = attempts
                emit(
                    "event_unclear",
                    subagent=NAME,
                    status="warning",
                    details=f"Ocorrido não identificado (tentativa {attempts}/{max_attempts})",
                )
                if attempts >= max_attempts:
                    return {
                        "sub": sub,
                        "result": StageResult(
                            status="failed", reason="Não foi possível entender o ocorrido"
                        ),
                    }
                return _ask(sub, messages.get("triage.unclear_event"), "Ocorrido não identificado")

        sub.outcome |= {
            "event_type": result.event_type,
            "event_label": result.label,
            "event_description": text,
            "has_injuries": result.has_injuries,
            "urgency": "alta" if result.has_injuries else "normal",
        }
        sub.step = "decide"
        emit(
            "event_classified",
            subagent=NAME,
            status="completed" if result.event_type == "COLISAO" else "warning",
            details=f'{result.label} (trecho: "{result.matched}")'
            + (" — urgência alta: feridos" if result.has_injuries else ""),
            data=result.model_dump(),
        )
        return {"sub": sub}

    return event_classification


def _ask(sub: Any, text: str, reason: str) -> dict[str, Any]:
    return {
        "sub": sub,
        "awaiting_field": "event",
        "result": StageResult(status="needs_input", reason=reason, user_message=text),
    }
