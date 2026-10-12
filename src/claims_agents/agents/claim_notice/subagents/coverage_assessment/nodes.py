"""Subagente de avaliação preliminar de cobertura (stub: a Triagem já validou colisão)."""

from typing import Any

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.coverage_assessment.schemas import (
    CoverageAssessment,
)
from claims_agents.observability.emit import emit

NAME = "coverage_assessment"


def coverage_assessment(state: NoticeGraphState) -> dict[str, Any]:
    sub = state.sub.model_copy(deep=True)
    assessment = CoverageAssessment(
        covered=True, reason="Cobertura de colisão verificada na Triagem"
    )
    sub.step = "register"
    emit(
        "coverage_assessed", subagent=NAME, details=assessment.reason, data=assessment.model_dump()
    )
    return {"sub": sub}
