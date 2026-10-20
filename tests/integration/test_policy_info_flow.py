"""Especialista Consultas no grafo completo (ADR-0019)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.llm import FakeLLMClient
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


async def test_first_message_query_asks_cpf_then_answers(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    r = await run_turn(graph, "q1", text("Oi, quando vence minha apólice?"))
    assert "informe o CPF" in replies(r) and r.state.awaiting.stage == "CONSULTA"  # type: ignore[union-attr]
    r = await run_turn(graph, "q1", text(happy_customer.cpf))
    msg = replies(r)
    assert "AUTO-0001-01" in msg and "vence em 14/01/2027" in msg
    assert "Posso ajudar com mais alguma coisa?" in msg
    assert r.state.awaiting is None and r.state.customer is not None
    assert r.state.claim_stage == ClaimStage.TRIAGEM and r.state.protocol is None
    assert "policy_info" in [e.data.get("target") for e in r.events if e.event == "route"]


async def test_claim_after_query_does_not_ask_cpf_again(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await run_turn(graph, "q2", text("Oi, minha apólice cobre vidros?"))
    r = await run_turn(graph, "q2", text(happy_customer.cpf))
    assert "sim, inclui a cobertura de vidros" in replies(r)
    r = await run_turn(graph, "q2", text("o para-brisa trincou ontem na rodovia SP-280"))
    assert "CPF" not in replies(r) and r.state.claim_stage == ClaimStage.DOCUMENTOS


async def test_query_mid_notice_resumes_pending_question(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await run_turn(graph, "q3", text("Oi"))
    await run_turn(graph, "q3", text(happy_customer.cpf))
    r = await run_turn(graph, "q3", text("bati sozinho num poste, ninguém se feriu"))
    assert r.state.claim_stage == ClaimStage.AVISO
    r = await run_turn(graph, "q3", text("quais são as minhas coberturas?"))
    msg = replies(r)
    assert "Colisão (casco" in msg and "Vamos continuar:" in msg and "partes do veículo" in msg
    assert r.state.claim_stage == ClaimStage.AVISO and r.state.awaiting.field == "description"  # type: ignore[union-attr]
    r = await run_turn(graph, "q3", text("o que é sinistro?"))
    assert "ocorrência do evento coberto" in replies(r)


async def test_hypothetical_question_does_not_open_claim(
    make_graph: Any, happy_customer: Customer
) -> None:
    llm = FakeLLMClient(
        responder=lambda msgs, role, model: (
            "Depende das condições do contrato e da análise do caso."
            if role == "writer"
            else {"intent": "continuar_etapa", "confidence": 0.9, "justification": "-"}
        )
    )
    graph = make_graph(llm=llm)
    await run_turn(graph, "q4", text("Oi"))
    await run_turn(graph, "q4", text(happy_customer.cpf))
    r = await run_turn(
        graph, "q4", text("se eu emprestar o carro pro meu irmão e ele bater, o seguro cobre?")
    )
    assert "Depende das condições" in replies(r)
    assert r.state.claim_stage == ClaimStage.TRIAGEM and r.state.protocol is None
    writer_call = next(c for c in llm.calls if c["role"] == "writer")
    assert "Base de conhecimento" in writer_call["messages"][0]["content"]  # LLM restrito à base
    assert "AUTO-0001-01" in writer_call["messages"][0]["content"]  # e aos dados da apólice


async def test_unknown_question_without_llm_suggests_broker(make_graph: Any) -> None:
    graph = make_graph()
    r = await run_turn(graph, "q5", text("quanto custa o seguro de um carro novo?"))
    assert "corretor" in replies(r) and r.state.claim_stage == ClaimStage.TRIAGEM


async def test_multiple_policies_and_unknown_cpf(make_graph: Any, fixtures: Any) -> None:
    fabio = next(c for c in fixtures[0] if c.name.startswith("Fabio"))
    graph = make_graph()
    await run_turn(graph, "q6", text("quero renovar meu seguro"))
    r = await run_turn(graph, "q6", text(fabio.cpf))
    assert (
        "das suas apólices" in replies(r)
        and "AUTO-0006-01" in replies(r)
        and "AUTO-0006-02" in replies(r)
    )
    await run_turn(graph, "q7", text("quando vence minha apólice?"))
    r = await run_turn(graph, "q7", text("529.982.247-25"))
    assert "Não localizei apólices" in replies(r)
