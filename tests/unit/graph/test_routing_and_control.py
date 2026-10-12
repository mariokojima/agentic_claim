import pytest

from claims_agents.agents.orchestrator.routing_policy import route
from claims_agents.domain import ClaimStage
from claims_agents.graph.control import PauseControl
from claims_agents.state import Awaiting


def test_route_by_table() -> None:
    assert route(ClaimStage.TRIAGEM, None).target == "triage"
    assert route(ClaimStage.AVISO, None).target == "claim_notice"
    assert route(ClaimStage.DOCUMENTOS, None).target == "documents"


def test_route_explains_pending_question() -> None:
    d = route(ClaimStage.AVISO, Awaiting(stage="AVISO", field="description"))
    assert d.target == "claim_notice" and "description" in d.reason


def test_terminal_stage_has_no_specialist() -> None:
    with pytest.raises(ValueError):
        route(ClaimStage.CONCLUIDO, None)


def test_pause_control_global_and_per_conversation() -> None:
    c = PauseControl()
    c.set(True, "a")
    assert c.is_paused("a") and not c.is_paused("b")
    c.set(True)
    assert c.is_paused("b")
    snap = c.set(False)
    assert snap.global_paused is False and snap.conversations == ["a"]
