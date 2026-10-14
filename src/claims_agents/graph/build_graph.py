"""Montagem do grafo principal (ver docs/architecture.md §1)."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.orchestrator.routing_policy import STAGE_TO_SPECIALIST
from claims_agents.core.types import NodeFn
from claims_agents.graph.demo import with_demo_delay
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.nodes import MainNodes, route_by_state
from claims_agents.state import GlobalState

SPECIALISTS = list(STAGE_TO_SPECIALIST.values())

NodeCallable = NodeFn[GlobalState]


def build_graph(
    deps: GraphDeps, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[Any, Any, Any, Any]:
    n = MainNodes(deps)
    delay_ms = deps.settings.demo.node_delay_ms

    def delay(fn: NodeCallable) -> NodeCallable:
        return with_demo_delay(fn, delay_ms)

    g = StateGraph(GlobalState)
    g.add_node("receive", delay(n.receive))
    g.add_node("guardrails_in", delay(n.guardrails_in))
    g.add_node("orchestrator", delay(n.orchestrator))
    g.add_node("triage", delay(n.triage))
    g.add_node("claim_notice", delay(n.claim_notice))
    g.add_node("documents", delay(n.documents))
    g.add_node("transition", delay(n.transition))
    g.add_node("guardrails_out", delay(n.guardrails_out))
    g.add_node("send", delay(n.send))

    g.add_edge(START, "receive")
    g.add_conditional_edges("receive", route_by_state, ["guardrails_in", "guardrails_out"])
    g.add_conditional_edges("guardrails_in", route_by_state, ["orchestrator", "transition"])
    g.add_conditional_edges("orchestrator", route_by_state, SPECIALISTS)
    for specialist in SPECIALISTS:
        g.add_edge(specialist, "transition")
    g.add_conditional_edges("transition", route_by_state, ["orchestrator", "guardrails_out"])
    g.add_edge("guardrails_out", "send")
    g.add_edge("send", END)
    return g.compile(checkpointer=checkpointer)
