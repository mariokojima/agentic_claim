"""Estado do subgrafo Consultas (perguntas sobre a apólice e dúvidas gerais de seguro)."""

from typing import Any

from pydantic import BaseModel, Field

from claims_agents.state import CustomerRef


class PolicyInfoGraphState(BaseModel):
    # entrada
    text: str = ""  # mensagem atual (pergunta ou, se aguardando, o CPF)
    pending_query: str = ""  # pergunta guardada enquanto o CPF é pedido
    awaiting_cpf: bool = False
    customer: CustomerRef | None = None
    # trabalho
    question: str = ""
    topic: str | None = None  # coberturas | renovacao | vencimento | vigencia | dados_apolice | faq
    faq_id: str | None = None
    coverage_asked: str | None = None
    policies: list[dict[str, Any]] = Field(default_factory=list)
    # saída
    answer: str | None = None
    ask_cpf: bool = False
    identified: CustomerRef | None = None
    source: str = "regras"
