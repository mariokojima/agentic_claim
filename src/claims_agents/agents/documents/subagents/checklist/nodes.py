"""Subagente de checklist: calcula os documentos exigidos para o tipo de sinistro (config)."""

from __future__ import annotations

from typing import Any

from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.documents.subagents.checklist.schemas import Requirement
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import ReceivedDocument, StageResult

NAME = "checklist"


def requirements_for(
    checklist: dict[str, Any], claim_type: str, event: dict[str, Any]
) -> list[Requirement]:
    reqs: list[Requirement] = []
    for item in checklist.get(claim_type, []):
        required = item.get("required")
        if required == "conditional":
            required = any(event.get(flag) for flag in item.get("required_if_any", []))
        if required:
            reqs.append(
                Requirement(
                    doc_type=item["doc_type"],
                    label=item["label"],
                    min_count=item.get("min_count", 1),
                )
            )
    return reqs


def pending_items(requirements: dict[str, Any], received: list[ReceivedDocument]) -> list[str]:
    """Lista legível do que falta, considerando apenas documentos válidos."""
    items: list[str] = []
    for doc_type, req in requirements.items():
        valid = sum(1 for d in received if d.valid and d.doc_type.value == doc_type)
        missing = req["min_count"] - valid
        if missing > 0:
            suffix = f" (faltam {missing} de {req['min_count']})" if req["min_count"] > 1 else ""
            items.append(f"• {req['label']}{suffix}")
    return items


def build(
    checklist: dict[str, Any], messages: Messages, claim_type: str = "COLISAO"
) -> NodeFn[DocumentsGraphState]:
    def checklist_node(state: DocumentsGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        if sub.step != "start":
            return {}
        reqs = requirements_for(checklist, claim_type, state.event)
        sub.requirements = {r.doc_type: r.model_dump() for r in reqs}
        sub.step = "await_documents"
        emit(
            "checklist_defined",
            subagent=NAME,
            details=", ".join(f"{r.label} x{r.min_count}" for r in reqs),
            data={"requirements": sub.requirements},
        )
        items = pending_items(sub.requirements, sub.received)
        return {
            "sub": sub,
            "awaiting_field": "documents",
            "result": StageResult(
                status="needs_input",
                reason="Documentos solicitados",
                user_message=messages.get("documents.request", items="\n".join(items)),
            ),
        }

    return checklist_node
