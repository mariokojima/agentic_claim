"""Checkpointer SQLite do LangGraph (thread_id = conversation_id).

Os tipos do estado são registrados explicitamente na allowlist do serializer msgpack
(o modo permissivo do LangGraph será bloqueado em versões futuras).
"""

import importlib
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

STATE_MODULES = (
    "claims_agents.state.contracts",
    "claims_agents.state.global_state",
    "claims_agents.domain.enums",
    "claims_agents.domain.models",
    "claims_agents.agents.guardrails.state",
    "claims_agents.agents.triage.state",
    "claims_agents.agents.claim_notice.state",
    "claims_agents.agents.documents.state",
)


def state_type_allowlist() -> list[tuple[str, str]]:
    allowed: list[tuple[str, str]] = []
    for module_name in STATE_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module_name and issubclass(obj, BaseModel | Enum):
                allowed.append((module_name, name))
    return allowed


def make_serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=state_type_allowlist())


@asynccontextmanager
async def open_checkpointer(path: Path) -> AsyncIterator[AsyncSqliteSaver]:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(path)) as conn:
        yield AsyncSqliteSaver(conn, serde=make_serializer())
