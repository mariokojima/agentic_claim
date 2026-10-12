"""Subgrafo de Guardrails: três estágios em paralelo (fan-out) e agregador (fan-in)."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.guardrails.aggregator import aggregator
from claims_agents.agents.guardrails.stages import StageName, build_stage
from claims_agents.agents.guardrails.state import GuardrailGraphState

STAGES: tuple[StageName, ...] = ("security", "ethics", "corporate")


def build_guardrails_graph(config: dict[str, Any]) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(GuardrailGraphState)
    for stage in STAGES:
        g.add_node(stage, build_stage(stage, config))
        g.add_edge(START, stage)
    g.add_node("aggregator", aggregator)
    g.add_edge(list(STAGES), "aggregator")
    g.add_edge("aggregator", END)
    return g.compile()
