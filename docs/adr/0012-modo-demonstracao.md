# ADR-0012 — Modo demonstração (atraso ilustrativo no fluxo)

- **Status:** aceito
- **Data:** 2026-10-12

## Contexto
Sem LLM, um turno inteiro roda em ~150 ms e o painel não deixa ver o fluxo entre as caixas.
Para apresentações, o autor pediu um atraso perceptível por caixa.

## Decisão
`settings.demo.node_delay_ms` (atraso no início de cada nó do grafo principal, aplicado por
`with_demo_delay` em `build_graph.py`) e `settings.demo.tool_delay_ms` (atraso em cada tool, aplicado
pelo `ResilientTool` fora do timeout). As tools emitem `tool_start` (processando) além de `tool_call`.
Default **0** em `configs/settings.yaml`; `make run` liga (500 ms/400 ms) e `make run DEMO_DELAY_MS=0`
desliga. Os agentes não conhecem o modo demonstração.

## Consequências
Latências medidas em modo demonstração não são válidas para a dissertação: testes, runner de
cenários e experimentos devem rodar com atraso 0.
