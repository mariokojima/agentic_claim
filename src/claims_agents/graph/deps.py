"""Dependências injetadas na construção do grafo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from claims_agents.core.llm import LLMClient
from claims_agents.core.messages import Messages, load_messages
from claims_agents.core.settings import Settings, load_config
from claims_agents.graph.control import PauseControl
from claims_agents.tools.registry import ToolRegistry


@dataclass
class GraphDeps:
    registry: ToolRegistry
    settings: Settings
    control: PauseControl = field(default_factory=PauseControl)
    messages: Messages = field(default_factory=load_messages)
    guardrails_config: dict[str, Any] = field(default_factory=lambda: load_config("guardrails"))
    triage_rules: dict[str, Any] = field(default_factory=lambda: load_config("triage_rules"))
    checklist: dict[str, Any] = field(default_factory=lambda: load_config("documents_checklist"))
    # LLM injetado explicitamente (None = só regras; testes usam FakeLLMClient)
    llm: LLMClient | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
