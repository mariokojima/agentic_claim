"""Especialista Consultas: classificação da pergunta e composição das respostas (ADR-0019)."""

from datetime import date

import pytest

from claims_agents.agents.policy_info.knowledge import PolicyKnowledge
from claims_agents.agents.policy_info.subagents.answer.nodes import AnswerComposer
from claims_agents.core.messages import load_messages
from claims_agents.core.settings import load_config

CFG = load_config("policy_info")
KB = PolicyKnowledge(CFG)
COMPOSER = AnswerComposer(CFG, load_messages())
TODAY = date(2026, 10, 19)


def policy(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "number": "AUTO-1",
        "status": "ATIVA",
        "start_date": "2026-01-15",
        "end_date": "2027-01-14",
        "coverages": ["COLISAO", "VIDROS"],
        "vehicle_plate": "AAA0A00",
        "vehicle_model": "Onix",
    }
    return base | over


@pytest.mark.parametrize(
    ("text", "topic", "faq"),
    [
        ("o que é sinistro?", "faq", "sinistro"),
        ("tem franquia?", "faq", "franquia"),
        ("como funciona a renovação?", "faq", "renovacao_geral"),
        ("o que é cobertura de terceiros", "faq", "terceiros"),
        ("quando vence minha apólice?", "vencimento", None),
        ("quero renovar meu seguro", "renovacao", None),
        ("minha apólice está ativa?", "vigencia", None),
        ("minha apólice cobre vidros?", "coberturas", None),
        ("minha apólice cobre terceiros?", "coberturas", None),  # pessoal: prioriza a apólice
        ("qual o número da minha apólice", "dados_apolice", None),
        ("se eu emprestar o carro e ele bater, o seguro cobre?", None, None),  # hipotética
        ("quanto custa o seguro de um carro novo?", None, None),
    ],
)
def test_classify(text: str, topic: str | None, faq: str | None) -> None:
    assert KB.classify(text) == (topic, faq)


def test_coverage_asked() -> None:
    assert KB.coverage_asked("minha apólice cobre vidros?") == "VIDROS"
    assert KB.coverage_asked("o seguro cobre enchente?") == "COLISAO"  # casco cobre natureza
    assert KB.coverage_asked("quais são as minhas coberturas?") is None


def test_expiration_lines() -> None:
    assert "vence em 14/01/2027 (daqui a 87 dias)" in COMPOSER.line(
        "vencimento", policy(), TODAY, None
    )
    assert "venceu em 31/12/2025" in COMPOSER.line(
        "vencimento", policy(end_date="2025-12-31"), TODAY, None
    )
    assert "vence hoje" in COMPOSER.line("vencimento", policy(end_date="2026-10-19"), TODAY, None)


def test_renewal_windows() -> None:
    assert "de 15/12/2026 até 14/01/2027" in COMPOSER.line("renovacao", policy(), TODAY, None)
    assert "já está no período de renovação" in COMPOSER.line(
        "renovacao", policy(end_date="2026-11-01"), TODAY, None
    )
    assert "venceu em" in COMPOSER.line("renovacao", policy(end_date="2026-01-01"), TODAY, None)
    assert "cancelada" in COMPOSER.line("renovacao", policy(status="CANCELADA"), TODAY, None)


def test_coverage_lines() -> None:
    assert "sim, inclui a cobertura de vidros" in COMPOSER.line(
        "coberturas", policy(), TODAY, "VIDROS"
    )
    assert "não inclui a cobertura de roubo e furto" in COMPOSER.line(
        "coberturas", policy(), TODAY, "ROUBO_FURTO"
    )
    full = COMPOSER.line("coberturas", policy(), TODAY, None)
    assert "Colisão (casco" in full and "Vidros" in full


def test_multiple_policies_answer() -> None:
    text = COMPOSER.policy_answer(
        "vigencia", [policy(), policy(number="AUTO-2", status="VENCIDA")], TODAY, None
    )
    assert text.startswith("Aqui estão as informações das suas apólices:")
    assert "AUTO-1" in text and "AUTO-2" in text and "vencida" in text
