"""Fase 4 — Aviso completo (danos, LLM na coleta, cobertura) e intenções do Orquestrador."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.llm import FakeLLMClient, LLMError
from claims_agents.core.settings import Settings
from claims_agents.domain import ClaimStage, Customer
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.runner import run_turn
from claims_agents.tools.registry import ToolRegistry
from tests.support.conversation import text

Graph = CompiledStateGraph[Any, Any, Any, Any]
SOLO = "bati sozinho num poste, ninguém se feriu"


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


async def to_notice(graph: Graph, conv: str, customer: Customer) -> Any:
    await run_turn(graph, conv, text("Oi"))
    await run_turn(graph, conv, text(customer.cpf))
    return await run_turn(graph, conv, text(SOLO))


# --- Aviso completo ---------------------------------------------------------------------------


async def test_notice_asks_damages_and_registers_with_coverage(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    r = await to_notice(graph, "n1", happy_customer)
    assert r.state.claim_stage == ClaimStage.AVISO and "partes do veículo" in replies(r)
    r = await run_turn(graph, "n1", text("ontem às 18h na Av. Paulista, 1000"))
    assert "partes do veículo" in replies(r) and "quando aconteceu" not in replies(r)
    r = await run_turn(graph, "n1", text("amassou o para-choque traseiro e a lanterna"))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS and r.state.protocol
    msg = replies(r)
    assert "Danos: para-choque traseiro, lanterna" in msg
    assert "Avaliação preliminar" in msg and "análise da equipe" in msg
    assert "terceiros" not in msg  # sem terceiros, não menciona essa cobertura


async def test_coverage_mentions_third_parties_when_involved(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await run_turn(graph, "n2", text("Oi"))
    await run_turn(graph, "n2", text(happy_customer.cpf))
    r = await run_turn(
        graph,
        "n2",
        text(
            "ontem bati na traseira de outro carro na Av. Brasil, 200; ninguém se feriu; "
            "amassou a frente"
        ),
    )
    assert "inclui cobertura para danos a terceiros" in replies(r)


async def test_llm_fills_what_rules_miss_in_notice(
    make_graph: Any, happy_customer: Customer
) -> None:
    llm = FakeLLMClient(
        responder=lambda msgs, role, model: (
            {
                "event_date": "2026-10-12",
                "event_time": "21:00",
                "location": "perto da casa da mãe, bairro Cambuí, Campinas",
                "what": "colisão",
                "damages": "porta do motorista",
            }
            if role == "extraction"
            else {
                "event_type": "INDEFINIDO",
                "has_third_parties": None,
                "has_injuries": None,
                "justification": "-",
            }
        )
    )
    graph = make_graph(llm=llm)
    # o LLM completa, já a partir do relato da Triagem, o que as regras não acharam
    r = await to_notice(graph, "n3", happy_customer)
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS
    assert r.state.notice.event["location"] == "perto da casa da mãe, bairro Cambuí, Campinas"
    assert any(e.event == "llm_extraction" for e in r.events)


async def test_llm_failure_in_notice_degrades_to_rules(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph(llm=FakeLLMClient(responder=lambda *a: LLMError("503")))
    await to_notice(graph, "n4", happy_customer)
    r = await run_turn(graph, "n4", text("aconteceu domingo à noite perto da casa da minha mãe"))
    assert r.state.claim_stage == ClaimStage.AVISO and "onde aconteceu" in replies(r)


# --- intenções por regras ---------------------------------------------------------------------


async def test_human_request_escalates_from_any_stage(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await to_notice(graph, "h1", happy_customer)
    r = await run_turn(graph, "h1", text("quero falar com um atendente"))
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO
    assert r.state.terminal_reason == "pedido_cliente"


async def test_cancel_goes_to_cancelado(make_graph: Any, happy_customer: Customer) -> None:
    graph = make_graph()
    await run_turn(graph, "x1", text("Oi"))
    r = await run_turn(graph, "x1", text("desisto, pode cancelar o atendimento"))
    assert r.state.claim_stage == ClaimStage.CANCELADO
    assert r.state.terminal_reason == "cancelado:cliente" and "encerrei" in replies(r)


async def test_cancel_policy_is_not_cancel_of_conversation(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await run_turn(graph, "x2", text("Oi"))
    await run_turn(graph, "x2", text(happy_customer.cpf))
    r = await run_turn(graph, "x2", text("quero cancelar minha apólice"))
    assert r.state.terminal_reason == "rejected:event_type_NAO_SINISTRO"


async def test_status_and_doubt_answer_and_resume(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await to_notice(graph, "s1", happy_customer)
    r = await run_turn(graph, "s1", text("qual o status do meu sinistro?"))
    msg = replies(r)
    assert "etapa Aviso de Sinistro" in msg and "Vamos continuar:" in msg
    assert "partes do veículo" in msg  # repete a pergunta pendente
    assert r.state.claim_stage == ClaimStage.AVISO
    r = await run_turn(graph, "s1", text("tem franquia?"))
    assert "franquia" in replies(r) and replies(r).count("Vamos continuar:") == 1
    r = await run_turn(graph, "s1", text("ontem às 18h na Av. Paulista, 1000; amassou a frente"))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS  # fluxo segue normalmente


async def test_correction_is_recorded_and_flow_continues(
    make_graph: Any, happy_customer: Customer
) -> None:
    graph = make_graph()
    await to_notice(graph, "k1", happy_customer)
    r = await run_turn(graph, "k1", text("na verdade foi ontem às 18h na Av. Paulista, 1000"))
    assert "Anotei sua correção" in replies(r) and r.state.corrections
    assert "partes do veículo" in replies(r)  # a informação também foi usada pela etapa


# --- flag do LLM de intenção ------------------------------------------------------------------


async def test_intent_llm_flag_off_never_calls_llm(
    make_graph: Any, settings: Settings, happy_customer: Customer
) -> None:
    settings.orchestrator.intent_llm_enabled = False
    llm = FakeLLMClient(
        responder=lambda msgs, role, model: (
            (_ for _ in ()).throw(AssertionError("LLM de intenção não deveria ser chamado"))
            if role == "intent"
            else LLMError("x")
        )
    )
    graph = make_graph(llm=llm)
    await to_notice(graph, "f1", happy_customer)
    r = await run_turn(graph, "f1", text("me passa uma receita de bolo de cenoura"))
    assert all(c["role"] != "intent" for c in llm.calls)
    assert r.state.claim_stage == ClaimStage.AVISO  # tratado como resposta (sem desvio)


async def test_intent_llm_flag_on_handles_deviations(
    make_graph: Any, settings: Settings, happy_customer: Customer
) -> None:
    settings.orchestrator.intent_llm_enabled = True

    def responder(msgs: Any, role: str, model: Any) -> Any:
        if role != "intent":
            return LLMError("só intenção neste teste")
        user = msgs[-1]["content"]
        if "bolo" in user:
            return {"intent": "fora_de_escopo", "confidence": 0.9, "justification": "receita"}
        if "fulano" in user:
            return {"intent": "falar_com_humano", "confidence": 0.4, "justification": "incerto"}
        return {"intent": "continuar_etapa", "confidence": 0.95, "justification": "resposta"}

    llm = FakeLLMClient(responder=responder)
    graph = make_graph(llm=llm)
    await to_notice(graph, "f2", happy_customer)
    r = await run_turn(graph, "f2", text("me passa uma receita de bolo de cenoura"))
    assert (
        "dedicado à abertura de sinistros" in replies(r) and r.state.claim_stage == ClaimStage.AVISO
    )
    r = await run_turn(graph, "f2", text("o fulano disse que viu tudo"))  # confiança baixa
    assert r.state.claim_stage == ClaimStage.AVISO and "dedicado" not in replies(r)
    r = await run_turn(graph, "f2", text("ontem às 18h na Av. Paulista, 1000; amassou a frente"))
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS and r.state.protocol
    assert any(c["role"] == "intent" for c in llm.calls)
