"""Execução de um turno: uma invocação do grafo por mensagem do usuário."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from claims_agents.observability.adapter import EventSink, StreamAdapter
from claims_agents.observability.events import AgentEvent
from claims_agents.state import GlobalState, Inbound


class TurnResult(BaseModel):
    events: list[AgentEvent]
    state: GlobalState


def thread_config(conversation_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": conversation_id}}


async def get_state(
    graph: CompiledStateGraph[Any, Any, Any, Any], conversation_id: str
) -> GlobalState | None:
    snapshot = await graph.aget_state(thread_config(conversation_id))
    return GlobalState.model_validate(snapshot.values) if snapshot.values else None


async def run_turn(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    conversation_id: str,
    inbound: Inbound,
    *,
    customer_phone: str | None = None,
    sinks: Iterable[EventSink] = (),
) -> TurnResult:
    graph_input: dict[str, Any] = {"conversation_id": conversation_id, "inbound": inbound}
    if customer_phone:
        graph_input["customer_phone"] = customer_phone
    adapter = StreamAdapter(conversation_id, sinks)
    events = await adapter.run(graph, graph_input, thread_config(conversation_id), None)
    state = await get_state(graph, conversation_id)
    assert state is not None
    return TurnResult(events=events, state=state)
