# Briefing — PoC agêntica de abertura de sinistro (mestrado)

> **Como usar.** Salve este arquivo em `docs/00-briefing.md` e o mockup do frontend em `docs/ui/mockup.jpeg`.
> No Claude Code (VS Code), inicie em **plan mode** e envie: `Leia @docs/00-briefing.md e execute a seção 13.`
> Itens marcados **[CONFIRMAR]** são defaults assumidos, e itens **[PREENCHER]** dependem do autor. Se algum deles bloquear o trabalho, use o default, siga em frente e registre a decisão em ADR.

---

## 1. Contexto e objetivo

PoC de mestrado: sistema multiagente que cobre um recorte da pipeline de sinistro de seguros, da primeira mensagem do segurado até a **conclusão da etapa de abertura do sinistro**.

- **Stack:** Python, LangChain, LangGraph.
- **Frontend** (ver `docs/ui/mockup.jpeg`): o lado esquerdo simula uma conversa estilo WhatsApp. O lado direito é um painel para acompanhar interações e fluxo, com:
  - grafo de nós com status ao vivo;
  - log de eventos (colunas Hora, Agente, Evento, Detalhes, Status);
  - KPIs "Taxa de Sucesso" e "Interações Ativas";
  - botão "Pausar agente".
  - **Ignore os nomes dos agentes especialistas e das tools que aparecem no mockup**; são ilustrativos. Rótulos da UI em pt-BR.
- **Tudo é mockado:** sem WhatsApp real e sem sistemas reais da seguradora. Usar **somente dados sintéticos**.
- **Perguntas de pesquisa da dissertação:** **[PREENCHER]**. Enquanto isso, instrumentar o sistema para medir as métricas da seção 12.
- **Fora de escopo da v1:** integração real com WhatsApp, autenticação/multiusuário, deploy em produção, visão computacional, outros ramos de seguro.

## 2. Defaults assumidos

| Item | Default |
|---|---|
| Ramo e tipo de sinistro | Seguro de automóvel, sinistro de **colisão** (um único tipo na v1) **[CONFIRMAR]** |
| Idioma | Conversa em pt-BR. Código e identificadores em inglês. Documentação e prompts em pt-BR |
| LLM | Provedor configurável em `configs/models.yaml`. Padrão: Anthropic via `langchain-anthropic` (`ANTHROPIC_API_KEY` no `.env`). Um modelo único no início; separar por papel depois **[CONFIRMAR]** |
| Critério de saída dos Documentos | Todos os documentos obrigatórios validados leva a `CONCLUIDO`. Com pendências, a conversa fica em "aguardando complemento", com timeout configurável **[CONFIRMAR]** |
| Validação de documentos | Determinística: tipo/MIME, tamanho, hash duplicado, metadados e consistência com os dados do processo. Sem visão computacional |
| Taxa de sucesso | Fluxos concluídos sem erro técnico nem escalonamento ÷ fluxos iniciados (configurável) **[CONFIRMAR]** |
| Persistência | SQLite (checkpointer, event store, mocks de domínio) |
| Python e gestor de pacotes | Python 3.12, `uv` |
| Frontend | Vite + React + TypeScript, comunicação por WebSocket **[CONFIRMAR]** |
| Regras de elegibilidade e urgência da Triagem | Propor regras mínimas em `configs/triage_rules.yaml` e registrar em ADR, para revisão do autor **[PREENCHER]** |
| Checklist de documentos (colisão) | CNH do condutor, CRLV, fotos dos danos (mínimo 3), boletim de ocorrência quando aplicável. Em `configs/documents_checklist.yaml` **[CONFIRMAR]** |

## 3. Arquitetura

Um **grafo principal em LangGraph**. Cada especialista é um **subgrafo** com um nó coordenador e um ou mais **subagentes**.

```
Mensagem ─► Guardrails (entrada) ──bloqueado──────────────┐
                  │ ok                                    │
                  ▼                                       │
            Orquestrador ◄──── etapa concluída ───┐       │
            (rota por etapa;                      │       │
             LLM só em desvios)                   │       │
                  │                               │       │
        ┌─────────┼──────────┐                    │       │
        ▼         ▼          ▼                    │       │
     Triagem    Aviso    Documentos               │       │
        └─────────┼──────────┘                    │       │
                  ▼                               │       │
          Transição de etapa ─────────────────────┘       │
                  │ aguardando cliente / concluído        │
                  ▼                                       │
          Guardrails (saída) ◄────────────────────────────┘
                  │
                  ▼
           Envia WhatsApp
```

