"""Classificação de intenção do Orquestrador (desvios do roteiro).

Regras (configs/orchestrator.yaml) sempre; LLM apenas quando as regras não resolvem e a flag
`orchestrator.intent_llm_enabled` está ligada. Respostas curtas e anexos nunca vão ao LLM.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel

from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.prompts import load_prompt

Intent = Literal[
    "continuar_etapa",
    "corrigir_dado_anterior",
    "duvida",
    "consulta_apolice",
    "status",
    "cancelar",
    "falar_com_humano",
    "fora_de_escopo",
]
CPF_LIKE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")


class IntentResult(BaseModel):
    intent: Intent
    source: Literal["regras", "llm", "padrão"]
    detail: str = ""


class LLMIntent(BaseModel):
    intent: Intent
    confidence: float
    justification: str


class IntentClassifier:
    def __init__(self, config: dict[str, Any], llm: LLMClient | None = None) -> None:
        self.patterns = {
            intent: [re.compile(p) for p in patterns]
            for intent, patterns in (config.get("intents") or {}).items()
        }
        llm_cfg = config.get("llm") or {}
        self.min_words = int(llm_cfg.get("min_words", 3))
        self.min_confidence = float(llm_cfg.get("min_confidence", 0.6))
        self.llm = llm

    def by_rules(self, text: str) -> IntentResult | None:
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if match := pattern.search(text):
                    return IntentResult(intent=intent, source="regras", detail=match.group(0))
        return None

    async def classify(
        self, text: str, *, stage: str, question: str, has_attachments: bool = False
    ) -> IntentResult:
        if found := self.by_rules(text):
            return found
        default = IntentResult(intent="continuar_etapa", source="padrão")
        if (
            self.llm is None
            or has_attachments
            or len(text.split()) < self.min_words
            or CPF_LIKE.search(text)
        ):
            return default
        prompt = load_prompt("orchestrator/intent")
        try:
            resp = await self.llm.chat(
                [
                    {"role": "system", "content": prompt.render(stage=stage, question=question)},
                    {"role": "user", "content": text},
                ],
                role="intent",
                response_model=LLMIntent,
                prompt_version=prompt.ref,
            )
        except LLMError:
            return default
        out = LLMIntent.model_validate(resp.parsed)
        if out.intent == "continuar_etapa" or out.confidence < self.min_confidence:
            return IntentResult(intent="continuar_etapa", source="llm", detail=out.justification)
        return IntentResult(intent=out.intent, source="llm", detail=out.justification)
