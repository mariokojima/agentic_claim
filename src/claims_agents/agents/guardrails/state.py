"""Estado do subgrafo de Guardrails (reutilizado na entrada e na saída)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from claims_agents.state import GuardrailCheck, GuardrailVerdict


class GuardrailGraphState(BaseModel):
    direction: Literal["input", "output"]
    text: str
    context: dict[str, Any] = Field(default_factory=dict)
    security: GuardrailCheck | None = None
    ethics: GuardrailCheck | None = None
    corporate: GuardrailCheck | None = None
    verdict: GuardrailVerdict | None = None