### 3.1 Estados do processo

`claim_stage`: `TRIAGEM → AVISO → DOCUMENTOS → CONCLUIDO`. Estados terminais alternativos: `ORIENTADO` (Triagem decidiu não abrir sinistro), `BLOQUEADO` (guardrail) e `ESCALADO_HUMANO`.

### 3.2 Componentes

- **Guardrails** (acionado na entrada do usuário e na resposta de LLM). Três estágios executados em paralelo (fan-out/fan-in): **Segurança**, **Ética** e **Corporativo**. Um agregador emite o veredito `allow | sanitize | block | escalate`, com justificativa.

  | Estágio | Entrada (usuário) | Saída (LLM) |
  |---|---|---|
  | Segurança | prompt injection, jailbreak, instruções embutidas em anexos | vazamento de PII e de dados de outros clientes, exposição de prompt |
  | Ética | linguagem discriminatória, pedidos enviesados | vieses ou tratamento diferenciado |
  | Corporativo | sinais de fraude | promessas indevidas de cobertura ou indenização |

  Implementação em camadas: regras determinísticas primeiro (regex de CPF, padrões de injection) e depois classificador LLM com saída estruturada. A checagem corporativa é reexecutada ao fim da Triagem, já com o contexto do segurado.
- **Orquestrador** (hub único de despacho). Usa uma tabela fixa `claim_stage → especialista`. Enquanto há pergunta pendente (`awaiting`), a resposta vai direto ao especialista da etapa. A classificação de intenção por LLM só entra em desvios, atrás da flag `orchestrator.intent_llm_enabled`. Intenções: `continuar_etapa`, `corrigir_dado_anterior`, `duvida`, `status`, `cancelar`, `falar_com_humano`, `fora_de_escopo`. Na v1, a correção de dado anterior é registrada e reconfirmada na etapa atual; regressão de etapa fica fora do escopo **[CONFIRMAR]**. Cada despacho emite um evento com o motivo.
- **Transição de etapa** (nó determinístico). Aplica o `StageResult` do especialista:
  - se a etapa concluiu, avança `claim_stage` e **volta ao Orquestrador** para despachar a próxima etapa na mesma rodada, com limite de saltos por rodada (default 5);
  - se está aguardando o cliente ou chegou a um estado terminal, segue para o Guardrails de saída.
  - **Toda mudança de `claim_stage` passa por este módulo (`graph/transitions.py`).**
- **Especialistas** (subgrafos) e **subagentes**: ver seção 5. Cada subagente recebe somente as tools de que precisa.

### 3.3 Estado e contratos

- **`GlobalState`** (Pydantic):
  - `conversation_id`, `customer`, `claim_stage`, `messages`, `inbound` (última entrada, com anexos);
  - `outbox` (mensagens a enviar), `awaiting` (pergunta pendente: etapa e campo);
  - sub-estados namespaced `triage`, `notice` e `documents`;
  - `protocol`, `guardrail_verdicts`, `paused`, `hops`, `terminal_reason`.
- **`StageResult`** (retorno de cada especialista): `status ∈ {completed, needs_input, rejected, failed}`, `payload` tipado, `reason`, `user_message` opcional (vai para o outbox).
- Cada especialista e subagente tem schema de estado próprio, com contrato de entrada e saída, para evitar um estado global inchado. A Triagem só conhece o contrato `StageResult` e não importa nada do Orquestrador, para poder ser testada isoladamente.
- **Multi-turno:** uma invocação do grafo por mensagem do usuário. Checkpointer SQLite com `thread_id = conversation_id`. Aguardar o cliente com `interrupt()`.
- **Outbox:** toda mensagem ao cliente vai para o `outbox`. Quando os especialistas "usam" a tool de WhatsApp, ela só enfileira. **O envio real ocorre num único nó final, depois do Guardrails de saída.**

### 3.4 Painel e eventos

- **`AgentEvent`:** `id, ts, conversation_id, agent, subagent?, event, details, status (completed | processing | warning | error), tool?, latency_ms, tokens?`.
- **Emitido em:**
  - entrada e saída de nós relevantes;
  - chamadas de tool;
  - vereditos de guardrail;
  - decisões de roteamento (com motivo);
  - transições de etapa.
