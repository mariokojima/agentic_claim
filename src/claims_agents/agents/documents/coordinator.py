"""Coordenador dinâmico de Documentos: encerra o turno assim que houver um `StageResult`."""

from collections.abc import Callable

from claims_agents.agents.documents.state import DocumentsGraphState

ORDER = ["checklist", "intake_storage", "validation", "complement"]


def after(node: str) -> Callable[[DocumentsGraphState], str]:
    def route(state: DocumentsGraphState) -> str:
        if state.result is not None:
            return "end"
        return ORDER[ORDER.index(node) + 1]

    return route
