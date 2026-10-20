"""Subgrafo do especialista Consultas (ADR-0019). Só conhece seu próprio estado."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.policy_info import coordinator
from claims_agents.agents.policy_info.knowledge import PolicyKnowledge
from claims_agents.agents.policy_info.state import PolicyInfoGraphState
from claims_agents.agents.policy_info.subagents.answer import nodes as answer
from claims_agents.agents.policy_info.subagents.customer_lookup import nodes as customer_lookup
from claims_agents.agents.policy_info.subagents.query_classification import (
    nodes as query_classification,
)
from claims_agents.core.llm import LLMClient
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeWrapper, identity
from claims_agents.tools.interfaces import GetCustomerData


def build_policy_info_graph(
    get_customer_data: GetCustomerData,
    config: dict[str, Any],
    messages: Messages,
    wrap: NodeWrapper = identity,
    llm: LLMClient | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    knowledge = PolicyKnowledge(config)
    g = StateGraph(PolicyInfoGraphState)
    g.add_node("query_classification", wrap(query_classification.build(knowledge)))
    g.add_node("customer_lookup", wrap(customer_lookup.build(get_customer_data, messages)))
    g.add_node("answer", wrap(answer.build(knowledge, config, messages, llm)))
    g.add_edge(START, "query_classification")
    g.add_conditional_edges(
        "query_classification",
        coordinator.after_classification,
        ["customer_lookup", "answer"],
    )
    g.add_edge("customer_lookup", "answer")
    g.add_edge("answer", END)
    return g.compile()
