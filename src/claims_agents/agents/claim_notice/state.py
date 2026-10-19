"""Estado do subgrafo de Aviso de Sinistro."""

from pydantic import BaseModel, Field

from claims_agents.state import CustomerRef, NoticeState, StageResult


class NoticeGraphState(BaseModel):
    # entrada
    text: str = ""
    prior_text: str = ""  # relato do ocorrido já feito na Triagem
    parties: dict[str, bool] = Field(default_factory=dict)  # has_third_parties / has_injuries
    known_what: str = ""  # ocorrido já entendido na Triagem (ex.: "colisão")
    coverages: list[str] = Field(default_factory=list)  # coberturas da apólice escolhida
    customer: CustomerRef | None = None
    sub: NoticeState = Field(default_factory=NoticeState)
    # saída
    protocol: str | None = None
    result: StageResult | None = None
    awaiting_field: str | None = None
