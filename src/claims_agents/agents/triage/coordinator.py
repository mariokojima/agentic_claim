"""Coordenador da Triagem: escolhe o próximo subagente a partir do sub-estado."""

from claims_agents.agents.triage.state import TriageGraphState


def next_subagent(state: TriageGraphState) -> str:
    if state.sub.step in ("start", "await_cpf"):
        return "customer_validation"
    return "decision"


def after_validation(state: TriageGraphState) -> str:
    return "end" if state.result is not None else "decision"
