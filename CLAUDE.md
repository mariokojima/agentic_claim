# CLAUDE.md — PoC agêntica de abertura de sinistro

PoC de mestrado: sistema multiagente (LangGraph) que conduz a abertura de um sinistro de
**automóvel/colisão**, da primeira mensagem do segurado (WhatsApp simulado) até `CONCLUIDO`.
Tudo é mockado e **somente com dados sintéticos**.

Fontes de verdade (não reler `docs/00-briefing.md`; use estes):
- `docs/requirements.md`: requisitos funcionais e não funcionais, escopo e métricas
- `docs/architecture.md`: grafo, estados, contratos, eventos e API
- `docs/adr/`: decisões e defaults (itens marcados [CONFIRMAR]/[PREENCHER] ficam lá)
- `docs/ui/mockup.jpeg`: layout do frontend (os nomes de agentes e tools no mockup são ilustrativos)

## Comandos

```bash
uv sync                 # instala dependências (Python 3.12, lockfile uv.lock)
make check              # ruff check + ruff format --check + mypy + pytest -q  (deve passar ao fim de cada fase)
make test               # pytest -q
make fmt                # ruff format + ruff check --fix
make seed               # carrega fixtures sintéticos no SQLite (data/claims.db)
make run                # API FastAPI em http://localhost:8000
make dev-front          # frontend Vite em http://localhost:5173 (proxy para a API)
make scenarios          # runner de cenários de avaliação (Fase 6)
```

Rodar um teste: `uv run pytest -q tests/unit/tools/test_customer_data.py -k not_found`.

## Layout

```
configs/      models.yaml, settings.yaml, guardrails.yaml, triage_rules.yaml, documents_checklist.yaml
prompts/      prompts versionados (espelham agents/)
data/         fixtures/ (clientes, apólices) · evaluation/ (cenários)
src/claims_agents/
  core/          settings, logging (mascara PII), fábrica de LLM, erros
  domain/        Customer, Policy, Claim, Document, enums
  state/         global_state.py (GlobalState), contracts.py (StageResult)
  graph/         build_graph.py, transitions.py, checkpointer.py
  agents/        guardrails/ orchestrator/ triage/ claim_notice/ documents/
  tools/         interfaces.py (Protocol), schemas.py, mocks/, real/, registry.py
  observability/ AgentEvent, adaptador de streaming, event store, métricas
  api/           FastAPI: chat, WebSocket, painel, controle
frontend/     Vite + React + TS (chat à esquerda, painel à direita)
tests/        unit/ integration/ e2e/ evals/
scripts/      seed, runner de cenários
```

Cada especialista é um subgrafo: `graph.py`, `state.py`, `coordinator.py`, `subagents/<nome>/{nodes.py,schemas.py}`.

## Regras invariantes (não violar)

1. **Nunca usar dados reais.** Apenas fixtures sintéticos; PII mascarada em logs e eventos.
2. **Toda mensagem ao cliente passa pelo `outbox` e pelo Guardrails de saída** antes do envio.
   Especialistas nunca enviam; o único envio real acontece no nó final `send`.
3. **Tools só via interface** (`tools/interfaces.py`), obtidas do `ToolRegistry`. Nenhum agente importa `tools/mocks`.
4. **`claim_stage` só muda em `graph/transitions.py`.**
5. **Prompts em `prompts/`** (versionados); modelos, regras e flags em `configs/`. Nada de prompt ou regra hardcoded.
6. **Segredos só em `.env`** (nunca versionado). Use `.env.example` como modelo.
7. **Sem LLM real em testes** unitários e de integração: use `FakeListChatModel` / respostas gravadas.
8. **Eventos do painel vêm de uma fonte única**: o adaptador de streaming (`observability/adapter.py`).
   Nós emitem eventos customizados via `get_stream_writer()`/helper `emit()`; nada de gravar no event store ad hoc.
9. Especialistas só conhecem o contrato `StageResult`; não importam nada do Orquestrador.

## Convenções

- Código e identificadores em **inglês**; docs, prompts, mensagens ao cliente e rótulos de UI em **pt-BR**.
- Valores de enum de domínio em pt-BR maiúsculo quando são estados do processo (`TRIAGEM`, `AVISO`, `CONCLUIDO`...).
- Pydantic v2 para todo estado, contrato e schema de tool. `mypy --strict` em `state/`, `tools/`, `domain/`.
- Funções de nó: `def node(state: GlobalState) -> dict` retornando apenas o delta do estado.
- Erros de tool: `ToolError` e subclasses (`NotFound`, `ToolTimeout`, `UpstreamError`) em `core/errors.py`.
- Testes espelham `src/` em `tests/unit/`; usar fixtures de `tests/conftest.py` (SQLite temporário, registry mock).
- Commits pequenos, por tarefa, em pt-BR no imperativo (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Novas dependências só com justificativa (no commit ou ADR).

## Skills de desenvolvimento (`.claude/skills/`)

`add-specialist-agent` · `add-subagent` · `add-tool` · `add-guardrail-rule` · `run-scenarios`.
Use-as ao estender o sistema; elas listam os arquivos a tocar e os testes exigidos.

## Fluxo de trabalho

- Trabalho em fases (ver `docs/requirements.md` §Fases). Ao fim de cada fase: `make check`, resumo, aguardar aprovação.
- Uma sessão por fase ou por subagente. Ler só os arquivos necessários; editar com `Edit`.
- Delegar execução de testes, lint e leitura de logs a subagente de modelo menor, trazendo só o resumo.
- Confirmar APIs de LangGraph/LangChain na documentação oficial (ou no código instalado em `.venv`) antes de usar algo novo.
- Respostas curtas; perguntar só o que bloqueia, agrupando dúvidas.
