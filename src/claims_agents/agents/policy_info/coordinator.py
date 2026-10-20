"""Coordenador de Consultas: classificação → identificação (só tópicos de apólice) → resposta."""

from claims_agents.agents.policy_info.state import PolicyInfoGraphState
from claims_agents.agents.policy_info.subagents.answer.nodes import POLICY_TOPICS


def after_classification(state: PolicyInfoGraphState) -> str:
    # tópicos da apólice exigem o segurado; perguntas livres usam a apólice se ele já for conhecido
    known = bool(state.customer and state.customer.cpf)
    if state.topic in POLICY_TOPICS or (state.topic is None and known):
        return "customer_lookup"
    return "answer"
