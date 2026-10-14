"""Modo demonstração (ADR-0012): atraso ilustrativo antes de executar um nó (síncrono ou não)."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from claims_agents.core.types import NodeFn


def with_demo_delay[S](fn: NodeFn[S], delay_ms: int) -> NodeFn[S]:
    """Segura o nó em "processando" por `delay_ms` antes de executá-lo. 0 = sem efeito."""
    if delay_ms <= 0:
        return fn

    async def delayed(state: S) -> Any:
        await asyncio.sleep(delay_ms / 1000)
        result = fn(state)
        return await result if inspect.isawaitable(result) else result

    return delayed


def demo_wrapper(delay_ms: int) -> Any:
    """`NodeWrapper` para os subgrafos dos especialistas (identidade quando desligado)."""

    def wrap[S](fn: NodeFn[S]) -> NodeFn[S]:
        return with_demo_delay(fn, delay_ms)

    return wrap
