"""Subagente de avaliação preliminar de cobertura, a partir das coberturas da apólice.

Determinístico e sem promessas: o resultado é "identificada/não identificada, sujeita à análise".
"""

from typing import Any

from claims_agents.agents.claim_notice.state import NoticeGraphState
from claims_agents.agents.claim_notice.subagents.coverage_assessment.schemas import (
    CoverageAssessment,
)
from claims_agents.observability.emit import emit
from claims_agents.state import StageResult

NAME = "coverage_assessment"


def assess(coverages: list[str], has_third_parties: bool) -> CoverageAssessment:
    covered = "COLISAO" in coverages
    third = ("TERCEIROS" in coverages) if has_third_parties else None
    reason = "Cobertura de colisão " + (
        "identificada na apólice" if covered else "ausente na apólice"
    )
    if third is not None:
        reason += "; danos a terceiros " + ("incluídos" if third else "não incluídos")
    return CoverageAssessment(covered=covered, reason=reason, third_party_coverage=third)


def coverage_assessment(state: NoticeGraphState) -> dict[str, Any]:
    sub = state.sub.model_copy(deep=True)
    result = assess(state.coverages, bool(sub.event.get("has_third_parties")))
    sub.event = dict(sub.event) | {"coverage": result.model_dump()}
    emit(
        "coverage_assessed",
        subagent=NAME,
        status="completed"
        if result.covered and result.third_party_coverage is not False
        else "warning",
        details=result.reason,
        data=result.model_dump(),
    )
    if not result.covered:
        return {
            "sub": sub,
            "result": StageResult(
                status="rejected",
                reason="no_coverage",
                payload={"rejection": "no_coverage"},
                user_message=None,
            ),
        }
    sub.step = "register"
    return {"sub": sub}
