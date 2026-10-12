# ADR-0004 — Critério de saída da etapa de Documentos

- **Status:** proposto — **[CONFIRMAR]**
- **Data:** 2026-10-12

## Decisão
`CONCLUIDO` quando **todos os documentos obrigatórios** do checklist estão validados. Com
pendências, a conversa fica em `DOCUMENTOS` com `awaiting` (status "aguardando complemento").
Timeout de inatividade configurável (`documents.complement_timeout_hours`, default 72h); ao expirar,
a conversa vai a `ESCALADO_HUMANO` com `terminal_reason="timeout_documentos"`.

## Consequências
Documentos opcionais (ex.: BO quando não aplicável) não bloqueiam a conclusão.
