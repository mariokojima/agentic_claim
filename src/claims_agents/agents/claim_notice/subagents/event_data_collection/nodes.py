"""Subagente de coleta dos dados do evento (stub da Fase 1: descrição livre em um turno)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.event_data_collection.schemas import EventDraft
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "event_data_collection"
MIN_DESCRIPTION_CHARS = 10


def build(
    messages: Messages, max_attempts: int, today: Callable[[], date] = date.today
) -> NodeFn[NoticeGraphState]:
    def event_data_collection(state: NoticeGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        if sub.step == "start":
            sub.step = "await_description"
            return {
                "sub": sub,
                "awaiting_field": "description",
                "result": StageResult(
                    status="needs_input",
                    reason="Descrição do evento solicitada",
                    user_message=messages.get("notice.ask_description"),
                ),
            }

        text = state.text.strip()
        if len(text) < MIN_DESCRIPTION_CHARS:
            attempts = sub.attempts.get("description", 0) + 1
            sub.attempts["description"] = attempts
            emit(
                "field_invalid",
                subagent=NAME,
                status="warning",
                details=f"Descrição insuficiente (tentativa {attempts}/{max_attempts})",
            )
            if attempts >= max_attempts:
                return {
                    "sub": sub,
                    "result": StageResult(
                        status="failed", reason="Limite de tentativas para a descrição excedido"
                    ),
                }
            return {
                "sub": sub,
                "awaiting_field": "description",
                "result": StageResult(
                    status="needs_input",
                    reason="Descrição insuficiente",
                    user_message=messages.get("notice.too_short"),
                ),
            }

        draft = EventDraft(event_date=today().isoformat(), location="a confirmar", description=text)
        sub.event = draft.model_dump()
        sub.step = "assess"
        emit("field_extracted", subagent=NAME, details="Descrição do evento recebida")
        return {"sub": sub}

    return event_data_collection
