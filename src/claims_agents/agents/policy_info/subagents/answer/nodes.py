"""Subagente de resposta: dados reais da apólice, base de conhecimento ou LLM restrito a eles."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from claims_agents.agents.policy_info.knowledge import PolicyKnowledge
from claims_agents.agents.policy_info.state import PolicyInfoGraphState
from claims_agents.agents.policy_info.subagents.answer.schemas import AnswerOutcome
from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.messages import Messages
from claims_agents.core.prompts import load_prompt
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit

NAME = "answer"
POLICY_TOPICS = ("coberturas", "renovacao", "vencimento", "vigencia", "dados_apolice")


def _br(day: str | date) -> str:
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return d.strftime("%d/%m/%Y")


class AnswerComposer:
    def __init__(self, config: dict[str, Any], messages: Messages) -> None:
        self.m = messages
        self.coverage_labels: dict[str, str] = config.get("coverage_labels", {})
        self.status_labels: dict[str, str] = config.get("status_labels", {})
        self.window = int(config.get("renewal_window_days", 30))

    def vehicle(self, p: dict[str, Any]) -> str:
        return f"{p['vehicle_model']} {p['vehicle_plate']}"

    def line(self, topic: str, p: dict[str, Any], today: date, coverage: str | None) -> str:
        start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        status = self.status_labels.get(p["status"], p["status"].lower())
        head = f"• Apólice {p['number']} ({self.vehicle(p)})"
        if topic == "vencimento":
            days = (end - today).days
            when = (
                self.m.get("policy_info.expired_on", end=_br(end))
                if days < 0
                else self.m.get("policy_info.expires_today")
                if days == 0
                else self.m.get("policy_info.expires_on", end=_br(end), days=days)
            )
            return f"{head}: {when}."
        if topic == "renovacao":
            if p["status"] == "CANCELADA":
                return f"{head}: {self.m.get('policy_info.renewal_cancelled')}."
            opens = end - timedelta(days=self.window)
            key = (
                "renewal_expired"
                if today > end
                else "renewal_open"
                if today >= opens
                else "renewal_future"
            )
            return (
                f"{head}: " + self.m.get(f"policy_info.{key}", start=_br(opens), end=_br(end)) + "."
            )
        if topic == "coberturas":
            covs = list(p.get("coverages", []))
            if coverage:
                label = self.coverage_labels.get(coverage, coverage).lower()
                key = "has_coverage" if coverage in covs else "lacks_coverage"
                return f"{head}: " + self.m.get(f"policy_info.{key}", coverage=label) + "."
            names = ", ".join(self.coverage_labels.get(c, c) for c in covs) or "nenhuma"
            return f"{head}: {names}."
        # vigencia / dados_apolice
        return (
            f"{head}: {status}, "
            + self.m.get("policy_info.term", start=_br(start), end=_br(end))
            + "."
        )

    def policy_answer(
        self, topic: str, policies: list[dict[str, Any]], today: date, coverage: str | None
    ) -> str:
        lines = [self.line(topic, p, today, coverage) for p in policies]
        header = self.m.get("policy_info.header_" + ("many" if len(policies) > 1 else "one"))
        footer = self.m.get("policy_info.footer") if topic == "coberturas" else ""
        return "\n".join([header, *lines] + ([footer] if footer else []))


def build(
    knowledge: PolicyKnowledge,
    config: dict[str, Any],
    messages: Messages,
    llm: LLMClient | None = None,
    today: Callable[[], date] = date.today,
) -> NodeFn[PolicyInfoGraphState]:
    composer = AnswerComposer(config, messages)

    async def grounded_llm(state: PolicyInfoGraphState) -> str | None:
        if llm is None:
            return None
        facts = "\n".join(composer.line("vigencia", p, today(), None) for p in state.policies)
        covs = "\n".join(composer.line("coberturas", p, today(), None) for p in state.policies)
        prompt = load_prompt("policy_info/answer")
        system = prompt.render(
            knowledge=knowledge.kb_context(),
            policy_facts=(facts + "\n" + covs).strip() or "(segurado não identificado)",
            today=_br(today()),
        )
        try:
            resp = await llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": state.question},
                ],
                role="writer",
                prompt_version=prompt.ref,
            )
        except LLMError:
            return None
        return resp.content.strip() or None

    async def answer(state: PolicyInfoGraphState) -> dict[str, Any]:
        if state.answer:  # o subagente anterior já respondeu (pedido de CPF, não encontrado...)
            return {}
        source = "regras"
        if state.topic in POLICY_TOPICS:
            text = composer.policy_answer(
                state.topic, state.policies, today(), state.coverage_asked
            )
        elif state.topic == "faq" and state.faq_id:
            entry = next(e for e in knowledge.faq if e.id == state.faq_id)
            text, source = entry.answer, "base_de_conhecimento"
        else:
            llm_text = await grounded_llm(state)
            text, source = (
                (llm_text, "llm")
                if llm_text
                else (messages.get("policy_info.unknown"), "sem_resposta")
            )
        outcome = AnswerOutcome(topic=state.topic, source=source)
        emit(
            "query_answered",
            subagent=NAME,
            status="completed" if source != "sem_resposta" else "warning",
            details=f"{state.topic or 'pergunta livre'} via {source}",
            data=outcome.model_dump(),
        )
        return {"answer": text, "source": source}

    return answer
