"""Subgrafo da Triagem. Só conhece o contrato `StageResult` (não importa o Orquestrador)."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.triage import coordinator
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.customer_validation import nodes as customer_validation
from claims_agents.agents.triage.subagents.decision import nodes as decision
from claims_agents.agents.triage.subagents.event_classification import (
    nodes as event_classification,
)
from claims_agents.agents.triage.subagents.parties import nodes as parties
from claims_agents.core.llm import LLMClient
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeWrapper, identity
from claims_agents.tools.interfaces import GetCustomerData


def build_triage_graph(
    get_customer_data: GetCustomerData,
    rules: dict[str, Any],
    messages: Messages,
    max_attempts: int = 3,
    wrap: NodeWrapper = identity,
    llm: LLMClient | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(TriageGraphState)
    g.add_node(
        "customer_validation",
        wrap(customer_validation.build(get_customer_data, messages, max_attempts)),
    )
    g.add_node(
        "event_classification", wrap(event_classification.build(rules, messages, max_attempts, llm))
    )
    g.add_node("parties", wrap(parties.build(rules, messages, max_attempts, llm)))
    g.add_node("decision", wrap(decision.build(rules, messages)))
    g.add_conditional_edges(
        START,
        coordinator.next_subagent,
        ["customer_validation", "event_classification", "parties", "decision"],
    )
    g.add_conditional_edges(
        "customer_validation",
        coordinator.after_validation,
        {"end": END, "decision": "decision", "event_classification": "event_classification"},
    )
    g.add_conditional_edges(
        "event_classification",
        coordinator.after_classification,
        {"end": END, "decision": "decision"},
    )
    g.add_conditional_edges(
        "decision", coordinator.after_decision, {"end": END, "parties": "parties"}
    )
    g.add_edge("parties", END)
    return g.compile()
