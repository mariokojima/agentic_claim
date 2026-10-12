import pytest

from claims_agents.domain import ClaimStage
from claims_agents.graph.transitions import decide_transition
from claims_agents.state import StageResult


def res(status: str) -> StageResult:
    return StageResult(status=status, reason="r")


@pytest.mark.parametrize(
    ("stage", "expected", "next_node"),
    [
        (ClaimStage.TRIAGEM, ClaimStage.AVISO, "orchestrator"),
        (ClaimStage.AVISO, ClaimStage.DOCUMENTOS, "orchestrator"),
        (ClaimStage.DOCUMENTOS, ClaimStage.CONCLUIDO, "guardrails_out"),
    ],
)
def test_completed_advances(stage: ClaimStage, expected: ClaimStage, next_node: str) -> None:
    out = decide_transition(stage, res("completed"), "allow", hops=0, max_hops=5)
    assert out.new_stage == expected and out.next_node == next_node


def test_needs_input_keeps_stage() -> None:
    out = decide_transition(ClaimStage.AVISO, res("needs_input"), "allow", 0, 5)
    assert out.new_stage == ClaimStage.AVISO and out.next_node == "guardrails_out"
    assert not out.changed(ClaimStage.AVISO)


def test_rejected_triage_is_orientado() -> None:
    out = decide_transition(ClaimStage.TRIAGEM, res("rejected"), "allow", 0, 5)
    assert out.new_stage == ClaimStage.ORIENTADO and out.terminal_reason == "rejected:r"


def test_failed_escalates_with_message() -> None:
    out = decide_transition(ClaimStage.DOCUMENTOS, res("failed"), "allow", 0, 5)
    assert out.new_stage == ClaimStage.ESCALADO_HUMANO and out.message_key == "transition.failed"


@pytest.mark.parametrize(
    ("decision", "expected"),
    [("block", ClaimStage.BLOQUEADO), ("escalate", ClaimStage.ESCALADO_HUMANO)],
)
def test_input_guardrail_overrides(decision: str, expected: ClaimStage) -> None:
    out = decide_transition(ClaimStage.TRIAGEM, None, decision, 0, 5)  # type: ignore[arg-type]
    assert out.new_stage == expected and out.next_node == "guardrails_out"


def test_hop_limit_escalates() -> None:
    out = decide_transition(ClaimStage.TRIAGEM, res("completed"), "allow", hops=5, max_hops=5)
    assert out.new_stage == ClaimStage.ESCALADO_HUMANO and out.terminal_reason == "max_hops"
