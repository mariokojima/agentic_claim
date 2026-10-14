"""Subagente de coleta dos dados do evento: exige quando, onde e o que aconteceu.

As informações são acumuladas entre mensagens; o cliente só é perguntado pelo que falta.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.event_data_collection.extraction import (
    extract_event,
)
from claims_agents.agents.claim_notice.subagents.event_data_collection.schemas import EventDraft
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "event_data_collection"
FIELDS = ("when", "where", "what")


def describe_when(event: dict[str, Any]) -> str:
    text = date.fromisoformat(event["event_date"]).strftime("%d/%m/%Y")
    if event.get("event_time"):
        text += f" às {event['event_time'][:5]}"
    return text


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
        ext = extract_event(text, today())
        event = dict(sub.event)
        before = {f: _has(event, f) for f in FIELDS}
        if ext.event_date and not before["when"]:
            event["event_date"] = ext.event_date.isoformat()
        if ext.event_time and not event.get("event_time"):
            event["event_time"] = ext.event_time.isoformat()
        if ext.location and not before["where"]:
            event["location"] = ext.location
        if ext.what and not before["what"]:
            event["what"] = ext.what
        if text:
            event["description"] = f"{event.get('description', '')} {text}".strip()
        sub.event = event

        found = [f for f in FIELDS if _has(event, f) and not before[f]]
        missing = [f for f in FIELDS if not _has(event, f)]
        emit(
            "field_extracted" if found else "field_invalid",
            subagent=NAME,
            status="completed" if found else "warning",
            details=_summary(event, missing),
            data={"found": found, "missing": missing, "future_date": ext.future_date},
        )

        if ext.future_date and not _has(event, "when"):
            return _ask(
                sub, messages.get("notice.future_date", date=ext.when_text), "Data no futuro"
            )
        if missing:
            if not found:
                attempts = sub.attempts.get("description", 0) + 1
                sub.attempts["description"] = attempts
                if attempts >= max_attempts:
                    return {
                        "sub": sub,
                        "result": StageResult(
                            status="failed",
                            reason="Limite de tentativas para os dados do evento excedido",
                        ),
                    }
            items = "\n".join(messages.get(f"notice.missing_{f}") for f in missing)
            text_out = messages.get("notice.missing", items=items)
            if any(_has(event, f) for f in FIELDS):
                text_out = (
                    messages.get("notice.understood", summary=_understood(event))
                    + "\n\n"
                    + text_out
                )
            return _ask(sub, text_out, f"Faltam: {', '.join(missing)}")

        draft = EventDraft(
            event_date=event["event_date"],
            event_time=event.get("event_time"),
            location=event["location"],
            description=event["description"],
        )
        sub.event = draft.model_dump() | {"what": event["what"]}
        sub.step = "assess"
        return {"sub": sub}

    return event_data_collection


def _has(event: dict[str, Any], field: str) -> bool:
    key = {"when": "event_date", "where": "location", "what": "what"}[field]
    return bool(event.get(key))


def _understood(event: dict[str, Any]) -> str:
    parts = []
    if _has(event, "when"):
        parts.append(f"quando: {describe_when(event)}")
    if _has(event, "where"):
        parts.append(f"onde: {event['location']}")
    if _has(event, "what"):
        parts.append(f"o que: {event['what']}")
    return "; ".join(parts)


def _summary(event: dict[str, Any], missing: list[str]) -> str:
    got = _understood(event) or "nada identificado"
    return f"{got}" + (f" | faltam: {', '.join(missing)}" if missing else " | completo")


def _ask(sub: Any, text: str, reason: str) -> dict[str, Any]:
    return {
        "sub": sub,
        "awaiting_field": "description",
        "result": StageResult(status="needs_input", reason=reason, user_message=text),
    }
