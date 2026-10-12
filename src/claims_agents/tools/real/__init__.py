"""Espaço para implementações reais das tools (fora do escopo da v1)."""

from typing import Any


class NotImplementedTool:
    """Stub de implementação real: falha explicitamente se selecionado na configuração."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def __call__(self, req: Any) -> Any:
        raise NotImplementedError(f"Implementação real de '{self.name}' não disponível na v1")
