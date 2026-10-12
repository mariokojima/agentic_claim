"""Wrapper de resiliência das tools: timeout, retry com backoff e notificação de chamadas."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from claims_agents.core.errors import ToolError, ToolTimeout


@dataclass(frozen=True)
class ToolCallRecord:
    tool: str
    status: Literal["completed", "warning", "error"]
    latency_ms: int
    attempts: int
    error: str | None = None


ToolObserver = Callable[[ToolCallRecord], None]


@dataclass(frozen=True)
class RetryPolicy:
    timeout_s: float = 5.0
    max_retries: int = 2
    backoff_base_s: float = 0.2


class ResilientTool[Req: BaseModel, Resp: BaseModel]:
    """Aplica timeout e retry a uma tool, preservando a interface `__call__(req) -> resp`."""

    def __init__(
        self,
        name: str,
        inner: Callable[[Req], Awaitable[Resp]],
        policy: RetryPolicy,
        observer: ToolObserver | None = None,
    ) -> None:
        self.name = name
        self.inner = inner
        self.policy = policy
        self.observer = observer

    async def __call__(self, req: Req) -> Resp:
        start = time.perf_counter()
        attempt = 0
        while True:
            attempt += 1
            try:
                result = await asyncio.wait_for(self.inner(req), timeout=self.policy.timeout_s)
            except TimeoutError:
                error: ToolError = ToolTimeout(f"{self.name}: tempo esgotado", tool=self.name)
            except ToolError as exc:
                error = exc
            else:
                self._notify("completed" if attempt == 1 else "warning", start, attempt)
                return result
            if not error.retryable or attempt > self.policy.max_retries:
                self._notify("error", start, attempt, error)
                raise error
            await asyncio.sleep(self.policy.backoff_base_s * 2 ** (attempt - 1))

    def _notify(
        self,
        status: Literal["completed", "warning", "error"],
        start: float,
        attempts: int,
        error: ToolError | None = None,
    ) -> None:
        if self.observer is None:
            return
        self.observer(
            ToolCallRecord(
                tool=self.name,
                status=status,
                latency_ms=int((time.perf_counter() - start) * 1000),
                attempts=attempts,
                error=f"{type(error).__name__}: {error}" if error else None,
            )
        )
