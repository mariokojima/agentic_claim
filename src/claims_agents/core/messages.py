"""Templates de mensagens ao cliente (`configs/messages.yaml`)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from claims_agents.core.settings import load_config


class Messages:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, **kwargs: Any) -> str:
        """`get("triage.ask_cpf")` → texto formatado."""
        node: Any = self._data
        for part in key.split("."):
            node = node[part]
        return str(node).format(**kwargs) if kwargs else str(node)


@lru_cache
def load_messages() -> Messages:
    return Messages(load_config("messages"))
