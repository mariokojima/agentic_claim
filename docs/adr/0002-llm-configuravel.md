# ADR-0002 — Provedor de LLM configurável, modelo único

- **Status:** substituída pela ADR-0015 (gateway no formato OpenAI, Gemini)
- **Data:** 2026-10-12

## Contexto
Experimentos precisam comparar modelos; testes não podem chamar LLM real.

## Decisão
`configs/models.yaml` define provedor, modelo e temperatura por papel (inicialmente todos os papéis
apontam para o mesmo modelo). Padrão: Anthropic via `langchain-anthropic`, `ANTHROPIC_API_KEY` no
`.env`. `core/llm.py` é a única fábrica; o provedor `fake` (`FakeListChatModel`) é usado em testes.

## Consequências
Trocar modelo é só configuração. Separar por papel (guardrail, extração, redação) é editar o YAML.