- **Fonte única:** os eventos de streaming do LangGraph (`stream_mode`), normalizados por um adaptador. Não espalhar emissão ad hoc.
- **Armazenamento e transmissão:** persistir em SQLite e transmitir ao painel por WebSocket. Os KPIs são derivados do event store.
- **Pausar agente:** flag global e por conversa, verificada no início do grafo. Pausado, as mensagens do usuário são registradas e o sistema responde com uma mensagem fixa de handoff humano.
- **API proposta:**
  - `POST /conversations`;
  - `WS /ws/chat/{conversation_id}`;
  - `WS /ws/events`;
  - `GET /events`;
  - `GET /metrics`;
  - `POST /control/pause`;
  - `POST /conversations/{id}/attachments`.

## 4. Fluxo do processo

1. **Triagem:** valida os dados do segurado, classifica o evento e decide entre abrir o sinistro (`AVISO`) ou orientar de outra forma (`ORIENTADO`).
2. **Aviso de Sinistro:** coleta os dados do evento, avalia a cobertura preliminar, registra o aviso, gera o protocolo e informa os próximos passos.
3. **Documentos e Evidências:** solicita, recebe, armazena e valida documentos, fotos e vídeos. Em caso de inconsistência ou falta, pede complementação. Ao cumprir o critério de saída (seção 2), o estado vai a `CONCLUIDO` e é enviada a confirmação final: protocolo, documentos recebidos e próximos passos.

## 5. Especialistas e subagentes

| Especialista | Subagentes | Tools | Natureza |
|---|---|---|---|
| **Triagem** | validação do segurado · envolvidos · classificação do evento (tipo, elegibilidade, urgência) · decisão | `get_customer_data`, `send_whatsapp` | **Determinística**: o controle de fluxo é regra e dado. O LLM só extrai valores estruturados das respostas livres e redige mensagens |
| **Aviso de Sinistro** | coleta de dados do evento · avaliação de cobertura · registro e protocolo | `send_whatsapp`, `open_claim` | A coleta é um loop com `interrupt()`; o registro é determinístico |
| **Documentos e Evidências** | checklist por tipo de sinistro · recepção e armazenamento · validação · complementação | `send_whatsapp`, `store_files`, `validate_document` | Loop até o critério de saída; coordenador dinâmico apenas aqui |

**Triagem (detalhe).** Interage com o cliente pedindo os dados necessários para seguir ou não para o Aviso.
1. Identificar o segurado (telefone da conversa ou CPF informado).
2. Checklist de dados obrigatórios (config): se faltar algo, pedir via outbox, aguardar com `interrupt()` e extrair o valor da resposta.
3. Validações por regra: apólice, vigência, envolvidos.
4. Classificar o evento (tipo, elegibilidade, urgência) por extração LLM mais tabela de regras.
5. Decidir: `completed` leva a `AVISO`; `rejected` devolve a orientação e vai a `ORIENTADO`.

Salvaguardas: limite de tentativas por campo (default 3) com escalonamento a humano, e timeout de inatividade.

**Aviso (detalhe).** Coletar data, hora, local, descrição, envolvidos e danos, pedindo o que faltar. A avaliação preliminar de cobertura verifica se o evento está nas coberturas da apólice (mock). O registro chama `open_claim`, gera o protocolo e comunica os próximos passos, incluindo a lista de documentos que serão pedidos.

**Documentos (detalhe).** O checklist vem de `configs/documents_checklist.yaml`. Os arquivos recebidos são armazenados e vinculados ao protocolo, e depois validados. O que falhar gera uma solicitação específica de complementação.

## 6. Tools (contratos propostos)

Cada tool é uma **interface (`Protocol`) com schemas Pydantic**, uma implementação **mock** (SQLite/JSON) e espaço para uma implementação real futura. Os mocks devem permitir **injetar falhas** (timeout, erro 5xx, não encontrado) para testar resiliência.

| Tool | Entrada | Saída | Usada por |
|---|---|---|---|
| **Get Dados Cliente** `get_customer_data` | telefone ou CPF | cliente (nome, CPF mascarado, telefone) e apólices (número, vigência início/fim, status, coberturas); erros: `NotFound`, `Timeout` | Triagem |
| **Envia WhatsApp** `send_whatsapp` | `conversation_id`, texto, anexos opcionais | `message_id`, status. No simulador, entrega ao chat por WebSocket | todos, via outbox |
| **Abre Sinistro** `open_claim` | `customer_id`, `policy_number`, dados do evento | `protocol`, `opened_at` | Aviso |
| **Armazena Arquivos** `store_files` | protocolo, arquivos, metadados | por arquivo: `file_id`, `uri`, `sha256` | Documentos |
| **Valida Documentos** `validate_document` | `file_id`, tipo de documento, contexto do processo | `valid`, `issues[]` | Documentos |

