# ADR-0003 — Stack técnica

- **Status:** aceito (frontend e React Flow **[CONFIRMAR]**)
- **Data:** 2026-10-12

## Decisão
Python 3.12 + `uv`; LangGraph + langchain-core + langchain-anthropic; `langgraph-checkpoint-sqlite`;
Pydantic v2 + pydantic-settings; FastAPI + Uvicorn + WebSocket; SQLite; pytest + pytest-asyncio +
httpx; ruff; mypy. Frontend: Vite + React + TypeScript, `@xyflow/react` (React Flow) para o grafo,
comunicação por WebSocket. Versões fixadas em `uv.lock` e `package-lock.json`.

## Consequências
Stack mínima, local, sem serviços externos além do provedor de LLM.
