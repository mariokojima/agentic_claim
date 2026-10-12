"""Helpers para conversas roteirizadas nos testes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claims_agents.domain import Customer, DocumentType
from claims_agents.state import Inbound, InboundAttachment

JPEG = b"\xff\xd8\xff" + b"0" * 4096
PDF = b"%PDF-1.4\n" + b"0" * 4096


def attachment(
    tmp: Path,
    doc_type: DocumentType | None,
    metadata: dict[str, Any],
    *,
    idx: int = 0,
    mime: str | None = None,
    content: bytes | None = None,
) -> InboundAttachment:
    is_photo = doc_type == DocumentType.FOTO_DANO
    mime = mime or ("image/jpeg" if is_photo else "application/pdf")
    tag = f"{doc_type}:{idx}:{uuid.uuid4().hex}".encode()
    data = content if content is not None else (JPEG if is_photo else PDF) + tag
    ext = "jpg" if "jpeg" in mime else "pdf"
    name = f"{(doc_type.value if doc_type else 'arquivo').lower()}_{idx}.{ext}"
    path = tmp / f"{uuid.uuid4().hex}_{name}"
    path.write_bytes(data)
    return InboundAttachment(
        upload_id=uuid.uuid4().hex,
        filename=name,
        mime_type=mime,
        size_bytes=len(data),
        path=str(path),
        doc_type=doc_type,
        metadata=metadata,
    )


def full_document_set(tmp: Path, customer: Customer, plate: str) -> list[InboundAttachment]:
    today = datetime.now(UTC).isoformat()
    docs = [
        attachment(tmp, DocumentType.CNH, {"cpf": customer.cpf}),
        attachment(tmp, DocumentType.CRLV, {"plate": plate}),
    ]
    docs += [
        attachment(tmp, DocumentType.FOTO_DANO, {"captured_at": today}, idx=i) for i in range(3)
    ]
    return docs


def text(t: str, attachments: list[InboundAttachment] | None = None) -> Inbound:
    return Inbound(text=t, attachments=attachments or [])
