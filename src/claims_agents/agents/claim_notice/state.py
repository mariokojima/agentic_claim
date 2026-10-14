"""Estado do subgrafo de Aviso de Sinistro."""

from pydantic import BaseModel, Field

from claims_agents.state import CustomerRef, NoticeState, StageResult


class NoticeGraphState(BaseModel):
    # entrada
    text: str = ""
    prior_text: str = ""  # relato do ocorrido já feito na Triagem
    customer: CustomerRef | None = None
    sub: NoticeState = Field(default_factory=NoticeState)
    # saída
    protocol: str | None = None
    result: StageResult | None = None
    awaiting_field: str | None = None
