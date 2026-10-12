# ADR-0013 — Bloqueio de entrada: recusar a mensagem, com limite por conversa

- **Status:** aceito (escolhido pelo autor em 2026-10-12; altera a regra de `block` da ADR-0005/arquitetura)
- **Data:** 2026-10-12

## Contexto
Na Fase 1, um veredito `block` do guardrail de entrada levava a conversa direto a `BLOQUEADO`
(terminal). Para demonstrar e avaliar os guardrails, encerrar na primeira tentativa obriga a abrir
uma nova conversa a cada teste e pune falsos positivos de forma desproporcional.

## Decisão
- `block` na entrada **recusa só a mensagem**: nenhum especialista é acionado, a etapa não muda e
  a pergunta pendente é repetida ("Desculpe, não posso atender a esse pedido… Vamos continuar…").
- O contador `GlobalState.input_blocks` soma as recusas da conversa; ao atingir
  `input_block_limit` (default 3, em `configs/guardrails.yaml`), a conversa vai a `BLOQUEADO`.
- `escalate` na entrada (ex.: sinais de fraude) continua levando a `ESCALADO_HUMANO`.
- Na saída: `sanitize` substitui o texto (ex.: CPF mascarado); `block`/`escalate` trocam a mensagem
  por uma resposta segura fixa.
- Regras determinísticas (regex) por estágio e direção em `configs/guardrails.yaml`, cada uma com
  `enabled`, `action`, `reason` e `patterns`. Nome e metadados dos anexos também são verificados na
  entrada (instruções embutidas em anexos).

## Consequências
Cada recusa gera os eventos `guardrail_verdict` (warning) e `input_refused`. Para o experimento
"com/sem guardrails", basta `enabled: false` no topo do YAML. Taxa de falsos positivos passa a ser
mensurável por cenário (Fase 6).
