"""LLM falso para testes (nenhuma chamada de rede). Respostas roteirizadas ou por função."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from claims_agents.core.llm.types import LLMError, LLMResponse, Message, Usage

Responder = Callable[[list[Message], str, type[BaseModel] | None], Any]


class FakeLLMClient:
    """`responses`: fila de respostas (str, dict, BaseModel ou Exception), consumida em ordem.
    `responder`: alternativa dinâmica, chamada com (messages, role, response_model)."""

    def __init__(
        self, responses: list[Any] | None = None, responder: Responder | None = None
    ) -> None:
        self.responses = list(responses or [])
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[Message],
        *,
        role: str = "default",
        response_model: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_version: str | None = None,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "role": role, "response_model": response_model})
        if self.responder is not None:
            value = self.responder(messages, role, response_model)
        elif self.responses:
            value = self.responses.pop(0)
        else:
            raise LLMError("FakeLLMClient sem respostas")
        if isinstance(value, Exception):
            raise value
        if isinstance(value, BaseModel):
            content = value.model_dump_json()
        elif isinstance(value, dict):
            content = json.dumps(value, ensure_ascii=False)
        else:
            content = str(value)
        parsed = response_model.model_validate_json(content) if response_model else None
        return LLMResponse(
            content=content, parsed=parsed, model="fake", usage=Usage(total_tokens=10)
        )
