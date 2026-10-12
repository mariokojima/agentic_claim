"""Estado do subgrafo de Documentos e Evidências."""

from typing import Any

from pydantic import BaseModel, Field

from claims_agents.state import (
    CustomerRef,
    DocumentsState,
    InboundAttachment,
    ReceivedDocument,
    StageResult,
)


class StoredUpload(BaseModel):
    file_id: str
    filename: str
    doc_type: str | None


class DocumentsGraphState(BaseModel):
    # entrada
    attachments: list[InboundAttachment] = Field(default_factory=list)
    protocol: str | None = None
    customer: CustomerRef | None = None
    event: dict[str, Any] = Field(default_factory=dict)
    sub: DocumentsState = Field(default_factory=DocumentsState)
    # trabalho do turno
    stored: list[StoredUpload] = Field(default_factory=list)
    batch: list[ReceivedDocument] = Field(default_factory=list)
    # saída
    result: StageResult | None = None
    awaiting_field: str | None = None
