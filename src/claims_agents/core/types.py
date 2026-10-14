"""Tipos utilitários compartilhados."""

from collections.abc import Callable
from typing import Any, Protocol


class NodeFn[S](Protocol):
    """Nó de grafo LangGraph (síncrono ou assíncrono) que recebe o estado pelo parâmetro `state`."""

    def __call__(self, state: S) -> Any: ...


# Envolve os nós de um subgrafo (ex.: atraso do modo demonstração). Os agentes só repassam.
NodeWrapper = Callable[[NodeFn[Any]], NodeFn[Any]]


def identity(fn: NodeFn[Any]) -> NodeFn[Any]:
    return fn
