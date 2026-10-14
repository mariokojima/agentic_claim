"""Subgrafo do Aviso de Sinistro."""

from collections.abc import Hashable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.claim_notice import coordinator
from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.coverage_assessment.nodes import (
    coverage_assessment,
)
from claims_agents.agents.claim_notice.subagents.event_data_collection import (
    nodes as event_data_collection,
)
from claims_agents.agents.claim_notice.subagents.registration import nodes as registration
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeWrapper, identity
from claims_agents.tools.interfaces import OpenClaim

SUBAGENTS = ["event_data_collection", "coverage_assessment", "registration"]


def build_claim_notice_graph(
    open_claim: OpenClaim,
    messages: Messages,
    max_attempts: int = 3,
    wrap: NodeWrapper = identity,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(NoticeGraphState)
    g.add_node("event_data_collection", wrap(event_data_collection.build(messages, max_attempts)))
    g.add_node("coverage_assessment", wrap(coverage_assessment))
    g.add_node("registration", wrap(registration.build(open_claim, messages)))
    routes: dict[Hashable, str] = {name: name for name in SUBAGENTS}
    routes["end"] = END
    g.add_conditional_edges(START, coordinator.next_subagent, routes)
    for name in SUBAGENTS:
        g.add_conditional_edges(name, coordinator.next_subagent, routes)
    return g.compile()
