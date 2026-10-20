"""Subagente de validação do segurado: pede o CPF, extrai e consulta `get_customer_data`."""

from __future__ import annotations

import re
from typing import Any

from claims_agents.agents.triage.state import TriageGraphState
from claims_agents.agents.triage.subagents.customer_validation.schemas import CpfExtraction
from claims_agents.core.errors import NotFound, ToolError
from claims_agents.core.messages import Messages
from claims_agents.core.privacy import is_valid_cpf, mask_cpf, only_digits
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import CustomerRef, StageResult
from claims_agents.tools.interfaces import GetCustomerData
from claims_agents.tools.schemas import GetCustomerDataRequest

NAME = "customer_validation"
CPF_CANDIDATE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")


def extract_cpf(text: str) -> CpfExtraction:
    for match in CPF_CANDIDATE.finditer(text):
        digits = only_digits(match.group())
        if is_valid_cpf(digits):
            return CpfExtraction(cpf=digits, valid=True)
    return CpfExtraction(cpf=None, valid=False)


def build(
    get_customer_data: GetCustomerData, messages: Messages, max_attempts: int
) -> NodeFn[TriageGraphState]:
    async def customer_validation(state: TriageGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        known_cpf = state.customer.cpf if state.customer and state.customer.cpf else None
        if sub.step == "start" and known_cpf:
            # segurado já identificado nesta conversa (ex.: numa consulta): não pede o CPF de novo
            sub.outcome["initial_text"] = state.text
        elif sub.step == "await_cpf" and known_cpf and not extract_cpf(state.text).valid:
            sub.outcome["initial_text"] = state.text
        if sub.step == "start" and not known_cpf:
            sub.step = "await_cpf"
            # relato espontâneo da 1ª mensagem (ex.: "Oi, bati o carro"), usado na classificação
            sub.outcome["initial_text"] = state.text
            return {
                "sub": sub,
                "awaiting_field": "cpf",
                "result": StageResult(
                    status="needs_input",
                    reason="CPF do titular solicitado",
                    user_message=messages.get("triage.ask_cpf"),
                ),
            }

        extraction = extract_cpf(state.text)
        if not extraction.valid and known_cpf:
            extraction = CpfExtraction(cpf=known_cpf, valid=True)
        if not extraction.valid or extraction.cpf is None:
            attempts = sub.attempts.get("cpf", 0) + 1
            sub.attempts["cpf"] = attempts
            emit(
                "field_invalid",
                subagent=NAME,
                status="warning",
                details=f"CPF não identificado (tentativa {attempts}/{max_attempts})",
            )
            if attempts >= max_attempts:
                return {
                    "sub": sub,
                    "result": StageResult(
                        status="failed", reason="Limite de tentativas para o CPF excedido"
                    ),
                }
            return {
                "sub": sub,
                "awaiting_field": "cpf",
                "result": StageResult(
                    status="needs_input",
                    reason="CPF inválido",
                    user_message=messages.get("triage.invalid_cpf"),
                ),
            }

        emit("field_extracted", subagent=NAME, details=f"CPF {mask_cpf(extraction.cpf)}")
        try:
            resp = await get_customer_data(GetCustomerDataRequest(cpf=extraction.cpf))
        except NotFound:
            # sem apólices: o subagente de decisão rejeita com a orientação configurada
            emit(
                "customer_not_found",
                subagent=NAME,
                status="warning",
                details=f"CPF {mask_cpf(extraction.cpf)} sem cadastro",
            )
            sub.step = "decide"
            sub.outcome |= {"policies": []}
            return {"sub": sub}
        except ToolError as exc:
            return {
                "sub": sub,
                "result": StageResult(
                    status="failed", reason=f"Falha ao consultar cliente: {type(exc).__name__}"
                ),
            }

        # identificado: entender o ocorrido; sem apólice, a decisão já orienta (não pergunta)
        sub.step = "classify" if resp.policies else "decide"
        sub.outcome |= {"policies": [p.model_dump(mode="json") for p in resp.policies]}
        return {
            "sub": sub,
            "customer": CustomerRef(
                id=resp.customer.id, name=resp.customer.name, cpf=extraction.cpf
            ),
        }

    return customer_validation
