# ADR-0008 — Regras mínimas de elegibilidade e urgência da Triagem

- **Status:** proposto — **[PREENCHER/REVISAR pelo autor]**
- **Data:** 2026-10-12

## Decisão (em `configs/triage_rules.yaml`)
- **Elegível** se: cliente encontrado; apólice com status `ATIVA`; data do evento dentro da
  vigência; cobertura `COLISAO` presente; tipo do evento = colisão.
- **Não elegível → ORIENTADO** com mensagem por motivo: apólice vencida/cancelada, sem cobertura,
  tipo de evento fora de escopo, cliente não encontrado após N tentativas.
- **Urgência alta** se: há feridos, veículo em via pública impedindo trânsito, ou terceiros
  envolvidos com danos pessoais. Urgência alta não muda o fluxo na v1; só é registrada e sinalizada.
- Limite de tentativas por campo: 3; excedido → `ESCALADO_HUMANO`.

## Consequências
Regras explícitas e testáveis caso a caso; o LLM só extrai valores das respostas livres.
