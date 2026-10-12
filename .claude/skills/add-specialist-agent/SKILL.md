---
name: add-specialist-agent
description: Adiciona um novo especialista (subgrafo LangGraph) ao fluxo de sinistro, incluindo etapa, roteamento, transição, prompts, eventos e testes. Use ao criar uma nova etapa do processo.
---

# Adicionar especialista

Leia antes: `docs/architecture.md` §2–4 e um especialista existente (`src/claims_agents/agents/triage/`).

## Passos
1. **Etapa**: adicione o valor em `ClaimStage` (`domain/enums.py`) e a linha na tabela de
   transições de `graph/transitions.py` (`completed`/`rejected` → próxima etapa). Só esse arquivo muda `claim_stage`.
2. **Sub-estado**: `agents/<nome>/state.py` com um `BaseModel` namespaced; registre o campo em
   `GlobalState` (`state/global_state.py`) com default.
3. **Subgrafo**: `agents/<nome>/graph.py` (`build_<nome>_graph(registry) -> CompiledStateGraph`),
   `coordinator.py` (decide o próximo subagente a partir do sub-estado) e `subagents/` (use `add-subagent`).
   O subgrafo devolve `last_result: StageResult` e, se precisar de input, `awaiting` + mensagem no `outbox`.
4. **Roteamento**: adicione `ClaimStage.X → "<nome>"` em `agents/orchestrator/routing_policy.py`
   e o nó em `graph/build_graph.py` (aresta para `transition`).
5. **Prompts**: `prompts/<nome>/*.md` (pt-BR, versionados no cabeçalho `version:`).
6. **Config**: regras/checklists em `configs/<nome>*.yaml`; nada hardcoded.
7. **Painel**: adicione o nó em `frontend/src/flow/nodes.ts` (id = nome do nó no grafo).
8. **Docs**: atualizar tabela de especialistas em `docs/architecture.md`; ADR se houver decisão.

## Regras
- Não importar nada de `agents/orchestrator/`. O contrato de saída é só `StageResult`.
- Tools somente via `ToolRegistry`/interfaces; mensagens ao cliente só via `outbox`.
- Emitir eventos com `emit()` (`observability/emit.py`), nunca gravar no event store.

## Testes exigidos
- `tests/unit/agents/<nome>/`: cada caminho (`completed`, `needs_input`, `rejected`, `failed`) com LLM falso.
- `tests/integration/`: turno multi-etapa passando pelo novo especialista com checkpointer temporário.
- `make check` verde.
