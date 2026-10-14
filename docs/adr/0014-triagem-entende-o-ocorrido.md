# ADR-0014 — Triagem entende o ocorrido antes de abrir o aviso

- **Status:** aceito (pedido do autor em 2026-10-13)
- **Data:** 2026-10-13

## Contexto
Na versão anterior, após identificar o segurado a Triagem já anunciava o aviso de sinistro
("Vamos registrar o aviso…") sem saber se o relato era de fato um sinistro coberto por este canal.

## Decisão
- Novo subagente **Classificação do ocorrido** entre a validação do segurado e a decisão:
  pergunta "o que aconteceu?" (ou aproveita o relato espontâneo da 1ª mensagem) e classifica em
  COLISAO, ROUBO_FURTO, INCENDIO, FENOMENO_NATURAL, VIDROS, ASSISTENCIA, NAO_SINISTRO ou "não
  entendido" (repergunta; após o limite de tentativas, escala a humano). Feridos → urgência alta e
  orientação para o SAMU.
- Regras (regex) e prioridade entre categorias em `configs/triage_rules.yaml`; o LLM (Fase 3)
  mantém as mesmas categorias.
- **Decisão:** só COLISAO segue para a checagem da apólice; demais tipos → `ORIENTADO` com
  mensagem específica (`rejection_messages.event_type_<TIPO>`). Cliente sem apólice não é
  perguntado sobre o ocorrido.
- Só depois da decisão favorável o assistente fala em registrar o aviso. O Aviso reaproveita o
  relato da Triagem e pergunta apenas o que faltar (quando/onde).

## Consequências
Fluxo mais fiel ao atendimento real e mensurável por cenário (acerto da classificação).
Envolvidos/terceiros ainda não são extraídos (Fase 3/4); por isso o BO segue não exigido.
