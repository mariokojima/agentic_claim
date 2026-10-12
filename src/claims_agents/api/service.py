"""Serviço da aplicação: conversas, anexos e execução de turnos com publicação de eventos."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.errors import ClaimsAgentsError
from claims_agents.core.settings import Settings
from claims_agents.domain import DocumentType
from claims_agents.graph.control import PauseControl
from claims_agents.graph.runner import TurnResult, get_state, run_turn
from claims_agents.observability.bus import EventBus
from claims_agents.observability.events import AgentEvent
from claims_agents.observability.metrics import Metrics, compute_metrics
from claims_agents.observability.store import EventStore
from claims_agents.state import GlobalState, Inbound, InboundAttachment


class ConversationNotFound(ClaimsAgentsError):  # noqa: N818
    pass


class UploadNotFound(ClaimsAgentsError):  # noqa: N818
    pass


@dataclass
class ChatService:
    settings: Settings
    graph: CompiledStateGraph[Any, Any, Any, Any]
    store: EventStore
    bus: EventBus
    control: PauseControl
    _locks: dict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))
    _uploads: dict[str, InboundAttachment] = field(default_factory=dict)

    # --- conversas ---

    def create_conversation(self, phone: str) -> str:
        conversation_id = f"conv_{uuid.uuid4().hex[:10]}"
        self.store.add_conversation(conversation_id, phone, datetime.now(UTC))
        return conversation_id

    def phone_of(self, conversation_id: str) -> str:
        conv = self.store.get_conversation(conversation_id)
        if conv is None:
            raise ConversationNotFound(conversation_id)
        return conv["phone"]

    async def state_of(self, conversation_id: str) -> GlobalState | None:
        self.phone_of(conversation_id)
        return await get_state(self.graph, conversation_id)

    # --- anexos ---

    async def save_upload(
        self,
        conversation_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
        doc_type: DocumentType | None,
        metadata: dict[str, Any] | None = None,
        simulate_metadata: bool = True,
    ) -> InboundAttachment:
        self.phone_of(conversation_id)
        upload_id = uuid.uuid4().hex[:12]
        folder = self.settings.storage_path / "inbox" / conversation_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{upload_id}_{Path(filename).name}"
        await asyncio.to_thread(path.write_bytes, content)
        meta = dict(metadata or {})
        if simulate_metadata:
            meta = await self._simulated_metadata(conversation_id, doc_type) | meta
        att = InboundAttachment(
            upload_id=upload_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            path=str(path),
            doc_type=doc_type,
            metadata=meta,
        )
        self._uploads[upload_id] = att
        return att

    async def _simulated_metadata(
        self, conversation_id: str, doc_type: DocumentType | None
    ) -> dict[str, Any]:
        """Simula os metadados que um OCR/EXIF extrairia (apenas dados sintéticos do processo)."""
        state = await get_state(self.graph, conversation_id)
        customer = state.customer if state else None
        if doc_type == DocumentType.CNH and customer and customer.cpf:
            return {"cpf": customer.cpf}
        if doc_type == DocumentType.CRLV and customer and customer.vehicle_plate:
            return {"plate": customer.vehicle_plate}
        if doc_type == DocumentType.FOTO_DANO:
            return {"captured_at": datetime.now(UTC).isoformat()}
        return {}

    # --- turnos ---

    async def handle_message(
        self, conversation_id: str, text: str, attachment_ids: list[str] | None = None
    ) -> TurnResult:
        phone = self.phone_of(conversation_id)
        attachments = []
        for upload_id in attachment_ids or []:
            if upload_id not in self._uploads:
                raise UploadNotFound(upload_id)
            attachments.append(self._uploads.pop(upload_id))
        inbound = Inbound(text=text, attachments=attachments)
        async with self._locks[conversation_id]:
            result = await run_turn(
                self.graph,
                conversation_id,
                inbound,
                customer_phone=phone,
                sinks=[self._persist_and_publish],
            )
        self.bus.publish({"type": "metrics", "metrics": self.metrics().model_dump(mode="json")})
        return result

    def _persist_and_publish(self, ev: AgentEvent) -> None:
        self.store.add(ev)
        self.bus.publish({"type": "event", "event": ev.model_dump(mode="json")})

    def metrics(self) -> Metrics:
        return compute_metrics(self.store, self.settings.metrics)

    def set_pause(self, paused: bool, conversation_id: str | None) -> dict[str, Any]:
        snapshot = self.control.set(paused, conversation_id).model_dump()
        self.bus.publish({"type": "control", "pause": snapshot})
        return snapshot


def reset_inbox(settings: Settings) -> None:
    shutil.rmtree(settings.storage_path / "inbox", ignore_errors=True)
