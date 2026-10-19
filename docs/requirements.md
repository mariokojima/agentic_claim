# Requisitos

## 1. Objetivo e escopo

Sistema multiagente que cobre um recorte da pipeline de sinistro de seguros: da primeira mensagem
do segurado (WhatsApp simulado) até a **conclusão da etapa de abertura do sinistro**.

- Ramo: **automóvel**, tipo **colisão** (único na v1, ADR-0001).
- Tudo mockado; **somente dados sintéticos**.
- Perguntas de pesquisa da dissertação: **[PREENCHER pelo autor]**. Enquanto isso, o sistema é
  instrumentado para as métricas da §5.

**Fora de escopo (v1):** WhatsApp real, autenticação/multiusuário, deploy em produção, visão
computacional, outros ramos de seguro, regressão de etapa (ADR-0010).

## 2. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Guardrails de entrada (mensagem do usuário) e de saída (resposta gerada) com três estágios em paralelo: Segurança, Ética, Corporativo. Agregador emite `allow \| sanitize \| block \| escalate` com justificativa. |
| RF-02 | Cada estágio de guardrail é ativável/desativável por configuração (`configs/guardrails.yaml`). |
| RF-03 | Veredito e justificativa de guardrail persistidos e emitidos como evento. |
| RF-04 | Checagem corporativa reexecutada ao fim da Triagem, com o contexto do segurado. |
| RF-05 | Orquestrador despacha por tabela fixa `claim_stage → especialista`; com pergunta pendente (`awaiting`) envia direto ao especialista da etapa. |
| RF-06 | Classificação de intenção por LLM apenas em desvios, atrás da flag `orchestrator.intent_llm_enabled`. Intenções: `continuar_etapa`, `corrigir_dado_anterior`, `duvida`, `status`, `cancelar`, `falar_com_humano`, `fora_de_escopo`. |
| RF-07 | Toda decisão de roteamento emite evento com motivo. |
| RF-08 | Transição de etapa determinística (`graph/transitions.py`): avança etapa e volta ao Orquestrador na mesma rodada (limite de saltos por rodada, default 5) ou segue para o Guardrails de saída. |
| RF-09 | **Triagem**: identifica o segurado (telefone ou CPF), coleta dados obrigatórios (config), valida apólice/vigência/envolvidos, classifica o evento (tipo, elegibilidade, urgência) e decide `AVISO` ou `ORIENTADO`. Limite de tentativas por campo (default 3) com escalonamento; timeout de inatividade. |
| RF-10 | **Aviso**: coleta data, hora, local, descrição, envolvidos e danos (multi-turno); avaliação preliminar de cobertura; `open_claim` gera protocolo; informa próximos passos e documentos que serão pedidos. |
| RF-11 | **Documentos**: checklist por tipo de sinistro (config); recebe, armazena (vinculado ao protocolo) e valida documentos; pede complementação específica; ao cumprir o critério de saída (ADR-0004) vai a `CONCLUIDO` e envia confirmação final. |
| RF-12 | Chat com texto e anexos, status de entrega e histórico por conversa. |
| RF-13 | Painel: grafo de nós com status ao vivo; log de eventos (Hora, Agente, Evento, Detalhes, Status); KPIs "Taxa de Sucesso" e "Interações Ativas"; botão "Pausar agente". |
| RF-14 | Pausa global e por conversa: mensagens do usuário são registradas e o sistema responde com mensagem fixa de handoff humano. |
| RF-15 | Tools com interface (`Protocol`), schemas Pydantic, implementação mock com injeção de falhas (timeout, 5xx, não encontrado) e espaço para implementação real. |

## 3. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | **Observabilidade**: trace de cada execução (nós, tools, tokens, latência). LangSmith opcional via env. |
| RNF-02 | **Auditabilidade**: toda decisão (roteamento, guardrail, elegibilidade) com justificativa persistida. |
| RNF-03 | **Reprodutibilidade**: prompts em `prompts/`, temperatura baixa, versões fixadas em `uv.lock`, modelos e regras em `configs/`. |
| RNF-04 | **Testabilidade**: o grafo roda com LLM falso ou gravado; sem LLM real em testes unitários/integração. |
| RNF-05 | **Privacidade**: apenas dados sintéticos; PII mascarada em logs e eventos. |
| RNF-06 | **Resiliência**: timeouts, retries com backoff e falha graciosa nas tools. |
| RNF-07 | **Qualidade**: `make check` (ruff + mypy + pytest) verde ao fim de cada fase; tipagem estrita em estado, contratos e tools. |

## 4. Estados do processo

`TRIAGEM → AVISO → DOCUMENTOS → CONCLUIDO`. Terminais alternativos: `ORIENTADO`, `BLOQUEADO`,
`ESCALADO_HUMANO` e `CANCELADO` (cliente desistiu; ADR-0016).

## 5. Avaliação (dissertação)

- Instrumentado desde a Fase 1: tokens, latência, custo estimado, nº de turnos, vereditos de
  guardrail e resultado de cada fluxo.
- **Cenários sintéticos:** caminho feliz, dados faltantes, apólice vencida, evento não coberto,
  fraude, prompt injection direta e indireta (via documento), fora de escopo, pedido de humano.
- **Métricas:** acerto de roteamento, taxa de conclusão, correção das chamadas de tools, bloqueio
  de ataques vs. falsos positivos, nº de turnos, latência, tokens e custo.
- **Experimentos (via config):** com/sem guardrails, com/sem LLM no roteamento, modelos diferentes.
- **Taxa de sucesso:** ver ADR-0006.
- **Conjuntos:** *smoke* (~10 cenários) diário; bateria completa só nos experimentos.

## 6. Fases e critérios de aceite

| Fase | Entrega | Aceite |
|---|---|---|
| 0 – Fundação | repo, `uv`, settings, logging, domínio, fixtures (≥10 clientes/apólices), interfaces e mocks das 5 tools, ADRs | `make check` passa; testes de tools/mocks incluindo injeção de falhas |
| 1 – Esqueleto ponta a ponta | `GlobalState`, `StageResult`, grafo com nós stub sem LLM, checkpointer, API + WebSocket, `AgentEvent` + event store, frontend | conversa simulada percorre `TRIAGEM → AVISO → DOCUMENTOS → CONCLUIDO`; painel em tempo real; teste e2e |
| 2 – Guardrails (base) | regras determinísticas mínimas (PII, injection) | veredito como evento; casos de teste |
| 3 – Triagem | fluxo completo, regras em config | `completed`, `rejected`, limite de tentativas e timeout testados |
| 4 – Aviso | coleta multi-turno, cobertura, protocolo; intenção LLM atrás da flag | protocolo gerado; flag liga/desliga sem quebrar |
| 5 – Documentos | upload, armazenamento, validação, complementação, `CONCLUIDO` | critério de saída e mensagem final testados |
| 6 – Guardrails completos e avaliação | classificadores LLM, fraude, runner, métricas, relatório | §5 executável com um comando |
