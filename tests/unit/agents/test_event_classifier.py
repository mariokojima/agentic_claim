import pytest

from claims_agents.agents.triage.subagents.event_classification.classifier import EventClassifier
from claims_agents.core.settings import load_config

CLASSIFIER = EventClassifier(load_config("triage_rules"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bati o carro", "COLISAO"),
        ("sofri uma batida no cruzamento", "COLISAO"),
        ("fui atingido por uma moto", "COLISAO"),
        ("um carro amassou minha porta no estacionamento", "COLISAO"),
        ("bati e quebrou o para-brisa", "COLISAO"),  # prioridade: colisão > vidros
        ("bati numa árvore", "COLISAO"),
        ("roubaram meu carro", "ROUBO_FURTO"),
        ("fui assaltado e levaram o carro", "ROUBO_FURTO"),
        ("o carro pegou fogo", "INCENDIO"),
        ("meu carro ficou alagado na enchente", "FENOMENO_NATURAL"),
        ("caiu uma árvore em cima do carro", "FENOMENO_NATURAL"),
        ("o para-brisa trincou", "VIDROS"),
        ("o retrovisor quebrou", "VIDROS"),
        ("o carro não liga, bateria arriada", "ASSISTENCIA"),
        ("pneu furado na estrada", "ASSISTENCIA"),
        ("quero a segunda via do boleto", "NAO_SINISTRO"),
        ("não sei", None),
        ("oi", None),
    ],
)
def test_classification(text: str, expected: str | None) -> None:
    assert CLASSIFIER.classify(text).event_type == expected


def test_injuries_flag() -> None:
    assert CLASSIFIER.classify("bati e tem gente ferida").has_injuries
    assert not CLASSIFIER.classify("bati o carro").has_injuries
