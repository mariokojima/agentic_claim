# ADR-0016 — Aviso completo e intenções do Orquestrador

- **Status:** aceito
- **Data:** 2026-10-19

## Contexto
Fase 4 do briefing: coleta multi-turno com cobertura e protocolo; camada de intenção por LLM no
Orquestrador atrás de uma flag, "só em desvios". Aceite: protocolo gerado e flag liga/desliga sem
quebrar o fluxo.

## Decisão
- **Aviso:** quando, onde, o que aconteceu e **danos** (envolvidos vêm da Triagem). Regras primeiro;
  o LLM (`prompts/claim_notice/event_extraction.md`) completa só os campos que faltam, inclusive a
  partir do relato da Triagem. Avaliação preliminar de cobertura pelas coberturas da apólice
  (colisão; danos a terceiros quando há terceiros), sempre "sujeita à análise".
- **Intenções:** `falar_com_humano` (→ `ESCALADO_HUMANO`), `cancelar` (→ novo estado terminal
  `CANCELADO`), `status`, `duvida` e `fora_de_escopo` (resposta fixa + retomada da pergunta
  pendente, sem mudar a etapa), `corrigir_dado_anterior` (registrada e reconfirmada na etapa
  atual, ADR-0010). Mudanças de etapa continuam só em `graph/transitions.py`.
- **Regras sempre ativas** (`configs/orchestrator.yaml`, `orchestrator.intents_enabled`), sem custo.
  O **LLM** (`prompts/orchestrator/intent.md`) só classifica mensagens que as regras não resolvem,
  com flag `orchestrator.intent_llm_enabled` (**desligada por padrão**); respostas curtas, CPF e
  anexos nunca vão ao LLM; confiança < 0,6 → `continuar_etapa`.
- A pergunta pendente passa a ser guardada no estado (`pending_question`) para retomar após desvios.

## Consequências
Experimento "com/sem LLM no roteamento" é só a flag. Com a flag ligada, cada mensagem livre
(≥ 3 palavras) não resolvida pelas regras custa uma chamada de LLM. "Cancelar minha apólice" não
cancela o atendimento (é orientação de não-sinistro).
