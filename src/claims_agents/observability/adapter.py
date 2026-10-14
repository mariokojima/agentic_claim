"""Adaptador de streaming: fonte única de `AgentEvent` (ADR-0011).

Consome `graph.astream(stream_mode=["tasks", "custom"], subgraphs=True)` e normaliza:
- `tasks` do grafo principal → `node_start` / `node_end` (com latência);
- `tasks` de subgrafos → `subagent_end` (agente = nó pai, subagente = nó interno);
- `custom` (via `emit()`) → evento de domínio, com agente inferido quando ausente.
Todo evento tem PII mascarada, é persistido e publicado.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.privacy import mask_text
from claims_agents.observability.emit import CUSTOM_KIND
from claims_agents.observability.events import AgentEvent

EventSink = Callable[[AgentEvent], Awaitable[None] | None]


class StreamAdapter:
    def __init__(self, conversation_id: str, sinks: Iterable[EventSink] = ()) -> None:
        self.conversation_id = conversation_id
        self.sinks = list(sinks)
        self.events: list[AgentEvent] = []
        self._started: dict[str, float] = {}
        self._current_node: str = "graph"

    async def run(
        self,
        graph: CompiledStateGraph[Any, Any, Any, Any],
        graph_input: Any,
        config: RunnableConfig,
        context: Any,
    ) -> list[AgentEvent]:
        turn_start = time.perf_counter()
        try:
            async for item in graph.astream(
                graph_input,
                config,
                context=context,
                stream_mode=["tasks", "custom"],
                subgraphs=True,
            ):
                # subgraphs=True + lista de modos → (namespace, modo, dado)
                ns, mode, chunk = cast(tuple[tuple[str, ...], str, Any], item)
                for ev in self.normalize(ns, mode, chunk):
                    await self._publish(ev)
        except Exception as exc:
            await self._publish(
                self._event(
                    agent=self._current_node,
                    event="turn_failed",
                    details=f"{type(exc).__name__}: {exc}",
                    status="error",
                )
            )
            raise
        await self._publish(
            self._event(
                agent="graph",
                event="turn_completed",
                details="Turno concluído",
                latency_ms=int((time.perf_counter() - turn_start) * 1000),
            )
        )
        return self.events

    def normalize(self, ns: tuple[str, ...], mode: str, chunk: Any) -> list[AgentEvent]:
        parent = ns[0].split(":", 1)[0] if ns else None
        if mode == "tasks":
            return self._from_task(parent, chunk)
        if mode == "custom" and isinstance(chunk, dict) and chunk.get("kind") == CUSTOM_KIND:
            return [self._from_custom(parent, chunk)]
        return []

    def _from_task(self, parent: str | None, chunk: dict[str, Any]) -> list[AgentEvent]:
        name, task_id = chunk["name"], chunk["id"]
        is_start = "result" not in chunk and "error" not in chunk
        if parent is None:
            if is_start:
                self._started[task_id] = time.perf_counter()
                self._current_node = name
                return [self._event(agent=name, event="node_start", status="processing")]
            latency = self._latency(task_id)
            error = chunk.get("error")
            return [
                self._event(
                    agent=name,
                    event="node_end",
                    status="error" if error else "completed",
                    details=str(error) if error else "",
                    latency_ms=latency,
                )
            ]
        if is_start:
            self._started[task_id] = time.perf_counter()
            return [
                self._event(
                    agent=parent, subagent=name, event="subagent_start", status="processing"
                )
            ]
        error = chunk.get("error")
        return [
            self._event(
                agent=parent,
                subagent=name,
                event="subagent_end",
                status="error" if error else "completed",
                details=str(error) if error else "",
                latency_ms=self._latency(task_id),
            )
        ]

    def _from_custom(self, parent: str | None, chunk: dict[str, Any]) -> AgentEvent:
        return self._event(
            agent=chunk.get("agent") or parent or self._current_node,
            subagent=chunk.get("subagent"),
            event=chunk["event"],
            details=chunk.get("details", ""),
            status=chunk.get("status", "completed"),
            tool=chunk.get("tool"),
            latency_ms=chunk.get("latency_ms"),
            tokens=chunk.get("tokens"),
            data=chunk.get("data") or {},
        )

    def _latency(self, task_id: str) -> int | None:
        start = self._started.pop(task_id, None)
        return int((time.perf_counter() - start) * 1000) if start is not None else None

    def _event(self, **kwargs: Any) -> AgentEvent:
        kwargs["details"] = mask_text(kwargs.get("details") or "")
        return AgentEvent(conversation_id=self.conversation_id, **kwargs)

    async def _publish(self, ev: AgentEvent) -> None:
        self.events.append(ev)
        for sink in self.sinks:
            result = sink(ev)
            if result is not None:
                await result
