"""Triagem entende o ocorrido antes de falar em aviso de sinistro (ADR-0014)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.settings import Settings
from claims_agents.domain import ClaimStage, Customer
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.runner import run_turn
from claims_agents.tools.registry import ToolRegistry
from tests.support.conversation import text

Graph = CompiledStateGraph[Any, Any, Any, Any]


@pytest.fixture
async def graph(registry: ToolRegistry, settings: Settings) -> AsyncIterator[Graph]:
    async with open_checkpointer(settings.checkpoints_db_path) as saver:
        yield build_graph(GraphDeps(registry=registry, settings=settings), saver)


def replies(r: Any) -> str:
    out = []
    for m in reversed(r.state.messages):
        if m.role == "user":
            break
        out.append(m.text)
    return "\n".join(reversed(out))


async def test_asks_what_happened_before_mentioning_claim(
    graph: Graph, happy_customer: Customer
) -> None:
    await run_turn(graph, "t1", text("Oi"))
    r = await run_turn(graph, "t1", text(happy_customer.cpf))
    assert r.state.claim_stage == ClaimStage.TRIAGEM
    assert r.state.awaiting is not None and r.state.awaiting.field == "event"
    assert "o que aconteceu" in replies(r) and "aviso" not in replies(r).lower()
    # decisão em turno posterior à identificação mantém a apólice escolhida (regressão)
    r = await run_turn(graph, "t1", text("Bati o carro"))
    # elegível: pergunta pelos envolvidos antes de concluir a Triagem
    assert r.state.claim_stage == ClaimStage.TRIAGEM and r.state.awaiting is not None
    assert r.state.awaiting.field == "parties" and "outro veículo" in replies(r)
    r = await run_turn(graph, "t1", text("não, só eu e ninguém se feriu"))
    assert r.state.claim_stage == ClaimStage.AVISO
    assert r.state.customer is not None and r.state.customer.policy_number == "AUTO-0001-01"
    assert "colisão" in replies(r) and "quando aconteceu" in replies(r)
    assert "o que aconteceu (ex" not in replies(r)  # a Triagem já entendeu o ocorrido
    r = await run_turn(graph, "t1", text("foi ontem às 18h na Av. Paulista, 1000"))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS and r.state.protocol


async def test_initial_message_is_reused(graph: Graph, happy_customer: Customer) -> None:
    await run_turn(
        graph,
        "t2",
        text("Oi, bati o carro sozinho ontem às 9h na Av. Brasil, 200, ninguém se feriu"),
    )
    r = await run_turn(graph, "t2", text(happy_customer.cpf))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS  # nada a perguntar: aviso já registrado
    assert "Av Brasil, 200" in replies(r)


@pytest.mark.parametrize(
    ("message", "reason", "snippet"),
    [
        ("Roubaram meu carro ontem", "rejected:event_type_ROUBO_FURTO", "roubo ou furto"),
        ("o para-brisa trincou na estrada", "rejected:event_type_VIDROS", "serviço de vidros"),
        (
            "meu carro não liga, preciso de guincho",
            "rejected:event_type_ASSISTENCIA",
            "Assistência 24h",
        ),
        (
            "quero a segunda via do boleto",
            "rejected:event_type_NAO_SINISTRO",
            "dedicado à abertura",
        ),
        (
            "uma árvore caiu no carro com a chuva",
            "rejected:event_type_FENOMENO_NATURAL",
            "natureza",
        ),
    ],
)
async def test_non_collision_is_oriented(
    graph: Graph, happy_customer: Customer, message: str, reason: str, snippet: str
) -> None:
    conv = f"t-{reason}"
    await run_turn(graph, conv, text("Oi"))
    await run_turn(graph, conv, text(happy_customer.cpf))
    r = await run_turn(graph, conv, text(message))
    assert r.state.claim_stage == ClaimStage.ORIENTADO and r.state.terminal_reason == reason
    assert snippet in replies(r) and r.state.protocol is None


async def test_unclear_event_escalates_after_attempts(
    graph: Graph, happy_customer: Customer
) -> None:
    await run_turn(graph, "t3", text("Oi"))
    await run_turn(graph, "t3", text(happy_customer.cpf))
    for _ in range(2):
        r = await run_turn(graph, "t3", text("não sei"))
        assert r.state.claim_stage == ClaimStage.TRIAGEM and "Não consegui entender" in replies(r)
    r = await run_turn(graph, "t3", text("sei lá"))
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO


async def test_injuries_raise_urgency(graph: Graph, happy_customer: Customer) -> None:
    await run_turn(graph, "t4", text("Oi"))
    await run_turn(graph, "t4", text(happy_customer.cpf))
    r = await run_turn(graph, "t4", text("Bati o carro e tem um ferido"))
    assert replies(r) == "Havia outro veículo ou pessoa envolvida no ocorrido?"  # só o que falta
    r = await run_turn(graph, "t4", text("não"))
    assert "SAMU (192)" in replies(r) and r.state.claim_stage == ClaimStage.AVISO
    assert r.state.triage.outcome["has_injuries"] is True


async def test_customer_without_policy_is_not_asked(graph: Graph, fixtures: Any) -> None:
    no_policy = fixtures[0][8]
    await run_turn(graph, "t5", text("Oi"))
    r = await run_turn(graph, "t5", text(no_policy.cpf))
    assert r.state.terminal_reason == "rejected:customer_not_found"
