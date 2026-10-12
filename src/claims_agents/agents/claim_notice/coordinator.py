"""Coordenador do Aviso: sequência coleta → cobertura → registro, retomável por `sub.step`."""

from claims_agents.agents.claim_notice.state import NoticeGraphState

STEP_TO_SUBAGENT = {
    "start": "event_data_collection",
    "await_description": "event_data_collection",
    "assess": "coverage_assessment",
    "register": "registration",
}


def next_subagent(state: NoticeGraphState) -> str:
    if state.result is not None:
        return "end"
    return STEP_TO_SUBAGENT.get(state.sub.step, "end")
