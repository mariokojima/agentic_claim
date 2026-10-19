"""Subgrafo de Documentos e Evidências."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claims_agents.agents.documents import coordinator
from claims_agents.agents.documents.state import DocumentsGraphState
from claims_agents.agents.documents.subagents.checklist import nodes as checklist
from claims_agents.agents.documents.subagents.complement import nodes as complement
from claims_agents.agents.documents.subagents.intake_storage import nodes as intake_storage
from claims_agents.agents.documents.subagents.validation import nodes as validation
from claims_agents.core.messages import Messages
from claims_agents.core.types import NodeWrapper, identity
from claims_agents.tools.interfaces import StoreFiles, ValidateDocument


def build_documents_graph(
    store_files: StoreFiles,
    validate_document: ValidateDocument,
    checklist_config: dict[str, Any],
    messages: Messages,
    wrap: NodeWrapper = identity,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(DocumentsGraphState)
    g.add_node("checklist", wrap(checklist.build(checklist_config, messages)))
    g.add_node("intake_storage", wrap(intake_storage.build(store_files, messages)))
    g.add_node("validation", wrap(validation.build(validate_document, messages)))
    g.add_node("complement", wrap(complement.build(messages, checklist_config)))
    g.add_edge(START, "checklist")
    for node, nxt in zip(coordinator.ORDER, coordinator.ORDER[1:], strict=False):
        g.add_conditional_edges(node, coordinator.after(node), {"end": END, nxt: nxt})
    g.add_edge("complement", END)
    return g.compile()
