# ADR-0005 — Espera pelo cliente via `awaiting` no estado (sem `interrupt()`)

- **Status:** aceito (aprovado no plano das Fases 0–1)
- **Data:** 2026-10-12

## Contexto
O briefing pede uma invocação do grafo por mensagem, guardrails de entrada em toda mensagem e
espera com `interrupt()`. Com `interrupt()` dentro do especialista, o `Command(resume=...)` retoma
no nó interrompido e **pula o Guardrails de entrada**.

## Decisão
Cada turno roda o grafo inteiro: `pause_check → guardrails_in → orchestrator → especialista →
transition → guardrails_out → send → END`. A espera é representada por `awaiting` (etapa + campo)
no `GlobalState`, persistido pelo checkpointer (`thread_id = conversation_id`). Com `awaiting`
setado, o Orquestrador despacha direto ao especialista da etapa. Especialistas são máquinas de
estado retomáveis via sub-estado. `interrupt()` fica reservado para handoff humano.

**Alternativa rejeitada:** rodar o Guardrails de entrada na API antes de `Command(resume=...)` —
duplica o pipeline fora do grafo e esconde o veredito do trace.

## Consequências
Todo turno passa pelos guardrails e gera eventos uniformes; o grafo é testável turno a turno.
