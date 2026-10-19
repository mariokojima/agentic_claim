# ADR-0015 — Gateway de LLM no formato OpenAI, com Gemini como provedor

- **Status:** aceito (pedido do autor em 2026-10-19; substitui a ADR-0002)
- **Data:** 2026-10-19

## Contexto
O autor pediu que toda chamada de LLM no código siga o padrão OpenAI (compatível) e que o
Gemini, cujas credenciais estão no `.env`, seja a fonte de LLM. A ADR-0002 previa Anthropic via
`langchain-anthropic`.

## Decisão
- Interface única `LLMClient.chat(messages, response_model=...)` com mensagens no formato
  `{"role", "content"}` e saída estruturada por `response_format` (JSON Schema).
- Implementação `OpenAICompatibleClient` sobre o SDK oficial `openai`, apontando para o endpoint
  compatível do Gemini (`.../v1beta/openai/`). Trocar de provedor (OpenAI, Anthropic, outros
  compatíveis) é só configuração em `configs/models.yaml`.
- Resiliência: erros transitórios (429/5xx/timeout) vão para os `fallback_models`
  (`gemini-flash-latest` → `gemini-flash-lite-latest`); JSON inválido recebe uma correção;
  falha definitiva levanta `LLMError` e os agentes **degradam para regras**.
- Observabilidade: evento `llm_call` com modelo, tokens, latência, tentativas, fallback e versão
  do prompt (`prompts/`, versionados).
- Segredos lidos do ambiente/`.env` (`api_key_env`), nunca registrados. Sem chave, ou com
  `provider: none`, o sistema funciona só com regras.
- O LLM é injetado explicitamente (`GraphDeps.llm`); testes usam `FakeLLMClient`.
- Uso na Fase 3: fallback da classificação do ocorrido e dos envolvidos (regras primeiro, LLM
  só quando elas não resolvem) e redação opcional de mensagens (`llm.rewrite_messages`).

## Consequências
`langchain-anthropic` removido; LangChain/LangGraph seguem para o grafo. Abordagem "regras
primeiro" reduz custo/latência e permite comparar regras × LLM na avaliação. Em 2026-10-19 o
`gemini-flash-latest` respondia 503 (alta demanda) e o fallback assumiu as chamadas.
