"""Modo demonstração (ADR-0012): atrasos ilustrativos por nó e por tool."""

import time
from typing import Any

from claims_agents.domain import Customer
from claims_agents.graph.build_graph import with_demo_delay
from claims_agents.state import GlobalState
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.resilience import ResilientTool, RetryPolicy, ToolCallRecord
from claims_agents.tools.schemas import GetCustomerDataRequest


async def _node(state: GlobalState) -> dict[str, Any]:
    return {"turns": 1}


def test_zero_delay_returns_original_node() -> None:
    assert with_demo_delay(_node, 0) is _node


async def test_node_delay_holds_before_running() -> None:
    delayed = with_demo_delay(_node, 50)
    start = time.perf_counter()
    assert await delayed(GlobalState(conversation_id="c")) == {"turns": 1}
    assert time.perf_counter() - start >= 0.05


async def test_tool_notifies_processing_and_applies_delay_outside_timeout(
    domain_db: Any, happy_customer: Customer
) -> None:
    from claims_agents.tools.mocks.customer_data import MockGetCustomerData

    records: list[ToolCallRecord] = []
    tool = ResilientTool(
        "get_customer_data",
        MockGetCustomerData(domain_db, FaultInjector()),
        RetryPolicy(timeout_s=0.02, demo_delay_s=0.05),  # atraso maior que o timeout não estoura
        records.append,
    )
    await tool(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert [r.status for r in records] == ["processing", "completed"]
    assert records[-1].latency_ms >= 50
