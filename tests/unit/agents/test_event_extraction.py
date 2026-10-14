"""Extração de quando/onde/o que aconteceu (Aviso) e coleta incremental."""

from datetime import date, time

import pytest

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.event_data_collection import nodes
from claims_agents.agents.claim_notice.subagents.event_data_collection.extraction import (
    extract_event,
)
from claims_agents.core.messages import load_messages
from claims_agents.state import NoticeState

TODAY = date(2026, 10, 13)  # terça-feira


@pytest.mark.parametrize(
    ("text", "when", "hour", "where", "what"),
    [
        (
            "Colisão traseira na Av. Fictícia, ontem às 18h",
            date(2026, 10, 12),
            time(18),
            "Av Fictícia",
            True,
        ),
        (
            "Ontem por volta das 19:30 um carro bateu na minha traseira na Rua das Flores, 120",
            date(2026, 10, 12),
            time(19, 30),
            "Rua das Flores",
            True,
        ),
        (
            "anteontem fui fechado e bati no poste da rodovia SP-280",
            date(2026, 10, 11),
            None,
            "rodovia SP-280",
            True,
        ),
        (
            "na sexta à noite colidi no estacionamento do shopping",
            date(2026, 10, 9),
            None,
            "estacionamento do shopping",
            True,
        ),
        (
            "no dia 10/10/2026 às 8h30 colidi no cruzamento da Av. Brasil",
            date(2026, 10, 10),
            time(8, 30),
            "cruzamento da Av Brasil",
            True,
        ),
        ("foi em 12/12, bati na Rua Augusta", date(2025, 12, 12), None, "Rua Augusta", True),
        ("hoje de manhã", TODAY, None, None, False),
        ("Rua Augusta", None, None, "Rua Augusta", False),
        ("bati o carro na rua", None, None, None, True),  # "na rua" é vago
        ("Fui ao mercado comprar pão", None, None, None, False),
    ],
)
def test_extract_event(
    text: str, when: date | None, hour: time | None, where: str | None, what: bool
) -> None:
    e = extract_event(text, TODAY)
    assert e.event_date == when
    assert e.event_time == hour
    assert e.location == where
    assert bool(e.what) is what


def test_future_date_is_flagged() -> None:
    e = extract_event("aconteceu em 15/10 na Av. Paulista", TODAY)
    assert e.future_date and e.event_date is None


def _run(texts: list[str]) -> list[dict]:  # type: ignore[type-arg]
    node = nodes.build(load_messages(), max_attempts=3, today=lambda: TODAY)
    state = NoticeGraphState(sub=NoticeState(step="await_description"))
    outs = []
    for t in texts:
        out = node(NoticeGraphState(text=t, sub=state.sub))
        state = NoticeGraphState(sub=out["sub"])
        outs.append(out)
    return outs


def test_asks_only_for_missing_and_accumulates() -> None:
    first, second, third = _run(["Bati o carro", "foi ontem", "na Av. Paulista, 1000"])
    msg1 = first["result"].user_message
    assert "quando aconteceu" in msg1 and "onde aconteceu" in msg1 and "o que aconteceu" not in msg1
    msg2 = second["result"].user_message
    assert "onde aconteceu" in msg2 and "quando aconteceu" not in msg2 and "Já anotei" in msg2
    assert "result" not in third  # completo: segue para a avaliação de cobertura
    assert third["sub"].step == "assess"
    assert third["sub"].event["location"] == "Av Paulista"
    assert third["sub"].event["event_date"] == "2026-10-12"


def test_no_progress_counts_attempts_until_failure() -> None:
    outs = _run(["oi", "não sei", "hmm"])
    assert [o["result"].status for o in outs] == ["needs_input", "needs_input", "failed"]


def test_future_date_asks_for_confirmation() -> None:
    (out,) = _run(["bati na Av. Paulista em 20/10"])
    assert "está no futuro" in out["result"].user_message
