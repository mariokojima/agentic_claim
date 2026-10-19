"""Subagente de classificação do ocorrido: entende se o relato é um sinistro (e de que tipo)
antes de qualquer menção à abertura de aviso.

Regras primeiro (configs/triage_rules.yaml); se não entenderem, o LLM (prompt versionado) entra
como fallback. Se a primeira mensagem do cliente já descreve o ocorrido, ela é aproveitada.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from claims_agents.agents.shared.event_extraction import extract_when
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.event_classification.classifier import EventClassifier
from claims_agents.agents.triage.subagents.event_classification.schemas import (
    EventClassification,
    LLMEventClassification,
)
from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.messages import Messages
from claims_agents.core.prompts import load_prompt
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "event_classification"
MIN_WORDS_FOR_LLM = 4


def build(
    rules: dict[str, Any],
    messages: Messages,
    max_attempts: int,
    llm: LLMClient | None = None,
    today: Callable[[], date] = date.today,
) -> NodeFn[TriageGraphState]:
    classifier = EventClassifier(rules)
    labels: dict[str, str] = rules["event_classification"].get("labels", {})

    async def classify(text: str) -> EventClassification:
        result = classifier.classify(text)
        # LLM só para relatos com conteúdo (evita gastar tokens com "Oi", "bom dia"...)
        if result.event_type is not None or llm is None or len(text.split()) < MIN_WORDS_FOR_LLM:
            return result
        prompt = load_prompt("triage/event_classification")
        try:
            resp = await llm.chat(
                [{"role": "system", "content": prompt.text}, {"role": "user", "content": text}],
                role="extraction",
                response_model=LLMEventClassification,
                prompt_version=prompt.ref,
            )
        except LLMError:
            return result  # degrada para regras (não entendido)
        out = LLMEventClassification.model_validate(resp.parsed)
        if out.event_type == "INDEFINIDO":
            return result
        return EventClassification(
            event_type=out.event_type,
            label=labels.get(out.event_type, out.event_type),
            matched=out.justification,
            has_injuries=bool(out.has_injuries),
            injuries_hint=out.has_injuries,
            has_third_parties=out.has_third_parties,
            source="llm",
        )

    async def event_classification(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        first_name = state.customer.name.split()[0] if state.customer else ""

        if sub.step == "classify":
            # Recém-identificado: aproveita o relato inicial, se houver.
            text = str(sub.outcome.get("initial_text", ""))
            result = await classify(text) if text else None
            if result is None or result.event_type is None:
                sub.step = "await_event"
                return _ask(
                    sub, messages.get("triage.ask_event", name=first_name), "Ocorrido solicitado"
                )
        else:  # await_event
            text = state.text
            result = await classify(text)
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

        event_date, _, future = extract_when(text, today())
        sub.outcome |= {
            "event_type": result.event_type,
            "event_label": result.label,
            "event_description": text,
            "classification_source": result.source,
            # pistas do LLM para o subagente de envolvidos (None = não informado; regras ficam
            # com o detector de envolvidos, que trata negativas como "ninguém se feriu")
            "has_injuries": result.injuries_hint,
            "has_third_parties": result.has_third_parties,
            "event_date": event_date.isoformat() if event_date and not future else None,
        }
        sub.step = "decide"
        emit(
            "event_classified",
            subagent=NAME,
            status="completed" if result.event_type == "COLISAO" else "warning",
            details=f"{result.label} — via {result.source} ({result.matched})",
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
