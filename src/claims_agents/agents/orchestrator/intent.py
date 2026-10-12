"""Classificação de intenção por LLM (flag `orchestrator.intent_llm_enabled`).

Fase 1: stub que sempre devolve `continuar_etapa`. A implementação com LLM entra na Fase 4.
"""

from typing import Literal

Intent = Literal[
    "continuar_etapa",
    "corrigir_dado_anterior",
    "duvida",
    "status",
    "cancelar",
    "falar_com_humano",
    "fora_de_escopo",
]


async def classify_intent(text: str) -> Intent:
    return "continuar_etapa"
