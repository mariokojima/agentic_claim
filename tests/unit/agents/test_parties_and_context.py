import pytest

from claims_agents.agents.guardrails.stages import _context_rules
from claims_agents.agents.triage.subagents.parties.detector import PartiesDetector
from claims_agents.core.prompts import load_prompt
from claims_agents.core.settings import load_config

DETECTOR = PartiesDetector(load_config("triage_rules"))


@pytest.mark.parametrize(
    ("text", "third", "injuries"),
    [
        ("Bati o carro", None, None),
        ("bati no poste sozinho", False, None),
        ("bati o carro no muro da garagem", False, None),
        ("um cara entrou na contramão e pegou minha porta", True, None),
        ("fui atingido por uma moto", True, None),
        ("bati na traseira de outro carro, ninguém se feriu", True, False),
        ("tem um ferido", None, True),
        ("ninguém se machucou", None, False),  # negativa antes da positiva
    ],
)
def test_detect(text: str, third: bool | None, injuries: bool | None) -> None:
    found = DETECTOR.detect(text)
    assert (found.has_third_parties, found.has_injuries) == (third, injuries)


@pytest.mark.parametrize(
    ("answer", "asked", "third", "injuries"),
    [
        ("não", ["third_parties", "injuries"], False, False),
        ("não, só eu", ["third_parties", "injuries"], False, False),
        ("sim", ["third_parties"], True, None),
        ("sim", ["third_parties", "injuries"], None, None),  # ambíguo → LLM ou nova pergunta
        ("sim, outro carro, mas ninguém se machucou", ["third_parties", "injuries"], True, False),
    ],
)
def test_from_answer(
    answer: str, asked: list[str], third: bool | None, injuries: bool | None
) -> None:
    found = DETECTOR.from_answer(answer, asked)
    assert (found.has_third_parties, found.has_injuries) == (third, injuries)


RULES = {"recent_policy": {"enabled": True, "action": "escalate", "max_days": 7, "reason": "r"}}


def test_recent_policy_context_rule() -> None:
    ctx = {"policy_start_date": "2026-10-10", "event_date": "2026-10-12"}
    hit = _context_rules(RULES, ctx)
    assert hit is not None and hit.decision == "escalate" and "2 dia" in hit.reason
    assert _context_rules(RULES, ctx | {"event_date": "2026-11-30"}) is None
    assert _context_rules(RULES, {}) is None
    assert _context_rules({"recent_policy": {"enabled": False}}, ctx) is None


def test_prompts_are_versioned() -> None:
    for name in ("triage/event_classification", "triage/parties", "common/writer"):
        prompt = load_prompt(name)
        assert prompt.version == "1" and prompt.text and prompt.ref == f"{name}@v1"
    rendered = load_prompt("triage/parties").render(question="Q?", description="D")
    assert '"Q?"' in rendered and '"D"' in rendered
