"""Subagente de complementação: decide entre concluir (critério de saída, ADR-0004) e pedir
complemento. Informa o que já foi validado e, ao concluir, envia a confirmação final com
protocolo, resumo do aviso, documentos recebidos e próximos passos."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.documents.subagents.checklist.nodes import pending_items
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import ReceivedDocument, StageResult

NAME = "complement"


def doc_labels(checklist: dict[str, Any], claim_type: str = "COLISAO") -> dict[str, str]:
    return {item["doc_type"]: item["label"] for item in checklist.get(claim_type, [])}


def received_lines(received: list[ReceivedDocument], labels: dict[str, str]) -> list[str]:
    """Documentos válidos agrupados por tipo, na ordem do checklist (ex.: "Fotos dos danos (3)")."""
    counts = Counter(d.doc_type.value for d in received if d.valid)
    order = [t for t in labels if t in counts] + [t for t in counts if t not in labels]
    return [f"• {labels.get(t, t)}" + (f" ({counts[t]})" if counts[t] > 1 else "") for t in order]


def event_summary(event: dict[str, Any]) -> str:
    parts = []
    if event.get("event_date"):
        when = date.fromisoformat(str(event["event_date"])).strftime("%d/%m/%Y")
        if event.get("event_time"):
            when += f" às {str(event['event_time'])[:5]}"
        parts.append(when)
    if event.get("location"):
        parts.append(str(event["location"]))
    summary = " — ".join(parts)
    if event.get("damages"):
        summary += f". Danos: {event['damages']}"
    return summary or "colisão"


def build(messages: Messages, checklist: dict[str, Any]) -> NodeFn[DocumentsGraphState]:
    labels = doc_labels(checklist)

    def complement(state: DocumentsGraphState) -> dict[str, Any]:
        sub = state.sub.model_copy(deep=True)
        missing_type = messages.get("documents.missing_type")
        problems = [f"• {d.filename}: {'; '.join(d.issues)}" for d in state.batch if not d.valid]
        problems += [f"• {s.filename}: {missing_type}" for s in state.stored if s.doc_type is None]
        pending = pending_items(sub.requirements, sub.received)
        validated = received_lines(sub.received, labels)
        if not pending:
            sub.step = "done"
            emit(
                "exit_criteria_met",
                subagent=NAME,
                details=f"Todos os documentos obrigatórios validados ({len(validated)} tipo(s))",
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
                        "documents.done",
                        protocol=state.protocol,
                        summary=event_summary(state.event),
                        received="\n".join(validated),
                    ),
                ),
            }
        parts = []
        if problems:
            parts.append(messages.get("documents.issues", issues="\n".join(problems)))
        if validated and state.batch:
            parts.append(messages.get("documents.validated", items="\n".join(validated)))
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
