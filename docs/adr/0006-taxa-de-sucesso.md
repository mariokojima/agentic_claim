# ADR-0006 — Definição de "Taxa de Sucesso"

- **Status:** proposto — **[CONFIRMAR]**
- **Data:** 2026-10-12

## Decisão
`taxa_sucesso = fluxos que terminam em CONCLUIDO ou ORIENTADO sem erro técnico nem escalonamento ÷
fluxos iniciados que já chegaram a estado terminal`. Configurável em `configs/settings.yaml`
(`metrics.success_terminal_states`, `metrics.count_open_flows`). Derivada do event store
(eventos `stage_transition` terminais e `error`).

## Consequências
`ORIENTADO` conta como sucesso (o sistema decidiu corretamente não abrir). `BLOQUEADO` não conta.
Fluxos ainda abertos ficam fora do denominador por default.
