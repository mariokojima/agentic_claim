---
name: run-scenarios
description: Executa os cenários de avaliação (smoke ou bateria completa) contra o grafo e resume métricas da dissertação. Use para validar mudanças ou rodar experimentos comparativos.
---

# Rodar cenários

## Comandos
```bash
make scenarios                    # smoke (13 cenários), só regras, sem LLM — segundos
make evaluate                     # full (28) × todos os experimentos, LLM real do .env
uv run python scripts/run_scenarios.py --suite full --experiments baseline,llm_full --allow-real-llm
uv run python scripts/run_scenarios.py --suite smoke --experiments no_guardrails
```
Relatório: `reports/<data>_<suíte>/report.md` (+ `summary.json`, `results.jsonl`); o último fica
em `reports/latest.md`. Padrão sequencial (`--concurrency 1`): concorrência infla a latência.

## Cenários (`data/evaluation/scenarios.yaml`)
Campos: `id`, `title`, `category`, `suites`, `customer` (prefixo do nome nos fixtures),
`attack`, `requires_llm`, `turns` (texto com `{cpf}`, `{text, documents}` com arquivos de
`public/<cpf>/` ou `_invalidos/`, ou `{timer: reminder|timeout}`) e `expected` (`final_stage`,
`terminal_reason`, `specialists`, `tools_required`, `tools_forbidden`, `intents`).
Novo cenário: adicione ao YAML; se for resolvível só com regras, o teste
`tests/evals/test_scenarios.py` passa a exigi-lo no smoke.

## Experimentos (`configs/experiments/*.yaml`)
`baseline`, `no_guardrails`, `llm_fallback`, `llm_routing`, `llm_full`, `llm_full_lite`.
Cada um sobrescreve `settings`, `guardrails` e `models` (merge profundo). `llm: true` exige
`--allow-real-llm` e chave no `.env`.

## Como resumir
Delegue a execução a um subagente de modelo menor e traga só: tabela comparativa, falhas
(esperado × obtido) e observações sobre falhas/fallback do LLM. Não cole logs inteiros.