## 7. Requisitos

**Funcionais**
- Guardrails nos 3 estágios, com veredito e justificativa persistidos e estágios ativáveis por configuração (necessário para experimentos).
- Orquestrador conforme 3.2, Triagem, Aviso e Documentos conforme a seção 5.
- Chat com texto e anexos, status de entrega e histórico por conversa.
- Painel conforme 3.4.

**Não funcionais**
- **Observabilidade:** trace de cada execução (nós, tools, tokens, latência).
- **Auditabilidade:** toda decisão (roteamento, guardrail, elegibilidade) com justificativa persistida.
- **Reprodutibilidade:** prompts versionados em `prompts/`, temperatura baixa, versões fixadas em lockfile, modelos e regras em `configs/`.
- **Testabilidade:** o grafo roda com LLM falso ou gravado.
- **Privacidade:** apenas dados sintéticos, com PII mascarada em logs.
- **Resiliência:** timeouts, retries e falha graciosa nas tools.

## 8. Stack

Python 3.12 · `uv` · `langgraph` · `langchain-core` · `langchain-anthropic` (provedor padrão) · `langgraph-checkpoint-sqlite` · Pydantic v2 + `pydantic-settings` · FastAPI + Uvicorn + WebSocket · SQLite · `pytest` + `pytest-asyncio` + `httpx` · `ruff` · `mypy` · Frontend Vite + React + TypeScript (biblioteca de grafo de nós, por exemplo React Flow **[CONFIRMAR]**) · LangSmith opcional via variáveis de ambiente.

> Use as versões estáveis atuais e **confirme as APIs na documentação oficial** de LangChain e LangGraph antes de codar, porque as APIs de agentes prontos mudaram entre versões. Fixe no lockfile.

## 9. Estrutura do repositório

```
claims-agents/
├── CLAUDE.md                       # convenções e regras invariantes (≤200 linhas)
├── .claude/skills/                 # skills de desenvolvimento (seção 13)
├── pyproject.toml · .env.example · Makefile
├── docs/
│   ├── 00-briefing.md · requirements.md · architecture.md
│   ├── ui/mockup.png
│   └── adr/
├── configs/                        # models.yaml, guardrails.yaml, triage_rules.yaml,
│                                   # documents_checklist.yaml, settings.yaml
├── prompts/                        # versionados; espelham agents/
├── data/
│   ├── fixtures/                   # clientes, apólices (sintéticos)
│   └── evaluation/                 # cenários e conversas de teste
├── src/claims_agents/
│   ├── core/                       # settings, logging, fábrica de LLM, erros
│   ├── domain/                     # Customer, Policy, Claim, Document, enums
│   ├── state/                      # global_state.py, contracts.py (StageResult)
│   ├── graph/                      # build_graph.py, transitions.py, checkpointer.py
│   ├── agents/
│   │   ├── guardrails/             # security, ethics, corporate, aggregator
│   │   ├── orchestrator/           # routing_policy.py, intent.py (flag)
│   │   ├── triage/                 # graph.py, state.py, coordinator.py, subagents/
│   │   ├── claim_notice/           # idem
│   │   └── documents/              # idem
│   ├── tools/                      # interfaces, schemas, mocks/, real/
│   ├── observability/              # AgentEvent, adaptador de streaming, event store
│   └── api/                        # FastAPI: chat, WebSocket, painel, controle
├── frontend/                       # chat (esquerda) + painel (direita)
├── tests/                          # unit/ integration/ e2e/ evals/
└── scripts/                        # seed de dados, runner de cenários
```

Cada subagente tem `graph.py` (ou `nodes.py`) e `schemas.py`.

## 10. Qualidade e testes

- `make check` = `ruff` + `mypy` + `pytest -q`. Deve passar ao fim de cada fase.
- Testes unitários e de integração usam **LLM falso ou respostas gravadas**; sem chamadas reais.
- O fluxo ponta a ponta é testado com conversas roteirizadas, cobrindo `CONCLUIDO`, `ORIENTADO`, `BLOQUEADO` e `ESCALADO_HUMANO`.
- Cada regra de guardrail e cada regra da Triagem tem casos de teste.
- Tipagem estrita nos módulos de estado, contratos e tools.

## 11. Fases e critérios de aceite

