---
name: add-tool
description: Adiciona uma nova tool com interface Protocol, schemas Pydantic, mock com injeção de falhas, registro no ToolRegistry e testes. Use quando um agente precisar de uma nova integração (mockada).
---

# Adicionar tool

## Passos
1. **Schemas** em `tools/schemas.py`: `<Tool>Request` e `<Tool>Response` (Pydantic, `extra="forbid"`).
2. **Interface** em `tools/interfaces.py`: `class <Tool>(Protocol): async def __call__(self, req) -> resp`.
   Documente os erros possíveis (`NotFound`, `ToolTimeout`, `UpstreamError` de `core/errors.py`).
3. **Mock** em `tools/mocks/<tool>.py`: implementação sobre SQLite/JSON com dados sintéticos; aceita
   `FaultInjector` (`tools/mocks/faults.py`) e chama `await self.faults.maybe_fail("<tool>")` no início.
4. **Real** em `tools/real/<tool>.py`: stub que levanta `NotImplementedError`.
5. **Registro** em `tools/registry.py`: campo tipado pela interface; seleção mock/real por
   `configs/settings.yaml` (`tools.<tool>.impl`). Chamadas passam pelo wrapper `resilient()`
   (timeout, retry, evento `tool_call`).
6. Atualize a tabela de tools em `docs/architecture.md` §5.

## Regras
- Agentes nunca importam `tools/mocks/` ou `tools/real/`; só a interface via registry.
- Saída com PII já mascarada quando destinada ao LLM (ex.: CPF `***.***.***-12`).

## Testes exigidos (`tests/unit/tools/test_<tool>.py`)
- Caminho feliz contra fixtures; validação de schema (entrada inválida).
- Cada falha injetada: timeout, 5xx (`UpstreamError`), não encontrado; retry recupera falha transitória.
