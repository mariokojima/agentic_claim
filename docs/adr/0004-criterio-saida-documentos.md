# ADR-0004 — Critério de saída da etapa de Documentos

- **Status:** proposto — **[CONFIRMAR]**
- **Data:** 2026-10-12

## Decisão
`CONCLUIDO` quando **todos os documentos obrigatórios** do checklist estão validados. Com
pendências, a conversa fica em `DOCUMENTOS` com `awaiting` (status "aguardando complemento").
Sem envio de documentos, um **lembrete** é enviado após `documents.reminder_minutes` (default 24h)
e, após `documents.complement_timeout_minutes` (default 72h) desde a última mensagem do cliente,
a conversa vai a `ESCALADO_HUMANO` com `terminal_reason="timeout_documentos"`. Um verificador
periódico na API (`documents.sweep_interval_seconds`) dispara esses eventos mesmo sem mensagem
nova; uma mensagem que chegue após o prazo também é tratada como timeout. (Fase 5)

## Consequências
Documentos opcionais (ex.: BO quando não aplicável) não bloqueiam a conclusão.
