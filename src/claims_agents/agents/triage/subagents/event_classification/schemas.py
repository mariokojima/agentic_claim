from typing import Literal

from pydantic import BaseModel


class EventClassification(BaseModel):
    """Resultado da classificação do ocorrido (regras na Fase 1-2; LLM a partir da Fase 3)."""

    event_type: str | None  # categoria de configs/triage_rules.yaml; None = não entendido
    label: str | None = None
    matched: str | None = None  # trecho que justificou a classificação (auditoria)
    has_injuries: bool = False
    has_third_parties: bool | None = None
    injuries_hint: bool | None = None  # só do LLM (entende negativas)
    source: Literal["regras", "llm"] = "regras"


class LLMEventClassification(BaseModel):
    """Saída estruturada pedida ao LLM (prompts/triage/event_classification.md)."""

    event_type: Literal[
        "COLISAO",
        "ROUBO_FURTO",
        "INCENDIO",
        "FENOMENO_NATURAL",
        "VIDROS",
        "ASSISTENCIA",
        "NAO_SINISTRO",
        "INDEFINIDO",
    ]
    has_third_parties: bool | None
    has_injuries: bool | None
    justification: str
