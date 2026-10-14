"""Coordenador da Triagem: escolhe o próximo subagente a partir do sub-estado.

Sequência: validação do segurado → classificação do ocorrido → decisão de elegibilidade.
"""

from claims_agents.agents.triage.state import TriageGraphState


def next_subagent(state: TriageGraphState) -> str:
    step = state.sub.step
    if step in ("start", "await_cpf"):
        return "customer_validation"
    if step in ("classify", "await_event"):
        return "event_classification"
    return "decision"


def after_validation(state: TriageGraphState) -> str:
    if state.result is not None:
        return "end"
    # cliente inexistente pula a classificação (a decisão rejeita com orientação)
    return "decision" if state.sub.step == "decide" else "event_classification"


def after_classification(state: TriageGraphState) -> str:
    return "end" if state.result is not None else "decision"
