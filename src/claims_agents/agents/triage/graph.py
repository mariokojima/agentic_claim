"""Subgrafo da Triagem. Só conhece o contrato `StageResult` (não importa o Orquestrador)."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.triage import coordinator
from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.customer_validation import nodes as customer_validation
from claims_agents.agents.triage.subagents.decision import nodes as decision
from claims_agents.core.messages import Messages
from claims_agents.tools.interfaces import GetCustomerData


def build_triage_graph(
    get_customer_data: GetCustomerData,
    rules: dict[str, Any],
    messages: Messages,
    max_attempts: int = 3,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(TriageGraphState)
    g.add_node(
        "customer_validation", customer_validation.build(get_customer_data, messages, max_attempts)
    )
    g.add_node("decision", decision.build(rules, messages))
    g.add_conditional_edges(START, coordinator.next_subagent, ["customer_validation", "decision"])
    g.add_conditional_edges(
        "customer_validation", coordinator.after_validation, {"end": END, "decision": "decision"}
    )
    g.add_edge("decision", END)
    return g.compile()
