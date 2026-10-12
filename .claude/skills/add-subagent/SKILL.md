---
name: add-subagent
description: Adiciona um subagente (nó ou mini-subgrafo) dentro de um especialista existente, com schema de entrada/saída, tools mínimas e testes. Use ao incluir um passo novo em Triagem, Aviso ou Documentos.
---

# Adicionar subagente

## Passos
1. Crie `agents/<especialista>/subagents/<nome>/` com:
   - `schemas.py`: `<Nome>Input` e `<Nome>Output` (Pydantic, estritos).
   - `nodes.py`: função(ões) puras `run(inp: <Nome>Input, deps) -> <Nome>Output`; o wrapper de nó
     lê/escreve o sub-estado do especialista.
2. Receba **apenas** as tools necessárias (injete as interfaces específicas, não o registry inteiro).
3. Se usar LLM: só para **extrair valores estruturados** ou **redigir mensagens**; use
   `core.llm.get_chat_model(role)` com `with_structured_output(<Schema>)`; prompt em
   `prompts/<especialista>/<nome>.md`. Controle de fluxo é sempre regra/dado.
4. Registre o subagente no `coordinator.py` do especialista (condição de entrada e de saída).
5. Emita `emit(event="subagent_start"/"subagent_end", subagent="<nome>", ...)` e eventos `tool_call`
   (o wrapper de resiliência já emite).

## Regras
- Limite de tentativas por campo (config) e escalonamento via `StageResult(status="failed")`.
- Mensagens ao cliente vão para `outbox`; PII nunca em `details` de evento sem máscara.

## Testes exigidos
- Unitário de `run()` com entradas válidas, faltantes e inválidas; LLM falso (`FakeListChatModel`).
- Teste do coordenador escolhendo o subagente no momento certo.
