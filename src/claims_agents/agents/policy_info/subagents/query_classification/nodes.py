"""Subagente de classificação da pergunta: tópico da apólice ou dúvida da base de conhecimento."""

from typing import Any

from claims_agents.agents.policy_info.knowledge import PolicyKnowledge
from claims_agents.agents.policy_info.state import PolicyInfoGraphState
from claims_agents.agents.policy_info.subagents.query_classification.schemas import (
    QueryClassification,
)
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit

NAME = "query_classification"


def build(knowledge: PolicyKnowledge) -> NodeFn[PolicyInfoGraphState]:
    def query_classification(state: PolicyInfoGraphState) -> dict[str, Any]:
        question = state.pending_query if state.awaiting_cpf else state.text
        topic, faq_id = knowledge.classify(question)
        result = QueryClassification(
            topic=topic,
            faq_id=faq_id,
            coverage_asked=knowledge.coverage_asked(question) if topic == "coberturas" else None,
        )
        emit(
            "query_classified",
            subagent=NAME,
            status="completed" if topic else "warning",
            details=f"{topic or 'não identificado'}"
            + (f" ({faq_id})" if faq_id else "")
            + (f" — cobertura: {result.coverage_asked}" if result.coverage_asked else ""),
            data=result.model_dump(),
        )
        return {"question": question, **result.model_dump()}

    return query_classification
