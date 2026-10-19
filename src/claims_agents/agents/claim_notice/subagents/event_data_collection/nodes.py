"""Subagente de coleta dos dados do evento: quando, onde, o que aconteceu e danos.

As informações são acumuladas entre mensagens; o cliente só é perguntado pelo que falta.
Regras primeiro; o LLM (prompt versionado) entra quando as regras deixam lacunas.
Envolvidos já vêm da Triagem.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.event_data_collection.schemas import EventDraft
from claims_agents.agents.shared.event_extraction import EventExtraction, extract_event
from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.messages import Messages
from claims_agents.core.prompts import load_prompt
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "event_data_collection"
FIELDS = ("when", "where", "what", "damages")
FIELD_LABELS = {"when": "quando", "where": "onde", "what": "o que", "damages": "danos"}
KEYS = {"when": "event_date", "where": "location", "what": "what", "damages": "damages"}
WEEKDAYS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]
MIN_WORDS_FOR_LLM = 4


class LLMEventData(BaseModel):
    """Saída estruturada pedida ao LLM (prompts/claim_notice/event_extraction.md)."""

    event_date: str | None
    event_time: str | None
    location: str | None
    what: str | None
    damages: str | None


def describe_when(event: dict[str, Any]) -> str:
    text = date.fromisoformat(event["event_date"]).strftime("%d/%m/%Y")
    if event.get("event_time"):
        text += f" às {event['event_time'][:5]}"
    return text


def build(
    messages: Messages,
    max_attempts: int,
    today: Callable[[], date] = date.today,
    llm: LLMClient | None = None,
) -> NodeFn[NoticeGraphState]:
    async def llm_fill(
        text: str, ext: EventExtraction, event: dict[str, Any], fields: list[str]
    ) -> EventExtraction:
        """Completa com o LLM apenas os campos que as regras não acharam."""
        missing = [f for f in fields if not event.get(KEYS[f]) and not _ext_has(ext, f)]
        if llm is None or not missing or len(text.split()) < MIN_WORDS_FOR_LLM:
            return ext
        prompt = load_prompt("claim_notice/event_extraction")
        day = today()
        system = prompt.render(today=day.isoformat(), weekday=WEEKDAYS[day.weekday()])
        try:
            resp = await llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": text}],
                role="extraction",
                response_model=LLMEventData,
                prompt_version=prompt.ref,
            )
        except LLMError:
            return ext
        out = LLMEventData.model_validate(resp.parsed)
        update: dict[str, Any] = {}
        parsed_date = _parse_date(out.event_date)
        if not ext.event_date and parsed_date and parsed_date <= day:
            update["event_date"] = parsed_date
        if not ext.event_time and (parsed_time := _parse_time(out.event_time)):
            update["event_time"] = parsed_time
        for field in ("location", "what", "damages"):
            if not getattr(ext, field) and getattr(out, field):
                update[field] = str(getattr(out, field))[:120]
        if update:
            emit(
                "llm_extraction",
                subagent=NAME,
                details=", ".join(sorted(update)),
                data={"fields": sorted(update)},
            )
        return ext.model_copy(update=update)

    async def event_data_collection(state: NoticeGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        first_pass = sub.step == "start"
        if first_pass:
            sub.step = "await_description"
            if not state.prior_text.strip():
                return _ask(sub, messages.get("notice.ask_description"), "Descrição solicitada")
            # reaproveita o relato da Triagem: só pergunta o que faltar
            text = state.prior_text.strip()
        else:
            text = state.text.strip()
        event = dict(sub.event)
        fields = [f for f in state.fields if f in FIELDS] or list(FIELDS)
        ext = await llm_fill(text, extract_event(text, today()), event, fields)
        before = {f: _has(event, f) for f in FIELDS}
        if ext.event_date and not before["when"]:
            event["event_date"] = ext.event_date.isoformat()
        if ext.event_time and not event.get("event_time"):
            event["event_time"] = ext.event_time.isoformat()
        if ext.location and not before["where"]:
            event["location"] = ext.location
        if ext.what and not before["what"]:
            event["what"] = ext.what
        elif first_pass and not before["what"] and state.known_what:
            event["what"] = state.known_what  # a Triagem já entendeu o ocorrido
        if ext.damages and not before["damages"]:
            event["damages"] = ext.damages
        if text:
            event["description"] = f"{event.get('description', '')} {text}".strip()
        sub.event = event

        found = [f for f in FIELDS if _has(event, f) and not before[f]]
        missing = [f for f in fields if not _has(event, f)]
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
            if not found and not first_pass:
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
            return _ask(sub, text_out, f"Faltam: {', '.join(FIELD_LABELS[m] for m in missing)}")

        draft = EventDraft(
            event_date=event["event_date"],
            event_time=event.get("event_time"),
            location=event["location"],
            description=event["description"],
            damages=event.get("damages") or "",
            has_third_parties=state.parties.get("has_third_parties", False),
            has_injuries=state.parties.get("has_injuries", False),
        )
        sub.event = draft.model_dump() | {"what": event.get("what") or state.known_what}
        sub.step = "assess"
        return {"sub": sub}

    return event_data_collection


def _has(event: dict[str, Any], field: str) -> bool:
    return bool(event.get(KEYS[field]))


def _ext_has(ext: EventExtraction, field: str) -> bool:
    return bool(getattr(ext, {"when": "event_date", "where": "location"}.get(field, field)))


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _parse_time(value: str | None) -> time | None:
    try:
        return datetime.strptime(value, "%H:%M").time() if value else None
    except ValueError:
        return None


def _understood(event: dict[str, Any]) -> str:
    parts = []
    if _has(event, "when"):
        parts.append(f"quando: {describe_when(event)}")
    if _has(event, "where"):
        parts.append(f"onde: {event['location']}")
    if _has(event, "what"):
        parts.append(f"o que: {event['what']}")
    if _has(event, "damages"):
        parts.append(f"danos: {event['damages']}")
    return "; ".join(parts)


def _summary(event: dict[str, Any], missing: list[str]) -> str:
    got = _understood(event) or "nada identificado"
    return f"{got}" + (
        f" | faltam: {', '.join(FIELD_LABELS[m] for m in missing)}" if missing else " | completo"
    )


def _ask(sub: Any, text: str, reason: str) -> dict[str, Any]:
    return {
        "sub": sub,
        "awaiting_field": "description",
        "result": StageResult(status="needs_input", reason=reason, user_message=text),
    }
