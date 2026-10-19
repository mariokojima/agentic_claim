"""Fase 5 — Documentos: critério de saída, mensagem final, progresso, lembrete e timeout."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.settings import Settings
from claims_agents.domain import ClaimStage, Customer, DocumentType
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.runner import run_turn
from claims_agents.state import Inbound
from claims_agents.tools.registry import ToolRegistry
from tests.support.conversation import attachment, full_document_set, text

Graph = CompiledStateGraph[Any, Any, Any, Any]
SOLO = (
    "ontem às 18h bati sozinho no poste da Av. Paulista, 1000, ninguém se feriu, amassou a frente"
)
WITH_THIRD = (
    "ontem às 18h bati na traseira de outro carro na Av. Paulista, 1000, ninguém se feriu, "
    "amassou a frente"
)


@pytest.fixture
async def make_graph(
    registry: ToolRegistry, settings: Settings
) -> AsyncIterator[Callable[..., Graph]]:
    async with open_checkpointer(settings.checkpoints_db_path) as saver:
        yield lambda **kw: build_graph(GraphDeps(registry=registry, settings=settings, **kw), saver)


def replies(r: Any) -> str:
    out = []
    for m in reversed(r.state.messages):
        if m.role == "user":
            break
        out.append(m.text)
    return "\n".join(reversed(out))


async def to_documents(graph: Graph, conv: str, customer: Customer, story: str = SOLO) -> Any:
    await run_turn(graph, conv, text("Oi"))
    await run_turn(graph, conv, text(customer.cpf))
    r = await run_turn(graph, conv, text(story))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS
    return r


async def test_final_message_has_protocol_summary_grouped_docs_and_next_steps(
    make_graph: Any, happy_customer: Customer, tmp_path: Path
) -> None:
    graph = make_graph()
    await to_documents(graph, "d1", happy_customer)
    r = await run_turn(
        graph, "d1", text("Seguem", full_document_set(tmp_path, happy_customer, "SNT1A23"))
    )
    assert r.state.claim_stage == ClaimStage.CONCLUIDO
    msg = replies(r)
    assert f"Protocolo: {r.state.protocol}" in msg
    assert "Av Paulista, 1000" in msg and "Danos: frente" in msg
    assert "• CNH do condutor\n• CRLV do veículo\n• Fotos dos danos (3)" in msg
    assert "Próximos passos:\n1." in msg and "vistoria" in msg
    assert any(e.event == "exit_criteria_met" for e in r.events)


async def test_partial_upload_reports_validated_and_pending(
    make_graph: Any, happy_customer: Customer, tmp_path: Path
) -> None:
    graph = make_graph()
    await to_documents(graph, "d2", happy_customer)
    cnh = attachment(tmp_path, DocumentType.CNH, {"cpf": happy_customer.cpf})
    r = await run_turn(graph, "d2", text("Segue a CNH", [cnh]))
    msg = replies(r)
    assert "Já validei:\n• CNH do condutor" in msg
    assert "Ainda faltam:" in msg and "CRLV do veículo" in msg and "Fotos dos danos" in msg
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS


async def test_police_report_required_with_third_parties_blocks_exit(
    make_graph: Any, happy_customer: Customer, tmp_path: Path
) -> None:
    graph = make_graph()
    r = await to_documents(graph, "d3", happy_customer, WITH_THIRD)
    assert "Boletim de ocorrência" in replies(r)
    r = await run_turn(
        graph, "d3", text("docs", full_document_set(tmp_path, happy_customer, "SNT1A23"))
    )
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS and "Boletim de ocorrência" in replies(r)
    bo = attachment(tmp_path, DocumentType.BOLETIM_OCORRENCIA, {})
    r = await run_turn(graph, "d3", text("BO", [bo]))
    assert r.state.claim_stage == ClaimStage.CONCLUIDO and "• Boletim de ocorrência" in replies(r)


async def test_reminder_timer_lists_pending_and_keeps_stage(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await to_documents(graph, "t1", happy_customer)
    r = await run_turn(graph, "t1", Inbound(kind="reminder"))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS
    msg = replies(r)
    assert (
        (r.state.protocol or "?") in msg and "CNH do condutor" in msg and "clipe de anexos" in msg
    )
    assert r.state.documents.reminded_at is not None
    # o disparo do timer não vira mensagem do cliente
    assert all(m.text for m in r.state.messages if m.role == "user")


async def test_timeout_timer_escalates_to_human(make_graph: Any, happy_customer: Customer) -> None:
    graph = make_graph()
    await to_documents(graph, "t2", happy_customer)
    r = await run_turn(graph, "t2", Inbound(kind="timeout"))
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO
    assert r.state.terminal_reason == "timeout_documentos"
    assert "dentro do prazo" in replies(r)


async def test_timer_outside_documents_is_ignored(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    before = await run_turn(graph, "t3", text("Oi"))
    r = await run_turn(graph, "t3", Inbound(kind="timeout"))
    assert r.state.claim_stage == ClaimStage.TRIAGEM
    assert len(r.state.messages) == len(before.state.messages)  # nada enviado, nada registrado
    assert any(e.event == "timer_ignored" for e in r.events)


async def test_late_message_after_deadline_is_timeout(
    make_graph: Any, settings: Settings, happy_customer: Customer, tmp_path: Path
) -> None:
    clock = {"now": datetime.now(UTC)}
    graph = make_graph(now=lambda: clock["now"])
    await to_documents(graph, "t4", happy_customer)
    clock["now"] += timedelta(minutes=settings.documents.complement_timeout_minutes + 1)
    r = await run_turn(
        graph, "t4", text("docs", full_document_set(tmp_path, happy_customer, "SNT1A23"))
    )
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO
    assert r.state.terminal_reason == "timeout_documentos"
