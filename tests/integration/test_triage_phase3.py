"""Fase 3 — Triagem completa: LLM como fallback (falso), envolvidos, vigência pela data do
evento, checagem corporativa com contexto, timeout de inatividade e redação de mensagens."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph

from claims_agents.core.llm import FakeLLMClient, LLMError
from claims_agents.core.settings import Settings
from claims_agents.domain import ClaimStage, Customer, Policy
from claims_agents.graph.build_graph import build_graph
from claims_agents.graph.checkpointer import open_checkpointer
from claims_agents.graph.deps import GraphDeps
from claims_agents.graph.runner import run_turn
from claims_agents.tools.registry import ToolRegistry
from tests.support.conversation import text

Graph = CompiledStateGraph[Any, Any, Any, Any]
GraphFactory = Callable[..., Any]


@pytest.fixture
async def make_graph(
    registry: ToolRegistry, settings: Settings
) -> AsyncIterator[Callable[[GraphDeps], Graph]]:
    async with open_checkpointer(settings.checkpoints_db_path) as saver:
        yield lambda deps: build_graph(deps, saver)


def deps(registry: ToolRegistry, settings: Settings, **kw: Any) -> GraphDeps:
    return GraphDeps(registry=registry, settings=settings, **kw)


def replies(r: Any) -> str:
    out = []
    for m in reversed(r.state.messages):
        if m.role == "user":
            break
        out.append(m.text)
    return "\n".join(reversed(out))


def customer(fixtures: tuple[list[Customer], list[Policy]], name: str) -> Customer:
    return next(c for c in fixtures[0] if c.name.startswith(name))


# --- LLM como fallback da classificação -------------------------------------------------------


async def test_llm_classifies_what_rules_do_not_understand(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    llm = FakeLLMClient(
        [
            {
                "event_type": "COLISAO",
                "has_third_parties": True,
                "has_injuries": None,
                "justification": "outro veículo atingiu a porta",
            }
        ]
    )
    graph = make_graph(deps(registry, settings, llm=llm))
    await run_turn(graph, "l1", text("Oi"))
    r = await run_turn(graph, "l1", text(happy_customer.cpf))
    assert llm.calls == []  # "Oi" não vai ao LLM
    r = await run_turn(graph, "l1", text("um cara entrou na contramão e pegou minha porta"))
    assert len(llm.calls) == 1 and llm.calls[0]["role"] == "extraction"
    assert r.state.triage.outcome["classification_source"] == "llm"
    assert replies(r) == "Alguém se feriu?"  # terceiro já informado pelo LLM
    events = [e for e in r.events if e.event == "event_classified"]
    assert "via llm" in events[0].details


async def test_llm_failure_degrades_to_rules(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    llm = FakeLLMClient([LLMError("503")])
    graph = make_graph(deps(registry, settings, llm=llm))
    await run_turn(graph, "l2", text("Oi"))
    await run_turn(graph, "l2", text(happy_customer.cpf))
    r = await run_turn(graph, "l2", text("um cara entrou na contramão e pegou minha porta"))
    assert r.state.claim_stage == ClaimStage.TRIAGEM and "Não consegui entender" in replies(r)


async def test_llm_disabled_by_flag(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    settings.triage.llm_fallback = False
    llm = FakeLLMClient([])
    graph = make_graph(deps(registry, settings, llm=llm))
    await run_turn(graph, "l3", text("Oi"))
    await run_turn(graph, "l3", text(happy_customer.cpf))
    await run_turn(graph, "l3", text("um cara entrou na contramão e pegou minha porta"))
    assert llm.calls == []


# --- envolvidos ------------------------------------------------------------------------------


async def test_ambiguous_parties_answer_uses_llm(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    llm = FakeLLMClient([{"has_third_parties": True, "has_injuries": False}])
    graph = make_graph(deps(registry, settings, llm=llm))
    await run_turn(graph, "p1", text("Oi"))
    await run_turn(graph, "p1", text(happy_customer.cpf))
    await run_turn(graph, "p1", text("Bati o carro"))
    r = await run_turn(graph, "p1", text("sim"))  # ambíguo para as duas perguntas
    assert llm.calls[0]["role"] == "extraction" and r.state.claim_stage == ClaimStage.AVISO
    assert r.state.triage.outcome["has_third_parties"] is True


async def test_third_parties_make_police_report_required(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    graph = make_graph(deps(registry, settings))
    await run_turn(graph, "p2", text("Oi"))
    await run_turn(graph, "p2", text(happy_customer.cpf))
    r = await run_turn(
        graph,
        "p2",
        text("Ontem às 9h bati na traseira de outro carro na Av. Brasil, 200. Ninguém se feriu"),
    )
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS
    assert "Boletim de ocorrência" in replies(r)
    assert r.state.notice.event["has_third_parties"] is True


async def test_no_third_parties_no_police_report(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    graph = make_graph(deps(registry, settings))
    await run_turn(graph, "p3", text("Oi"))
    await run_turn(graph, "p3", text(happy_customer.cpf))
    r = await run_turn(
        graph, "p3", text("ontem bati sozinho no poste da Rua Augusta, 50; ninguém se feriu")
    )
    assert r.state.claim_stage == ClaimStage.DOCUMENTOS and "Boletim" not in replies(r)


async def test_unanswered_parties_escalates(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    graph = make_graph(deps(registry, settings))
    await run_turn(graph, "p4", text("Oi"))
    await run_turn(graph, "p4", text(happy_customer.cpf))
    await run_turn(graph, "p4", text("Bati o carro"))
    r = await run_turn(graph, "p4", text("hmm"))
    assert "Não consegui entender" in replies(r)
    for _ in range(2):
        r = await run_turn(graph, "p4", text("talvez"))
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO


# --- vigência pela data do evento ------------------------------------------------------------


async def test_policy_term_checked_against_event_date(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    graph = make_graph(deps(registry, settings))  # apólice da Ana começa em 15/01/2026
    await run_turn(graph, "v1", text("Oi"))
    await run_turn(graph, "v1", text(happy_customer.cpf))
    r = await run_turn(graph, "v1", text("no dia 10/01/2026 bati sozinho no poste"))
    assert r.state.terminal_reason == "rejected:outside_policy_term"


# --- checagem corporativa com contexto ------------------------------------------------------


async def test_recent_policy_is_escalated_at_end_of_triage(
    make_graph: Any, registry: ToolRegistry, settings: Settings, fixtures: Any
) -> None:
    marina = customer(fixtures, "Marina")  # vigência desde 10/10/2026
    graph = make_graph(deps(registry, settings))
    await run_turn(graph, "c1", text("Oi"))
    await run_turn(graph, "c1", text(marina.cpf))
    r = await run_turn(
        graph, "c1", text("no dia 12/10/2026 bati no poste, só eu, ninguém se feriu")
    )
    assert r.state.claim_stage == ClaimStage.ESCALADO_HUMANO
    assert r.state.terminal_reason == "guardrail_corporate"
    assert "vou registrar o aviso" not in replies(r) and "especialistas humanos" in replies(r)
    check = next(e for e in r.events if e.event == "corporate_check")
    assert "recent_policy" in check.details and r.state.protocol is None


async def test_regular_policy_passes_corporate_check(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    graph = make_graph(deps(registry, settings))
    await run_turn(graph, "c2", text("Oi"))
    await run_turn(graph, "c2", text(happy_customer.cpf))
    r = await run_turn(graph, "c2", text("ontem bati sozinho no poste, ninguém se feriu"))
    assert r.state.claim_stage == ClaimStage.AVISO
    assert [e.data["decision"] for e in r.events if e.event == "corporate_check"] == ["allow"]


# --- timeout de inatividade -------------------------------------------------------------------


async def test_inactivity_timeout_restarts_triage(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    clock = {"now": datetime.now(UTC)}
    graph = make_graph(deps(registry, settings, now=lambda: clock["now"]))
    await run_turn(graph, "i1", text("Oi"))
    await run_turn(graph, "i1", text(happy_customer.cpf))  # aguardando "o que aconteceu"
    clock["now"] += timedelta(minutes=settings.triage.inactivity_timeout_minutes + 1)
    r = await run_turn(graph, "i1", text("Bati o carro"))
    assert "reiniciar o atendimento" in replies(r) and "CPF" in replies(r)
    assert r.state.awaiting is not None and r.state.awaiting.field == "cpf"
    assert any(e.event == "inactivity_timeout" for e in r.events)


async def test_no_timeout_within_limit(
    make_graph: Any, registry: ToolRegistry, settings: Settings, happy_customer: Customer
) -> None:
    clock = {"now": datetime.now(UTC)}
    graph = make_graph(deps(registry, settings, now=lambda: clock["now"]))
    await run_turn(graph, "i2", text("Oi"))
    await run_turn(graph, "i2", text(happy_customer.cpf))
    clock["now"] += timedelta(minutes=5)
    r = await run_turn(graph, "i2", text("Bati o carro"))
    assert "reiniciar" not in replies(r)


# --- redação pelo LLM -------------------------------------------------------------------------


async def test_writer_rewrites_messages_when_enabled(
    make_graph: Any, registry: ToolRegistry, settings: Settings
) -> None:
    settings.llm.rewrite_messages = True
    llm = FakeLLMClient(responder=lambda msgs, role, model: "Oi! Me passa seu CPF, por favor?")
    graph = make_graph(deps(registry, settings, llm=llm))
    r = await run_turn(graph, "w1", text("Oi"))
    assert replies(r) == "Oi! Me passa seu CPF, por favor?"
    assert llm.calls[0]["role"] == "writer"


async def test_writer_failure_keeps_original(
    make_graph: Any, registry: ToolRegistry, settings: Settings
) -> None:
    settings.llm.rewrite_messages = True
    graph = make_graph(deps(registry, settings, llm=FakeLLMClient([LLMError("down")])))
    r = await run_turn(graph, "w2", text("Oi"))
    assert "informe o CPF" in replies(r)


async def test_writer_output_still_goes_through_output_guardrail(
    make_graph: Any, registry: ToolRegistry, settings: Settings
) -> None:
    settings.llm.rewrite_messages = True
    llm = FakeLLMClient(responder=lambda *a: "Garantimos o pagamento da sua indenização!")
    graph = make_graph(deps(registry, settings, llm=llm))
    r = await run_turn(graph, "w3", text("Oi"))
    assert "Garantimos" not in replies(r)  # bloqueado pelo guardrail de saída (undue_promise)
