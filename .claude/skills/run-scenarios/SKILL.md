---
name: run-scenarios
description: Executa os cenários de avaliação (smoke ou bateria completa) contra o grafo e resume métricas da dissertação. Use para validar mudanças ou rodar experimentos comparativos.
---

# Rodar cenários

## Comandos
```bash
make scenarios                                   # smoke (~10 cenários), LLM falso/gravado
uv run python scripts/run_scenarios.py --suite full --config configs/experiments/<exp>.yaml
uv run python scripts/run_scenarios.py --scenario happy_path -v
```

## Cenários (`data/evaluation/<suite>/*.yaml`)
Cada cenário: `id`, `customer_phone`, `turns` (texto + anexos), `expected` (estado terminal,
especialistas visitados, tools chamadas, vereditos de guardrail). Cobertura mínima: caminho feliz,
dados faltantes, apólice vencida, evento não coberto, fraude, injection direta e indireta (documento),
fora de escopo, pedido de humano.

## Saída
`reports/<timestamp>/` com `results.jsonl` (um por cenário) e `summary.md` com: acerto de roteamento,
taxa de conclusão, correção das tools, bloqueio de ataques vs. falsos positivos, turnos, latência,
tokens e custo estimado.

## Como resumir
Delegue a execução a um subagente de modelo menor e traga apenas: nº de cenários, falhas (id +
esperado vs. obtido) e as métricas agregadas. Não cole logs inteiros.

## Experimentos
Configs em `configs/experiments/`: `no_guardrails.yaml`, `intent_llm_on.yaml`, `model_<x>.yaml`.
Rodar com LLM real exige `.env` com chave e `--allow-real-llm`.
