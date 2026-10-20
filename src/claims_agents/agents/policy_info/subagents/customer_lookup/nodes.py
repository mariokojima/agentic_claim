"""Subagente de identificação do segurado: usa o cliente da conversa ou pede o CPF."""

from __future__ import annotations

from typing import Any

from claims_agents.agents.policy_info.state import PolicyInfoGraphState
from claims_agents.agents.policy_info.subagents.answer.nodes import POLICY_TOPICS
from claims_agents.agents.triage.subagents.customer_validation.nodes import extract_cpf
from claims_agents.core.errors import NotFound, ToolError
from claims_agents.core.messages import Messages
from claims_agents.core.privacy import mask_cpf
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import CustomerRef
from claims_agents.tools.interfaces import GetCustomerData
from claims_agents.tools.schemas import GetCustomerDataRequest

NAME = "customer_lookup"


def build(get_customer_data: GetCustomerData, messages: Messages) -> NodeFn[PolicyInfoGraphState]:
    async def customer_lookup(state: PolicyInfoGraphState) -> dict[str, Any]:
        cpf = state.customer.cpf if state.customer and state.customer.cpf else None
        if cpf is None and state.awaiting_cpf:
            extraction = extract_cpf(state.text)
            if not extraction.valid:
                return {"answer": messages.get("policy_info.invalid_cpf"), "ask_cpf": True}
            cpf = extraction.cpf
        if cpf is None and state.topic not in POLICY_TOPICS:
            return {}  # pergunta livre: não pede CPF
        if cpf is None:
            emit("cpf_requested", subagent=NAME, details="CPF necessário para consultar a apólice")
            return {"answer": messages.get("policy_info.ask_cpf"), "ask_cpf": True}
        try:
            resp = await get_customer_data(GetCustomerDataRequest(cpf=cpf))
        except NotFound:
            emit(
                "customer_not_found",
                subagent=NAME,
                status="warning",
                details=f"CPF {mask_cpf(cpf)} sem cadastro",
            )
            return {"answer": messages.get("policy_info.not_found")}
        except ToolError:
            return {"answer": messages.get("policy_info.unavailable")}
        emit("policies_loaded", subagent=NAME, details=f"{len(resp.policies)} apólice(s)")
        identified = CustomerRef(id=resp.customer.id, name=resp.customer.name, cpf=cpf)
        return {
            "policies": [p.model_dump(mode="json") for p in resp.policies],
            "identified": identified,
        }

    return customer_lookup
