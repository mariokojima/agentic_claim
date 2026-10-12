"""Controle de pausa do agente (global e por conversa)."""

from __future__ import annotations

import threading

from pydantic import BaseModel


class PauseSnapshot(BaseModel):
    global_paused: bool
    conversations: list[str]


class PauseControl:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._global = False
        self._conversations: set[str] = set()

    def is_paused(self, conversation_id: str) -> bool:
        with self._lock:
            return self._global or conversation_id in self._conversations

    def set(self, paused: bool, conversation_id: str | None = None) -> PauseSnapshot:
        with self._lock:
            if conversation_id is None:
                self._global = paused
            elif paused:
                self._conversations.add(conversation_id)
            else:
                self._conversations.discard(conversation_id)
        return self.snapshot()

    def snapshot(self) -> PauseSnapshot:
        with self._lock:
            return PauseSnapshot(
                global_paused=self._global, conversations=sorted(self._conversations)
            )
