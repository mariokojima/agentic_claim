# ADR-0001 — Escopo: seguro de automóvel, sinistro de colisão

- **Status:** proposto — **[CONFIRMAR com o autor]**
- **Data:** 2026-10-12

## Contexto
O briefing deixa ramo e tipo de sinistro em aberto, com default auto/colisão.

## Decisão
A v1 cobre apenas **automóvel / colisão**. Tipo de sinistro é um enum (`ClaimType.COLISAO`) e
checklists/regras são indexados por tipo, para permitir novos tipos sem refatoração.

## Consequências
Triagem orienta (`ORIENTADO`) eventos de outros tipos. Cenários de avaliação usam só colisão.
