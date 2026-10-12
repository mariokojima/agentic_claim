"""Conexões WebSocket do simulador de chat (entrega das mensagens do `send_whatsapp` mock)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ChatHub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)

    def connect(self, conversation_id: str, ws: WebSocket) -> None:
        self._sockets[conversation_id].add(ws)

    def disconnect(self, conversation_id: str, ws: WebSocket) -> None:
        self._sockets[conversation_id].discard(ws)

    async def send(self, conversation_id: str, payload: dict[str, Any]) -> bool:
        delivered = False
        for ws in list(self._sockets.get(conversation_id, ())):
            try:
                await ws.send_json(payload)
                delivered = True
            except Exception:  # conexão encerrada
                self.disconnect(conversation_id, ws)
        return delivered

    async def deliver(self, conversation_id: str, message: dict[str, object]) -> bool:
        """Callback de entrega usado pelo mock de `send_whatsapp`."""
        return await self.send(conversation_id, {"type": "message", "role": "assistant", **message})
