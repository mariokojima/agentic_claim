"""Subagente de registro: chama `open_claim` e gera o protocolo (determinístico)."""

from __future__ import annotations

from typing import Any

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.event_data_collection.nodes import describe_when
from claims_agents.agents.claim_notice.subagents.registration.schemas import RegistrationOutcome
from claims_agents.core.errors import ToolError
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.domain import ClaimEventData
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult
from claims_agents.tools.interfaces import OpenClaim
from claims_agents.tools.schemas import OpenClaimRequest

NAME = "registration"


def build(open_claim: OpenClaim, messages: Messages) -> NodeFn[NoticeGraphState]:
    async def registration(state: NoticeGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        customer = state.customer
        if customer is None or customer.policy_number is None:
            return {
                "sub": sub,
                "result": StageResult(
                    status="failed", reason="Segurado/apólice ausentes no registro"
                ),
            }
        event = ClaimEventData.model_validate(
            {k: v for k, v in sub.event.items() if k in ClaimEventData.model_fields}
        )
        try:
            resp = await open_claim(
                OpenClaimRequest(
                    customer_id=customer.id, policy_number=customer.policy_number, event=event
                )
            )
        except ToolError as exc:
            return {
                "sub": sub,
                "result": StageResult(
                    status="failed", reason=f"Falha ao registrar aviso: {type(exc).__name__}"
                ),
            }
        outcome = RegistrationOutcome(protocol=resp.protocol, opened_at=resp.opened_at.isoformat())
        sub.step = "done"
        emit(
            "claim_opened",
            subagent=NAME,
            details=f"Protocolo {resp.protocol}",
            data=outcome.model_dump(),
        )
        return {
            "sub": sub,
            "protocol": resp.protocol,
            "result": StageResult(
                status="completed",
                reason="Aviso registrado",
                payload=outcome.model_dump(),
                user_message=messages.get(
                    "notice.registered",
                    protocol=resp.protocol,
                    when=describe_when(sub.event),
                    location=event.location,
                    damages=event.damages or "não informados",
                )
                + "\n"
                + _coverage_line(sub.event.get("coverage") or {}, messages),
            ),
        }

    return registration


def _coverage_line(coverage: dict[str, Any], messages: Messages) -> str:
    third = coverage.get("third_party_coverage")
    extra = (
        ""
        if third is None
        else messages.get("notice.third_party_" + ("included" if third else "not_included"))
    )
    return messages.get("notice.coverage", third_party=extra)
