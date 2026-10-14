from pydantic import BaseModel


class EventClassification(BaseModel):
    """Resultado da classificação do ocorrido (regras na Fase 1-2; LLM a partir da Fase 3)."""

    event_type: str | None  # categoria de configs/triage_rules.yaml; None = não entendido
    label: str | None = None
    matched: str | None = None  # trecho que justificou a classificação (auditoria)
    has_injuries: bool = False
