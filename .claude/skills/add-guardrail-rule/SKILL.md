---
name: add-guardrail-rule
description: Adiciona uma regra de guardrail (determinística ou classificador LLM) a um estágio — segurança, ética ou corporativo — na entrada ou saída, com config e casos de teste. Use ao endurecer os guardrails.
---

# Adicionar regra de guardrail

## Passos
1. Escolha estágio (`security` | `ethics` | `corporate`) e direção (`input` | `output`).
2. **Determinística** (preferir primeiro): adicione em `agents/guardrails/<estagio>.py` uma função
   `check_<nome>(text, ctx) -> RuleHit | None`; padrões (regex, listas) ficam em
   `configs/guardrails.yaml` sob `<estagio>.<direcao>.rules.<nome>` com `enabled`, `action`
   (`allow|sanitize|block|escalate`) e `patterns`.
3. **LLM** (Fase 6): prompt em `prompts/guardrails/<estagio>_<direcao>.md`, saída estruturada
   `ClassifierVerdict`; executa só se nenhuma regra determinística decidiu `block`.
4. O agregador (`agents/guardrails/aggregator.py`) combina por precedência
   `block > escalate > sanitize > allow` e grava a justificativa em `guardrail_verdicts`.
5. `sanitize` deve devolver o texto transformado (ex.: CPF mascarado), nunca descartar silenciosamente.

## Regras
- Toda regra precisa ser desligável por config (experimentos com/sem guardrails).
- Justificativa sempre em pt-BR e sem repetir a PII detectada.

## Testes exigidos (`tests/unit/guardrails/test_<estagio>.py`)
- Casos positivos (dispara) e negativos (não dispara — falso positivo) para cada padrão.
- Regra desligada não dispara. Veredito aparece como evento `guardrail_verdict`.
- Adicione um cenário em `data/evaluation/` se a regra cobre um ataque novo.
