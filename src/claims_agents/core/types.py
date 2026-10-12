"""Tipos utilitários compartilhados."""

from typing import Any, Protocol


class NodeFn[S](Protocol):
    """Nó de grafo LangGraph (síncrono ou assíncrono) que recebe o estado pelo parâmetro `state`."""

    def __call__(self, state: S) -> Any: ...
