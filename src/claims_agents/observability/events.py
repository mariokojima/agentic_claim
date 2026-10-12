"""Modelo de evento do painel (`AgentEvent`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventStatus = Literal["completed", "processing", "warning", "error"]

# Rótulos pt-BR dos nós do grafo principal (o frontend usa os mesmos ids).
AGENT_LABELS: dict[str, str] = {
    "receive": "Mensagem WhatsApp",
    "guardrails_in": "Guardrails (entrada)",
    "orchestrator": "Orquestrador",
    "triage": "Triagem",
    "claim_notice": "Aviso de Sinistro",
    "documents": "Documentos",
    "transition": "Transição de etapa",
    "guardrails_out": "Guardrails (saída)",
    "send": "Envio WhatsApp",
}


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    conversation_id: str
    agent: str
    subagent: str | None = None
    event: str
    details: str = ""
    status: EventStatus = "completed"
    tool: str | None = None
    latency_ms: int | None = None
    tokens: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)  # dados estruturados (ex.: from/to da etapa)
