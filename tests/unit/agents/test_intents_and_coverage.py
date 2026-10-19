import pytest

from claims_agents.agents.claim_notice.subagents.coverage_assessment.nodes import assess
from claims_agents.agents.orchestrator.intent import IntentClassifier
from claims_agents.agents.shared.event_extraction import extract_damages
from claims_agents.core.settings import load_config
from claims_agents.domain import ClaimStage
from claims_agents.graph.transitions import decide_transition
from claims_agents.state import StageResult

RULES = IntentClassifier(load_config("orchestrator"))


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("quero falar com um atendente", "falar_com_humano"),
        ("prefiro conversar com alguém da equipe", "falar_com_humano"),
        ("não quero falar com robô", "falar_com_humano"),
        ("desisto", "cancelar"),
        ("pode cancelar o atendimento", "cancelar"),
        ("não quero mais abrir o aviso", "cancelar"),
        ("qual o status do meu sinistro?", "status"),
        ("qual é o meu protocolo", "status"),
        ("na verdade foi anteontem", "corrigir_dado_anterior"),
        ("me enganei no endereço", "corrigir_dado_anterior"),
        ("quanto tempo demora?", "duvida"),
        ("tem franquia?", "duvida"),
        ("quero cancelar minha apólice", None),  # não é cancelar o atendimento
        ("Bati o carro", None),
        ("sim", None),
    ],
)
def test_intent_rules(text: str, intent: str | None) -> None:
    found = RULES.by_rules(text)
    assert (found.intent if found else None) == intent


async def test_short_answers_and_cpf_never_go_to_llm() -> None:
    from claims_agents.core.llm import FakeLLMClient

    llm = FakeLLMClient([])
    clf = IntentClassifier(load_config("orchestrator"), llm)
    for t in ("sim", "não sei", "529.982.247-25", "ok obrigado"):
        assert (await clf.classify(t, stage="TRIAGEM", question="?")).intent == "continuar_etapa"
    assert llm.calls == []


def test_cancel_transition() -> None:
    result = StageResult(status="rejected", reason="r", payload={"cancelled_by": "cliente"})
    out = decide_transition(ClaimStage.AVISO, result, "allow", 0, 5)
    assert out.new_stage == ClaimStage.CANCELADO and out.message_key == "transition.cancelled"
    assert ClaimStage.CANCELADO.is_terminal


def test_coverage_assessment() -> None:
    full = ["COLISAO", "TERCEIROS"]
    assert assess(full, has_third_parties=False).third_party_coverage is None
    assert assess(full, has_third_parties=True).third_party_coverage is True
    assert assess(["COLISAO"], has_third_parties=True).third_party_coverage is False
    assert not assess(["VIDROS"], has_third_parties=False).covered


@pytest.mark.parametrize(
    ("text", "damages"),
    [
        ("amassou o para-choque traseiro e quebrou a lanterna", "para-choque traseiro, lanterna"),
        ("o farol e o capô ficaram destruídos", "farol, capô"),
        ("raspei a lateral esquerda", "lateral esquerda"),
        ("sem danos", "sem danos aparentes"),
        ("Bati o carro", None),
    ],
)
def test_extract_damages(text: str, damages: str | None) -> None:
    assert extract_damages(text) == damages
