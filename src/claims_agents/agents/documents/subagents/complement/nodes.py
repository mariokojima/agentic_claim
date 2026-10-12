"""Subagente de complementação: decide entre concluir (critério de saída) e pedir complemento."""

from __future__ import annotations

from typing import Any

from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.documents.subagents.checklist.nodes import pending_items
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "complement"


def build(messages: Messages) -> NodeFn[DocumentsGraphState]:
    def complement(state: DocumentsGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        missing_type = messages.get("documents.missing_type")
        problems = [f"• {d.filename}: {'; '.join(d.issues)}" for d in state.batch if not d.valid]
        problems += [f"• {s.filename}: {missing_type}" for s in state.stored if s.doc_type is None]
        pending = pending_items(sub.requirements, sub.received)
        if not pending:
            sub.step = "done"
            received = "\n".join(
                f"• {d.doc_type.value}: {d.filename}" for d in sub.received if d.valid
            )
            emit(
                "exit_criteria_met",
                subagent=NAME,
                details="Todos os documentos obrigatórios validados",
            )
            return {
                "sub": sub,
                "result": StageResult(
                    status="completed",
                    reason="Documentos obrigatórios validados",
                    payload={
                        "documents": [d.model_dump(mode="json") for d in sub.received if d.valid]
                    },
                    user_message=messages.get(
                        "documents.done", protocol=state.protocol, received=received
                    ),
                ),
            }
        parts = []
        if problems:
            parts.append(messages.get("documents.issues", issues="\n".join(problems)))
        parts.append(messages.get("documents.pending", items="\n".join(pending)))
        emit(
            "complement_requested",
            subagent=NAME,
            status="warning",
            details=f"{len(pending)} pendência(s), {len(problems)} problema(s)",
        )
        return {
            "sub": sub,
            "awaiting_field": "documents",
            "result": StageResult(
                status="needs_input",
                reason="Documentos pendentes",
                payload={"pending": pending},
                user_message="\n\n".join(parts),
            ),
        }

    return complement