| Fase | Entrega | Aceite |
|---|---|---|
| **0 – Fundação** | repo, `uv`, settings, logging, modelos de domínio, fixtures sintéticos (≥10 clientes e apólices: vigente, vencida, sem cobertura etc.), interfaces e mocks das 5 tools, ADRs | `make check` passa; testes das tools e dos mocks, incluindo injeção de falhas |
| **1 – Esqueleto ponta a ponta** | `GlobalState`, `StageResult`, grafo com **nós stub sem LLM** (guardrails, Orquestrador por tabela, 3 especialistas, transição, outbox/envio), checkpointer, API com WebSocket, `AgentEvent` + event store, frontend (chat + painel conforme mockup) | uma conversa simulada percorre `TRIAGEM → AVISO → DOCUMENTOS → CONCLUIDO` com stubs; o painel mostra eventos em tempo real; teste e2e automatizado |
| **2 – Guardrails (base)** | nós de entrada e saída com regras determinísticas mínimas (PII, padrões de injection) | veredito registrado como evento; casos de teste |
| **3 – Triagem** | fluxo completo da seção 5, regras em config | caminhos `completed` e `rejected`, limite de tentativas e timeout testados |
| **4 – Aviso** | coleta multi-turno, cobertura, protocolo; camada de intenção LLM do Orquestrador atrás da flag | protocolo gerado; a flag liga e desliga sem quebrar o fluxo |
| **5 – Documentos** | upload no chat, armazenamento, validação, complementação, estado `CONCLUIDO` | critério de saída e mensagem final testados |
| **6 – Guardrails completos e avaliação** | classificadores LLM, fraude, runner de cenários, métricas, relatório | seção 12 executável com um comando |

## 12. Avaliação (dissertação)

- **Instrumentar desde a fase 1:** tokens, latência, custo estimado, nº de turnos, vereditos de guardrail e resultado de cada fluxo.
- **Cenários sintéticos:** caminho feliz, dados faltantes, apólice vencida, evento não coberto, fraude, prompt injection direta e indireta (via documento), fora de escopo, pedido de humano.
- **Métricas:** acerto de roteamento, taxa de conclusão do fluxo, correção das chamadas de tools, bloqueio de ataques versus falsos positivos, nº de turnos, latência, tokens e custo.
- **Experimentos comparativos (via configuração):** com e sem guardrails, com e sem LLM no roteamento, modelos diferentes.
- **Definição de "taxa de sucesso":** seção 2.
- **Conjuntos de avaliação:** um conjunto *smoke* (~10 cenários) para uso diário e a bateria completa só nos experimentos.

## 13. Instruções de trabalho para o Claude Code

**Comece em plan mode.** Proponha o plano das Fases 0 e 1 e aguarde aprovação. Depois:

1. **Gerar a base de contexto** a partir deste briefing, de forma enxuta:
   - `CLAUDE.md` (≤200 linhas): comandos, convenções e regras invariantes;
   - `docs/requirements.md` e `docs/architecture.md`;
   - ADRs para as decisões e os defaults da seção 2;
   - skills em `.claude/skills/`: `add-specialist-agent`, `add-subagent`, `add-tool`, `add-guardrail-rule`, `run-scenarios`.
2. **Implementar as Fases 0 e 1.** Parar ao fim de cada fase, rodar `make check` e resumir o resultado. Não avançar para a fase seguinte sem aprovação.
3. Commits pequenos, por tarefa.

**Regras invariantes**
- Nunca usar dados reais.
- Toda mensagem ao cliente passa pelo outbox e pelo Guardrails de saída antes do envio.
- Tools só via interface; nenhuma chamada direta a mocks nos agentes.
- Mudanças de `claim_stage` somente em `graph/transitions.py`.
- Prompts em `prompts/`, versionados; modelos e regras em `configs/`.
- Segredos só em `.env` (nunca versionado).
- Sem LLM real em testes unitários.

**Economia de tokens**
- Uma sessão por fase ou por subagente.
- Depois de gerar `CLAUDE.md` e `docs/`, **não reler este briefing**; usar esses arquivos.
- Ler apenas os arquivos necessários e editar com `Edit`, sem reescrever arquivos inteiros.
- Delegar a subagentes (modelo menor) a execução de testes, lint e leitura de logs, devolvendo só o resumo.
- Rodar testes com saída resumida (`pytest -q`).
- Não adicionar dependências sem justificar.
- Respostas curtas. Perguntar só o que for bloqueante, agrupando as dúvidas.

**Perguntas em aberto.** As marcadas **[CONFIRMAR]** e **[PREENCHER]** da seção 2. Use os defaults, registre em ADR e sinalize ao autor na revisão da fase.
