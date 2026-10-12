"""Estado do subgrafo de Triagem (contrato de entrada e saída do especialista)."""

from pydantic import BaseModel, Field

from claims_agents.state import CustomerRef, StageResult, TriageState


class TriageGraphState(BaseModel):
    # entrada
    text: str = ""
    phone: str | None = None
    sub: TriageState = Field(default_factory=TriageState)
    # saída
    customer: CustomerRef | None = None
    result: StageResult | None = None
    awaiting_field: str | None = None
