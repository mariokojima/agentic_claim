# ADR-0010 — Correção de dado anterior sem regressão de etapa

- **Status:** proposto — **[CONFIRMAR]**
- **Data:** 2026-10-12

## Decisão
A intenção `corrigir_dado_anterior` é registrada (evento + campo no sub-estado da etapa atual) e o
dado é reconfirmado na etapa atual. `claim_stage` nunca regride na v1.
