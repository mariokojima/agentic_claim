# Arquitetura

## 1. Visão geral

Um **grafo principal LangGraph** (`graph/build_graph.py`). Cada especialista é um **subgrafo**
com um coordenador e subagentes. Uma invocação do grafo por mensagem do usuário; estado
persistido por checkpointer SQLite com `thread_id = conversation_id` (ADR-0005).

```
START
  │
  ▼
pause_check ──pausado──► (mensagem fixa de handoff no outbox) ─────────────┐
  │ ativo                                                                  │
  ▼                                                                        │
guardrails_in  (fan-out: security ∥ ethics ∥ corporate → aggregator)       │
  │ allow/sanitize                     block/escalate ─► transition ───────┤
  ▼                                                                        │
orchestrator ◄──────────── etapa concluída (hops < max_hops) ──┐           │
  │ (tabela claim_stage → especialista; LLM só em desvios)     │           │
  ├──► triage ───────┐                                         │           │
  ├──► claim_notice ─┼──► transition ──────────────────────────┘           │
  └──► documents ────┘        │ aguardando cliente / terminal              │
                              ▼                                            │
                        guardrails_out ◄───────────────────────────────────┘
                              │
                              ▼
                            send  (único ponto que chama send_whatsapp)
                              │
                              ▼
                             END
```

## 2. Estados do processo

`ClaimStage`: `TRIAGEM → AVISO → DOCUMENTOS → CONCLUIDO`; terminais `ORIENTADO`, `BLOQUEADO`,
`ESCALADO_HUMANO`. **Só `graph/transitions.py` altera `claim_stage`.**

| Etapa | Especialista | `completed` leva a | `rejected` leva a |
|---|---|---|---|
| TRIAGEM | triage | AVISO | ORIENTADO |
| AVISO | claim_notice | DOCUMENTOS | ORIENTADO |
| DOCUMENTOS | documents | CONCLUIDO | — |

`failed` (erro técnico não recuperável ou tentativas esgotadas) leva a `ESCALADO_HUMANO`.
Veredito `block` leva a `BLOQUEADO`; `escalate`, a `ESCALADO_HUMANO`.

## 3. Componentes

**Guardrails** (`agents/guardrails/`): três estágios em paralelo (Segurança, Ética, Corporativo)
e um agregador. Camadas: regras determinísticas (regex de CPF, padrões de injection) e depois
classificador LLM com saída estruturada (Fase 6). Estágios ligados/desligados em
`configs/guardrails.yaml`. Precedência do agregador: `block > escalate > sanitize > allow`.

| Estágio | Entrada (usuário) | Saída (LLM) |
|---|---|---|
| Segurança | prompt injection, jailbreak, instruções em anexos | vazamento de PII/dados de terceiros, exposição de prompt |
| Ética | linguagem discriminatória, pedidos enviesados | vieses, tratamento diferenciado |
| Corporativo | sinais de fraude | promessas indevidas de cobertura/indenização |

**Orquestrador** (`agents/orchestrator/`): `routing_policy.py` com a tabela fixa
`claim_stage → especialista`; com `awaiting` setado, despacha direto ao especialista da etapa.
`intent.py` (flag `orchestrator.intent_llm_enabled`) só em desvios. Todo despacho emite evento
`route` com motivo.

**Transição** (`graph/transitions.py`): aplica o `StageResult`. Se `completed` e a nova etapa não é
terminal, incrementa `hops` e volta ao Orquestrador (limite `graph.max_hops_per_turn`, default 5;
estourou → `ESCALADO_HUMANO`). Se `needs_input` ou terminal, segue para `guardrails_out`.

**Especialistas** (subgrafos):

| Especialista | Subagentes | Tools |
|---|---|---|
| triage | customer_validation, parties, event_classification, decision | `get_customer_data`, `send_whatsapp` (outbox) |
| claim_notice | event_data_collection, coverage_assessment, registration | `open_claim`, `send_whatsapp` (outbox) |
| documents | checklist, intake_storage, validation, complement | `store_files`, `validate_document`, `send_whatsapp` (outbox) |

