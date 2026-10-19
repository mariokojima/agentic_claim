"""Subagente de envolvidos: há terceiros? alguém se feriu? (só para colisão)

Usa o relato já feito; pergunta apenas o que não foi informado. Regras primeiro, LLM como
fallback para respostas ambíguas. Terceiros ou feridos tornam o BO obrigatório (Documentos).
"""

from __future__ import annotations

from typing import Any

from claims_agents.agents.triage.completion import triage_completed
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.parties.detector import PartiesDetector
from claims_agents.agents.triage.subagents.parties.schemas import PartiesExtraction
from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.messages import Messages
from claims_agents.core.prompts import load_prompt
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "parties"
FIELDS = ("third_parties", "injuries")


def build(
    rules: dict[str, Any], messages: Messages, max_attempts: int, llm: LLMClient | None = None
) -> NodeFn[TriageGraphState]:
    detector = PartiesDetector(rules)

    async def parties(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        known = {f: sub.outcome.get(f"has_{f}") for f in FIELDS}

        if sub.step == "parties":  # primeira passagem: usa o relato
            found = detector.detect(str(sub.outcome.get("event_description", "")))
            _merge(known, found)
        else:  # await_parties: interpreta a resposta
            asked = list(sub.outcome.get("parties_asked", []))
            found = detector.from_answer(state.text, asked)
            if llm is not None and any(_merged(known, found)[f] is None for f in asked):
                found = await _llm_fallback(llm, state.text, sub.outcome, messages, asked) or found
            before = dict(known)
            _merge(known, found)
            if known == before:
                attempts = sub.attempts.get("parties", 0) + 1
                sub.attempts["parties"] = attempts
                if attempts >= max_attempts:
                    return {
                        "sub": sub,
                        "result": StageResult(
                            status="failed", reason="Não foi possível identificar os envolvidos"
                        ),
                    }

        sub.outcome |= {f"has_{f}": v for f, v in known.items()}
        missing = [f for f in FIELDS if known[f] is None]
        if missing:
            sub.step = "await_parties"
            sub.outcome["parties_asked"] = missing
            key = "triage.ask_parties_" + ("both" if len(missing) == 2 else missing[0])
            if sub.attempts.get("parties"):
                key = "triage.unclear_parties"
            return {
                "sub": sub,
                "awaiting_field": "parties",
                "result": StageResult(
                    status="needs_input",
                    reason=f"Envolvidos: falta {', '.join(missing)}",
                    user_message=messages.get(key),
                ),
            }
        sub.step = "done"
        emit(
            "parties_identified",
            subagent=NAME,
            status="warning" if known["injuries"] else "completed",
            details=f"Terceiros: {_yn(known['third_parties'])}; feridos: {_yn(known['injuries'])}",
            data={"has_third_parties": known["third_parties"], "has_injuries": known["injuries"]},
        )
        return {"sub": sub, "result": triage_completed(sub.outcome, messages)}

    return parties


def _merged(known: dict[str, bool | None], found: PartiesExtraction) -> dict[str, bool | None]:
    out = dict(known)
    _merge(out, found)
    return out


def _merge(known: dict[str, bool | None], found: PartiesExtraction) -> None:
    for f in FIELDS:
        value = getattr(found, f"has_{f}")
        if known[f] is None and value is not None:
            known[f] = value


async def _llm_fallback(
    llm: LLMClient, answer: str, outcome: dict[str, Any], messages: Messages, asked: list[str]
) -> PartiesExtraction | None:
    prompt = load_prompt("triage/parties")
    question = messages.get("triage.ask_parties_" + ("both" if len(asked) == 2 else asked[0]))
    system = prompt.render(question=question, description=str(outcome.get("event_description", "")))
    try:
        resp = await llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": answer}],
            role="extraction",
            response_model=PartiesExtraction,
            prompt_version=prompt.ref,
        )
    except LLMError:
        return None
    return PartiesExtraction.model_validate(resp.parsed)


def _yn(value: bool | None) -> str:
    return "sim" if value else "não"
