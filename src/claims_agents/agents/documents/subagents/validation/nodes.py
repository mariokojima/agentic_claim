"""Subagente de validação: chama `validate_document` para cada arquivo armazenado no turno."""

from __future__ import annotations

from datetime import date
from typing import Any

from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.documents.subagents.validation.schemas import BatchValidation
from claims_agents.core.errors import ToolError
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.domain import DocumentType
from claims_agents.observability.emit import emit
from claims_agents.state import ReceivedDocument, StageResult
from claims_agents.tools.interfaces import ValidateDocument
from claims_agents.tools.schemas import ValidateDocumentRequest, ValidationContext

NAME = "validation"


def build(validate_document: ValidateDocument, messages: Messages) -> NodeFn[DocumentsGraphState]:
    async def validation(state: DocumentsGraphState) -> dict[str, Any]:
        assert state.protocol is not None
        event_date = state.event.get("event_date")
        ctx = ValidationContext(
            protocol=state.protocol,
            customer_cpf=state.customer.cpf if state.customer else None,
            vehicle_plate=state.customer.vehicle_plate if state.customer else None,
            event_date=date.fromisoformat(event_date) if event_date else None,
        )
        batch: list[ReceivedDocument] = []
        for item in state.stored:
            if item.doc_type is None:
                emit(
                    "document_invalid",
                    subagent=NAME,
                    status="warning",
                    details=f"{item.filename}: tipo não informado",
                )
                continue
            doc_type = DocumentType(item.doc_type)
            try:
                resp = await validate_document(
                    ValidateDocumentRequest(file_id=item.file_id, doc_type=doc_type, context=ctx)
                )
            except ToolError as exc:
                return {
                    "result": StageResult(
                        status="failed", reason=f"Falha ao validar documento: {type(exc).__name__}"
                    )
                }
            issues = [i.message for i in resp.issues]
            batch.append(
                ReceivedDocument(
                    file_id=item.file_id,
                    filename=item.filename,
                    doc_type=doc_type,
                    valid=resp.valid,
                    issues=issues,
                )
            )
            emit(
                "document_validated" if resp.valid else "document_invalid",
                subagent=NAME,
                status="completed" if resp.valid else "warning",
                details=f"{doc_type.value} {item.filename}: "
                + ("válido" if resp.valid else "; ".join(issues)),
            )
        untyped = [s.filename for s in state.stored if s.doc_type is None]
        summary = BatchValidation(
            valid=sum(d.valid for d in batch),
            invalid=sum(not d.valid for d in batch) + len(untyped),
        )
        sub = state.sub.model_copy(deep=True)
        sub.received = [*sub.received, *batch]
        emit(
            "batch_validated",
            subagent=NAME,
            details=f"{summary.valid} válido(s), {summary.invalid} com problema",
            data=summary.model_dump(),
        )
        return {"sub": sub, "batch": batch}

    return validation
