"""Injeção de falhas nos mocks: timeout, erro 5xx e não encontrado."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Literal

from claims_agents.core.errors import NotFound, UpstreamError

FaultKind = Literal["timeout", "upstream", "not_found"]


@dataclass
class FaultRule:
    kind: FaultKind
    probability: float = 1.0
    times: int | None = None  # None = sempre; N = só nas próximas N chamadas elegíveis
    delay_s: float = 30.0  # usado por "timeout" (deve exceder o timeout do wrapper)
    status_code: int = 503


@dataclass
class FaultInjector:
    rules: dict[str, list[FaultRule]] = field(default_factory=dict)
    seed: int | None = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def add(self, tool: str, rule: FaultRule) -> FaultInjector:
        self.rules.setdefault(tool, []).append(rule)
        return self

    def clear(self, tool: str | None = None) -> None:
        if tool is None:
            self.rules.clear()
        else:
            self.rules.pop(tool, None)

    async def maybe_fail(self, tool: str) -> None:
        for rule in self.rules.get(tool, []):
            if rule.times is not None and rule.times <= 0:
                continue
            if self._rng.random() >= rule.probability:
                continue
            if rule.times is not None:
                rule.times -= 1
            if rule.kind == "timeout":
                await asyncio.sleep(rule.delay_s)
            elif rule.kind == "upstream":
                raise UpstreamError(
                    f"{tool}: erro {rule.status_code} simulado",
                    tool=tool,
                    status_code=rule.status_code,
                )
            elif rule.kind == "not_found":
                raise NotFound(f"{tool}: recurso não encontrado (simulado)", tool=tool)
