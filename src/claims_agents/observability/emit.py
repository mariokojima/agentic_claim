"""Emissão de eventos de domínio a partir dos nós (via stream `custom` do LangGraph).

Os nós nunca gravam no event store: apenas escrevem no stream; o adaptador normaliza e persiste.
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from claims_agents.observability.events import EventStatus
from claims_agents.tools.resilience import ToolCallRecord

CUSTOM_KIND = "agent_event"


def emit(
    event: str,
    *,
    agent: str | None = None,
    details: str = "",
    status: EventStatus = "completed",
    subagent: str | None = None,
    tool: str | None = None,
    latency_ms: int | None = None,
    tokens: int | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Escreve um evento no stream. Fora de uma execução do grafo, é no-op."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer(
        {
            "kind": CUSTOM_KIND,
            "event": event,
            "agent": agent,
            "details": details,
            "status": status,
            "subagent": subagent,
            "tool": tool,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "data": data or {},
        }
    )


def tool_observer(record: ToolCallRecord) -> None:
    """Observer do `ResilientTool`: converte cada chamada de tool em evento `tool_call`."""
    details = f"{record.attempts} tentativa(s)"
    if record.error:
        details += f" — {record.error}"
    emit(
        "tool_call",
        tool=record.tool,
        status=record.status,
        latency_ms=record.latency_ms,
        details=details,
        data={"attempts": record.attempts},
    )
