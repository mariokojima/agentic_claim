"""Subagente de recepção e armazenamento: grava os anexos do turno via `store_files`."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from claims_agents.agents.documents.state import DocumentsGraphState, StoredUpload
from claims_agents.agents.documents.subagents.checklist.nodes import pending_items
from claims_agents.agents.documents.subagents.intake_storage.schemas import IntakeSummary
from claims_agents.core.errors import ToolError
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeFn
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult
from claims_agents.tools.interfaces import StoreFiles
from claims_agents.tools.schemas import FileUpload, StoreFilesRequest

NAME = "intake_storage"


def build(store_files: StoreFiles, messages: Messages) -> NodeFn[DocumentsGraphState]:
    async def intake_storage(state: DocumentsGraphState) -> dict[str, Any]:
        if not state.attachments:
            items = pending_items(state.sub.requirements, state.sub.received)
            return {
                "awaiting_field": "documents",
                "result": StageResult(
                    status="needs_input",
                    reason="Nenhum anexo recebido",
                    user_message=messages.get("documents.reminder", items="\n".join(items)),
                ),
            }
        if state.protocol is None:
            return {"result": StageResult(status="failed", reason="Protocolo ausente")}
        uploads = [
            FileUpload(
                filename=a.filename,
                mime_type=a.mime_type,
                content=await asyncio.to_thread(Path(a.path).read_bytes),
                doc_type=a.doc_type,
                metadata=a.metadata,
            )
            for a in state.attachments
        ]
        try:
            resp = await store_files(StoreFilesRequest(protocol=state.protocol, files=uploads))
        except ToolError as exc:
            return {
                "result": StageResult(
                    status="failed", reason=f"Falha ao armazenar arquivos: {type(exc).__name__}"
                )
            }
        stored = [
            StoredUpload(
                file_id=f.file_id,
                filename=f.filename,
                doc_type=a.doc_type.value if a.doc_type else None,
            )
            for f, a in zip(resp.files, state.attachments, strict=True)
        ]
        summary = IntakeSummary(
            received=len(uploads),
            stored=len(stored),
            untyped=sum(s.doc_type is None for s in stored),
        )
        emit(
            "files_stored",
            subagent=NAME,
            details=f"{summary.stored} arquivo(s) armazenado(s)",
            data=summary.model_dump(),
        )
        return {"stored": stored}

    return intake_storage
