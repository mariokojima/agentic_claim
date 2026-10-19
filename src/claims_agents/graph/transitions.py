"""Transição de etapa — ÚNICO módulo que altera `claim_stage`."""

from __future__ import annotations

from pydantic import BaseModel

from claims_agents.domain import ClaimStage
from claims_agents.state import GuardrailDecision, StageResult

NEXT_ON_COMPLETED: dict[ClaimStage, ClaimStage] = {
    ClaimStage.TRIAGEM: ClaimStage.AVISO,
    ClaimStage.AVISO: ClaimStage.DOCUMENTOS,
    ClaimStage.DOCUMENTOS: ClaimStage.CONCLUIDO,
}
NEXT_ON_REJECTED: dict[ClaimStage, ClaimStage] = {
    ClaimStage.TRIAGEM: ClaimStage.ORIENTADO,
    ClaimStage.AVISO: ClaimStage.ORIENTADO,
    ClaimStage.DOCUMENTOS: ClaimStage.ESCALADO_HUMANO,
}


class TransitionOutcome(BaseModel):
    new_stage: ClaimStage
    reason: str
    next_node: str  # "orchestrator" (nova etapa na mesma rodada) | "guardrails_out"
    message_key: str | None = None  # mensagem fixa a enfileirar (messages.yaml)
    reask: bool = False  # repetir a pergunta pendente após recusar a mensagem
    terminal_reason: str | None = None

    def changed(self, old: ClaimStage) -> bool:
        return self.new_stage != old


def decide_transition(
    stage: ClaimStage,
    result: StageResult | None,
    input_decision: GuardrailDecision | None,
    hops: int,
    max_hops: int,
    input_blocks: int = 0,
    block_limit: int = 1,
) -> TransitionOutcome:
    """Função pura: decide a próxima etapa a partir do resultado do turno.

    `input_blocks` é o número de recusas anteriores na conversa; a recusa atual conta +1.
    """
    if input_decision == "block":
        if input_blocks + 1 >= block_limit:
            return TransitionOutcome(
                new_stage=ClaimStage.BLOQUEADO,
                reason=f"Guardrail de entrada bloqueou ({input_blocks + 1}/{block_limit} recusas)",
                next_node="guardrails_out",
                message_key="transition.blocked",
                terminal_reason="guardrail_block",
            )
        return TransitionOutcome(
            new_stage=stage,
            reason=f"Mensagem recusada pelo guardrail ({input_blocks + 1}/{block_limit})",
            next_node="guardrails_out",
            message_key="transition.refused",
            reask=True,
        )
    if input_decision == "escalate":
        return TransitionOutcome(
            new_stage=ClaimStage.ESCALADO_HUMANO,
            reason="Guardrail de entrada escalou",
            next_node="guardrails_out",
            message_key="transition.escalated",
            terminal_reason="guardrail_escalate",
        )
    if result is None:
        return TransitionOutcome(
            new_stage=stage, reason="Sem resultado de especialista", next_node="guardrails_out"
        )
    if result.status == "needs_input":
        return TransitionOutcome(
            new_stage=stage,
            reason=f"Aguardando cliente: {result.reason}",
            next_node="guardrails_out",
        )
    if result.status == "failed" and result.payload.get("escalated_by"):
        return TransitionOutcome(
            new_stage=ClaimStage.ESCALADO_HUMANO,
            reason=result.reason,
            next_node="guardrails_out",
            message_key="transition.escalated",
            terminal_reason=str(result.payload["escalated_by"]),
        )
    if result.status == "failed":
        return TransitionOutcome(
            new_stage=ClaimStage.ESCALADO_HUMANO,
            reason=result.reason,
            next_node="guardrails_out",
            message_key="transition.failed",
            terminal_reason=f"failed:{stage.value}",
        )
    if result.status == "rejected":
        new = NEXT_ON_REJECTED[stage]
        return TransitionOutcome(
            new_stage=new,
            reason=result.reason,
            next_node="guardrails_out",
            terminal_reason=f"rejected:{result.reason}",
        )
    new = NEXT_ON_COMPLETED[stage]
    if new.is_terminal:
        return TransitionOutcome(
            new_stage=new,
            reason=result.reason,
            next_node="guardrails_out",
            terminal_reason="completed",
        )
    if hops + 1 > max_hops:
        return TransitionOutcome(
            new_stage=ClaimStage.ESCALADO_HUMANO,
            reason=f"Limite de {max_hops} saltos por rodada excedido",
            next_node="guardrails_out",
            message_key="transition.failed",
            terminal_reason="max_hops",
        )
    return TransitionOutcome(new_stage=new, reason=result.reason, next_node="orchestrator")
