# ADR-0011 — Eventos do painel a partir de uma fonte única

- **Status:** aceito
- **Data:** 2026-10-12

## Decisão
`AgentEvent` é produzido apenas por `observability/adapter.py`, que consome o streaming do LangGraph
(`stream_mode=["updates", "custom"]`). Nós emitem eventos de domínio (tool, rota, veredito,
transição) via helper `emit()` que usa `get_stream_writer()`. O adaptador persiste no event store
e publica no bus do WebSocket. PII é mascarada no adaptador.

## Consequências
Nada de gravação ad hoc; os testes verificam eventos consumindo o mesmo stream.
