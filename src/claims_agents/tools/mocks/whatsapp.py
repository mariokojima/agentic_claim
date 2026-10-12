"""Mock de `send_whatsapp`: registra a mensagem e entrega ao simulador (WebSocket) se houver."""

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.schemas import SendWhatsappRequest, SendWhatsappResponse

NAME = "send_whatsapp"

DeliveryFn = Callable[[str, dict[str, object]], Awaitable[bool]]


class MockSendWhatsapp:
    def __init__(
        self, db: DomainDB, faults: FaultInjector | None = None, delivery: DeliveryFn | None = None
    ) -> None:
        self.db = db
        self.faults = faults or FaultInjector()
        self.delivery = delivery

    async def __call__(self, req: SendWhatsappRequest) -> SendWhatsappResponse:
        await self.faults.maybe_fail(NAME)
        message_id = f"wamid.{uuid.uuid4().hex[:16]}"
        sent_at = datetime.now(UTC).isoformat()
        status: Literal["sent", "delivered"] = "sent"
        if self.delivery is not None:
            payload: dict[str, object] = {
                "message_id": message_id,
                "text": req.text,
                "attachments": [a.model_dump() for a in req.attachments],
                "sent_at": sent_at,
            }
            status = "delivered" if await self.delivery(req.conversation_id, payload) else "sent"
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?)",
                (
                    message_id,
                    req.conversation_id,
                    req.text,
                    json.dumps([a.model_dump() for a in req.attachments]),
                    status,
                    sent_at,
                ),
            )
        return SendWhatsappResponse(message_id=message_id, status=status)
