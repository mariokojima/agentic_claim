"""Montagem da aplicação (banco, event store, tools, LLM, grafo e serviço).

Usada pela API e pelo runner de cenários, para que a avaliação exercite o mesmo código.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from claims_agents.api.service import ChatService
from claims_agents.core.llm import LLMClient
from claims_agents.core.settings import PROJECT_ROOT, Settings
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.control import PauseControl
from claims_agents.graph.deps import GraphDeps
from claims_agents.observability.bus import EventBus
from claims_agents.observability.emit import tool_observer
from claims_agents.observability.store import EventStore
from claims_agents.tools.mocks.db import DomainDB, load_fixtures
from claims_agents.tools.registry import build_registry

DeliveryFn = Callable[[str, dict[str, object]], Awaitable[bool]]


@dataclass
class Runtime:
    service: ChatService
    store: EventStore
    deps: GraphDeps


def ensure_seeded(settings: Settings) -> None:
    db = DomainDB(settings.domain_db_path)
    if not db.query("SELECT 1 FROM customers LIMIT 1"):
        db.seed(*load_fixtures(PROJECT_ROOT / "data" / "fixtures"))
    db.close()


@asynccontextmanager
async def open_runtime(
    settings: Settings,
    *,
    llm: LLMClient | None = None,
    delivery: DeliveryFn | None = None,
    guardrails_config: dict[str, Any] | None = None,
) -> AsyncIterator[Runtime]:
    ensure_seeded(settings)
    bus, control = EventBus(), PauseControl()
    store = EventStore(settings.events_db_path)
    registry = build_registry(settings, delivery=delivery, observer=tool_observer)
    deps = GraphDeps(registry=registry, settings=settings, control=control, llm=llm)
    if guardrails_config is not None:
        deps.guardrails_config = guardrails_config
    try:
        async with open_checkpointer(settings.checkpoints_db_path) as saver:
            graph = build_graph(deps, saver)
            yield Runtime(ChatService(settings, graph, store, bus, control), store, deps)
    finally:
        store.close()
