"""Grafo completo (stubs, sem LLM) com checkpointer SQLite, turno a turno."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.settings import Settings
from claims_agents.domain import ClaimStage, Customer, DocumentType, Policy
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.runner import run_turn
from claims_agents.observability.events import AgentEvent
from claims_agents.tools.registry import ToolRegistry
from tests.support.conversation import attachment, full_document_set, text

Graph = CompiledStateGraph[Any, Any, Any, Any]


@pytest.fixture
def deps(registry: ToolRegistry, settings: Settings) -> GraphDeps:
    return GraphDeps(registry=registry, settings=settings)


@pytest.fixture
async def graph(deps: GraphDeps, settings: Settings) -> AsyncIterator[Graph]:
    async with open_checkpointer(settings.checkpoints_db_path) as saver:
        yield build_graph(deps, saver)


def kinds(events: list[AgentEvent]) -> list[str]:
    return [e.event for e in events]


async def test_happy_path_reaches_concluido(
    graph: Graph, happy_customer: Customer, tmp_path: Path
) -> None:
    conv = "conv-happy"
    r1 = await run_turn(graph, conv, text("Oi, bati o carro"), customer_phone=happy_customer.phone)
    assert r1.state.claim_stage == ClaimStage.TRIAGEM
    assert r1.state.awaiting is not None and r1.state.awaiting.field == "cpf"
    assert "flow_started" in kinds(r1.events)

    r2 = await run_turn(graph, conv, text(f"Meu CPF é {happy_customer.cpf}"))
    assert r2.state.claim_stage == ClaimStage.AVISO  # TRIAGEM concluída, AVISO na mesma rodada
    assert r2.state.customer is not None and r2.state.customer.policy_number == "AUTO-0001-01"
    assert r2.state.awaiting is not None and r2.state.awaiting.field == "description"
    routes = [e.data["target"] for e in r2.events if e.event == "route"]
    assert routes == ["triage", "claim_notice"]

    r3 = await run_turn(graph, conv, text("Colisão traseira na Av. Fictícia, ontem às 18h"))
    assert r3.state.claim_stage == ClaimStage.DOCUMENTOS
    assert r3.state.protocol and r3.state.protocol.startswith("SIN-")
    assert any(e.event == "tool_call" and e.tool == "open_claim" for e in r3.events)

    r4 = await run_turn(
        graph, conv, text("Segue", full_document_set(tmp_path, happy_customer, "SNT1A23"))
    )
    assert r4.state.claim_stage == ClaimStage.CONCLUIDO
    assert r4.state.terminal_reason == "completed"
    final = r4.state.messages[-1]
    assert final.role == "assistant" and (r4.state.protocol or "?") in final.text

    # Toda mensagem ao cliente passou pelo guardrail de saída antes do envio.
    for r in (r1, r2, r3, r4):
        ks = kinds(r.events)
        assert ks.index("message_sent") > max(
            i
            for i, e in enumerate(r.events)
            if e.event == "guardrail_verdict" and e.data.get("direction") == "output"
        )

    r5 = await run_turn(graph, conv, text("Olá de novo"))
    assert r5.state.claim_stage == ClaimStage.CONCLUIDO
    assert "encerrado" in r5.state.messages[-1].text


async def test_documents_complement_loop(
    graph: Graph, happy_customer: Customer, tmp_path: Path
) -> None:
    conv = "conv-docs"
    await run_turn(graph, conv, text("Oi"))
    await run_turn(graph, conv, text(happy_customer.cpf))
    await run_turn(graph, conv, text("Ontem bati o carro no estacionamento do mercado"))
    partial = [
        attachment(tmp_path, DocumentType.CNH, {"cpf": happy_customer.cpf}),
        attachment(tmp_path, DocumentType.CRLV, {"plate": "ERR0R00"}),
    ]
    r = await run_turn(graph, conv, text("Docs", partial))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS
    reply = r.state.messages[-1].text
    assert "placa" in reply.lower() and "Fotos dos danos" in reply
    assert r.state.awaiting is not None and r.state.awaiting.field == "documents"


@pytest.mark.parametrize(
    ("customer_idx", "expected_reason"),
    [
        (2, "rejected:policy_not_active"),
        (3, "rejected:no_coverage"),
        (7, "rejected:outside_policy_term"),
        (8, "rejected:customer_not_found"),
    ],
)
async def test_triage_rejection_goes_to_orientado(
    graph: Graph,
    fixtures: tuple[list[Customer], list[Policy]],
    customer_idx: int,
    expected_reason: str,
) -> None:
    customer = fixtures[0][customer_idx]
    conv = f"conv-rej-{customer_idx}"
    await run_turn(graph, conv, text("Oi"))
    r = await run_turn(graph, conv, text(customer.cpf))
    assert r.state.claim_stage == ClaimStage.ORIENTADO
    assert r.state.terminal_reason == expected_reason
    assert "corretor" in r.state.messages[-1].text or "Não localizamos" in r.state.messages[-1].text


async def test_unknown_cpf_is_rejected(graph: Graph) -> None:
    await run_turn(graph, "conv-x", text("Oi"))
    r = await run_turn(graph, "conv-x", text("529.982.247-25"))
    assert r.state.terminal_reason == "rejected:customer_not_found"


async def test_invalid_cpf_attempts_escalate(graph: Graph) -> None:
    conv = "conv-attempts"
    await run_turn(graph, conv, text("Oi"))
    for _ in range(2):
        r = await run_turn(graph, conv, text("não sei"))
        assert r.state.claim_stage == ClaimStage.TRIAGEM
    r = await run_turn(graph, conv, text("ainda não sei"))
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO


async def test_pause_returns_handoff_without_running_agents(
    graph: Graph, deps: GraphDeps, happy_customer: Customer
) -> None:
    conv = "conv-pause"
    await run_turn(graph, conv, text("Oi"))
    deps.control.set(True, conv)
    r = await run_turn(graph, conv, text(happy_customer.cpf))
    assert r.state.claim_stage == ClaimStage.TRIAGEM
    assert r.state.messages[-1].text == deps.settings.pause.handoff_message
    assert "route" not in kinds(r.events)
    deps.control.set(False, conv)
    r = await run_turn(graph, conv, text(happy_customer.cpf))
    assert r.state.claim_stage == ClaimStage.AVISO