Os especialistas são máquinas de estado retomáveis: o progresso fica no sub-estado namespaced
(`triage`, `notice`, `documents`) e cada turno avança até precisar de input (`needs_input`).

## 4. Estado e contratos (`state/`)

```python
class GlobalState(BaseModel):
    conversation_id: str
    customer: CustomerRef | None
    claim_stage: ClaimStage = ClaimStage.TRIAGEM
    messages: list[ChatMessage]            # histórico (reducer: append)
    inbound: Inbound | None                # última entrada (texto + anexos)
    outbox: list[OutboxMessage]            # a enviar neste turno
    awaiting: Awaiting | None              # pergunta pendente: stage + field
    triage: TriageState; notice: NoticeState; documents: DocumentsState
    protocol: str | None
    guardrail_verdicts: list[GuardrailVerdict]  # reducer: append
    paused: bool; hops: int; terminal_reason: str | None
    last_result: StageResult | None        # saída do especialista para a transição

class StageResult(BaseModel):
    status: Literal["completed", "needs_input", "rejected", "failed"]
    payload: dict[str, Any]  # tipado por especialista (TriageOutcome, NoticeOutcome...)
    reason: str
    user_message: str | None  # vai para o outbox
```

A Triagem (e os demais especialistas) só conhece `StageResult` e o próprio sub-estado.

## 5. Tools (`tools/`)

Interface `Protocol` + schemas Pydantic + mock (SQLite/JSON) + `real/` (stub). Obtidas sempre do
`ToolRegistry`. Mocks aceitam `FaultInjector` (timeout, 5xx, not found). Chamadas passam por um
wrapper de resiliência (timeout, retry com backoff) que emite eventos `tool_call`.

| Tool | Entrada | Saída |
|---|---|---|
| `get_customer_data` | telefone ou CPF | cliente (CPF mascarado) + apólices; `NotFound`, `ToolTimeout` |
| `send_whatsapp` | `conversation_id`, texto, anexos | `message_id`, status |
| `open_claim` | `customer_id`, `policy_number`, dados do evento | `protocol`, `opened_at` |
| `store_files` | protocolo, arquivos, metadados | por arquivo: `file_id`, `uri`, `sha256` |
| `validate_document` | `file_id`, tipo, contexto | `valid`, `issues[]` |

## 6. Eventos e painel (`observability/`)

```python
class AgentEvent(BaseModel):
    id: str; ts: datetime; conversation_id: str
    agent: str; subagent: str | None
    event: str            # node_start, node_end, tool_call, guardrail_verdict, route, stage_transition, message_sent...
    details: str          # pt-BR, PII mascarada
    status: Literal["completed", "processing", "warning", "error"]
    tool: str | None; latency_ms: int | None; tokens: int | None
```

- **Fonte única**: `observability/adapter.py` consome `graph.astream(..., stream_mode=["updates", "custom"])`
  e normaliza em `AgentEvent`. Nós emitem eventos de domínio com `emit()` (wrapper de
  `get_stream_writer()`); o adaptador gera `node_start/node_end` a partir das atualizações.
- Eventos persistidos em SQLite (`EventStore`) e publicados num bus in-process para `WS /ws/events`.
- KPIs derivados do event store (`metrics.py`): Taxa de Sucesso (ADR-0006) e Interações Ativas
  (conversas não terminais com atividade dentro do timeout).

## 7. API (`api/`)

| Método | Rota | Uso |
|---|---|---|
| POST | `/conversations` | cria conversa (telefone sintético) |
| WS | `/ws/chat/{conversation_id}` | chat do simulador (entrada do usuário e entregas do `send_whatsapp`) |
| WS | `/ws/events` | stream de `AgentEvent` + snapshot de métricas |
| GET | `/events` | eventos persistidos (filtro por conversa) |
| GET | `/metrics` | KPIs |
| POST | `/control/pause` | pausa global ou por conversa |
| POST | `/conversations/{id}/attachments` | upload de anexo (retorna referência usada na próxima mensagem) |

## 8. Persistência

SQLite em `data/`: `checkpoints.db` (LangGraph), `claims.db` (mocks de domínio: clientes,
apólices, sinistros, arquivos), `events.db` (event store). Arquivos enviados em `data/storage/`.
