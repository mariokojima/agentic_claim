"""Prompts versionados em `prompts/` (markdown com cabeçalho `version`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from claims_agents.core.errors import ConfigError
from claims_agents.core.settings import PROMPTS_DIR


class Prompt(BaseModel):
    name: str
    version: str
    text: str

    @property
    def ref(self) -> str:
        return f"{self.name}@v{self.version}"

    def render(self, **kwargs: str) -> str:
        return self.text.format(**kwargs) if kwargs else self.text


@lru_cache
def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> Prompt:
    """`load_prompt("triage/event_classification")` → prompts/triage/event_classification.md"""
    path = prompts_dir / f"{name}.md"
    if not path.exists():
        raise ConfigError(f"Prompt não encontrado: {path}")
    raw = path.read_text(encoding="utf-8")
    version = "0"
    if raw.startswith("---"):
        header, _, body = raw[3:].partition("---")
        for line in header.splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "version":
                version = value.strip()
        raw = body
    return Prompt(name=name, version=version, text=raw.strip())
