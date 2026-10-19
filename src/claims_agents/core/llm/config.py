"""Configuração do LLM (`configs/models.yaml`) e leitura de segredos do `.env`."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, Field

from claims_agents.core.errors import ConfigError
from claims_agents.core.settings import PROJECT_ROOT, load_config


class ProviderConfig(BaseModel):
    base_url: str | None = None
    api_key_env: str | None = None


class ModelConfig(BaseModel):
    model: str
    fallback_models: list[str] = Field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: float = 30.0
    max_retries: int = 2
    backoff_base_s: float = 0.5


class LLMConfig(BaseModel):
    provider: str
    providers: dict[str, ProviderConfig]
    default: ModelConfig
    roles: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @property
    def provider_config(self) -> ProviderConfig:
        if self.provider not in self.providers:
            raise ConfigError(f"Provedor de LLM não configurado: {self.provider}")
        return self.providers[self.provider]

    def for_role(self, role: str) -> ModelConfig:
        override = self.roles.get(role) or {}
        return ModelConfig.model_validate(self.default.model_dump() | override)


def load_llm_config(data: dict[str, Any] | None = None) -> LLMConfig:
    return LLMConfig.model_validate(data if data is not None else load_config("models"))


@lru_cache
def _dotenv() -> dict[str, str | None]:
    path = PROJECT_ROOT / ".env"
    return dotenv_values(path) if path.exists() else {}


def get_secret(name: str | None) -> str | None:
    """Lê um segredo do ambiente ou do `.env`. Nunca registrar o valor em logs/eventos."""
    if not name:
        return None
    return os.environ.get(name) or _dotenv().get(name) or None
