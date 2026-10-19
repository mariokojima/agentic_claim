"""Classificador LLM dos guardrails (Fase 6): uma chamada avalia os três estágios.

Camada após as regras determinísticas: só roda quando elas não decidiram `block`, para mensagens
com conteúdo (`min_words`), na(s) direção(ões) configurada(s). Falha do LLM → nenhuma checagem
extra (as regras continuam valendo).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from claims_agents.core.llm import LLMClient, LLMError
from claims_agents.core.prompts import load_prompt
from claims_agents.state import GuardrailCheck

Stage = Literal["security", "ethics", "corporate"]


class StageJudgement(BaseModel):
    decision: Literal["allow", "block", "escalate"]
    reason: str


class LLMGuardrailVerdict(BaseModel):
    security: StageJudgement
    ethics: StageJudgement
    corporate: StageJudgement
    confidence: float


class GuardrailLLMClassifier:
    def __init__(self, config: dict[str, Any], llm: LLMClient | None) -> None:
        cfg = config.get("llm_classifier") or {}
        self.llm = llm if cfg.get("enabled", False) and config.get("enabled", True) else None
        self.directions = set(cfg.get("directions", ["input"]))
        self.min_words = int(cfg.get("min_words", 4))
        self.min_confidence = float(cfg.get("min_confidence", 0.7))
        stages = config.get("stages", {})
        self.enabled_stages: set[str] = {
            s for s in ("security", "ethics", "corporate") if stages.get(s, {}).get("enabled", True)
        }

    def applies(self, direction: str, text: str) -> bool:
        return (
            self.llm is not None
            and direction in self.directions
            and len(text.split()) >= self.min_words
        )

    async def classify(
        self, direction: Literal["input", "output"], text: str
    ) -> list[GuardrailCheck]:
        if self.llm is None:
            return []
        prompt = load_prompt(f"guardrails/{direction}_classifier")
        try:
            resp = await self.llm.chat(
                [{"role": "system", "content": prompt.text}, {"role": "user", "content": text}],
                role="guardrail_classifier",
                response_model=LLMGuardrailVerdict,
                prompt_version=prompt.ref,
            )
        except LLMError:
            return []
        out = LLMGuardrailVerdict.model_validate(resp.parsed)
        if out.confidence < self.min_confidence:
            return []
        checks: list[GuardrailCheck] = []
        for stage in ("security", "ethics", "corporate"):
            judgement: StageJudgement = getattr(out, stage)
            if stage not in self.enabled_stages or judgement.decision == "allow":
                continue
            decision = judgement.decision
            if direction == "output" and decision == "escalate":
                decision = "block"
            checks.append(
                GuardrailCheck(
                    stage=stage,
                    decision=decision,
                    reason=f"[llm_classifier] {judgement.reason}",
                    rule="llm_classifier",
                )
            )
        return checks
