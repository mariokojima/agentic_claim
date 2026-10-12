"""Contratos entre especialistas e o grafo principal."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StageStatus = Literal["completed", "needs_input", "rejected", "failed"]
GuardrailDecision = Literal["allow", "sanitize", "block", "escalate"]


class StageResult(BaseModel):
    """Retorno de cada especialista. É o único contrato que o especialista conhece."""

    model_config = ConfigDict(extra="forbid")

    status: StageStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    user_message: str | None = None


class Awaiting(BaseModel):
    """Pergunta pendente ao cliente: etapa e campo aguardado."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    field: str
    attempts: int = 0


class GuardrailCheck(BaseModel):
    """Resultado de um estágio de guardrail (segurança, ética ou corporativo)."""

    model_config = ConfigDict(extra="forbid")

    stage: Literal["security", "ethics", "corporate"]
    decision: GuardrailDecision
    reason: str
    rule: str | None = None
    sanitized_text: str | None = None


class GuardrailVerdict(BaseModel):
    """Veredito agregado de um ponto de guardrail."""

    model_config = ConfigDict(extra="forbid")

    direction: Literal["input", "output"]
    decision: GuardrailDecision
    reason: str
    checks: list[GuardrailCheck] = Field(default_factory=list)
    text: str | None = None  # texto final (sanitizado quando aplicável)
