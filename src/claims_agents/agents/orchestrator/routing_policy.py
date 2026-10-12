"""Política de roteamento do Orquestrador: tabela fixa `claim_stage → especialista`."""

from __future__ import annotations

from pydantic import BaseModel

from claims_agents.domain import ClaimStage
from claims_agents.state import Awaiting

STAGE_TO_SPECIALIST: dict[ClaimStage, str] = {
    ClaimStage.TRIAGEM: "triage",
    ClaimStage.AVISO: "claim_notice",
    ClaimStage.DOCUMENTOS: "documents",
}


class RoutingDecision(BaseModel):
    target: str
    reason: str
    intent: str | None = None


def route(stage: ClaimStage, awaiting: Awaiting | None) -> RoutingDecision:
    target = STAGE_TO_SPECIALIST.get(stage)
    if target is None:
        raise ValueError(f"Etapa sem especialista: {stage}")
    if awaiting is not None and awaiting.stage == stage.value:
        reason = f"Resposta à pergunta pendente '{awaiting.field}' da etapa {stage.value}"
    else:
        reason = f"Tabela de roteamento: {stage.value} → {target}"
    return RoutingDecision(target=target, reason=reason)
