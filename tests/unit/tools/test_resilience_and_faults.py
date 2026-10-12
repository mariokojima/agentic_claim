import pytest

from claims_agents.core.errors import NotFound, ToolTimeout, UpstreamError
from claims_agents.domain import Customer
from claims_agents.tools.mocks.faults import FaultInjector, FaultRule
from claims_agents.tools.registry import ToolRegistry
from claims_agents.tools.resilience import ToolCallRecord
from claims_agents.tools.schemas import GetCustomerDataRequest


async def test_timeout_is_retried_then_fails(
    registry: ToolRegistry,
    faults: FaultInjector,
    happy_customer: Customer,
    tool_calls: list[ToolCallRecord],
) -> None:
    faults.add("get_customer_data", FaultRule(kind="timeout", delay_s=1.0))
    with pytest.raises(ToolTimeout):
        await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert tool_calls[-1].status == "error" and tool_calls[-1].attempts == 3


async def test_transient_upstream_error_recovers_with_retry(
    registry: ToolRegistry,
    faults: FaultInjector,
    happy_customer: Customer,
    tool_calls: list[ToolCallRecord],
) -> None:
    faults.add("get_customer_data", FaultRule(kind="upstream", times=1))
    resp = await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert resp.customer.id == happy_customer.id
    assert tool_calls[-1].status == "warning" and tool_calls[-1].attempts == 2


async def test_persistent_upstream_error(
    registry: ToolRegistry, faults: FaultInjector, happy_customer: Customer
) -> None:
    faults.add("get_customer_data", FaultRule(kind="upstream", status_code=502))
    with pytest.raises(UpstreamError) as exc:
        await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert exc.value.status_code == 502


async def test_not_found_is_not_retried(
    registry: ToolRegistry,
    faults: FaultInjector,
    happy_customer: Customer,
    tool_calls: list[ToolCallRecord],
) -> None:
    faults.add("get_customer_data", FaultRule(kind="not_found"))
    with pytest.raises(NotFound):
        await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert tool_calls[-1].attempts == 1


async def test_probability_zero_never_fails(
    registry: ToolRegistry, faults: FaultInjector, happy_customer: Customer
) -> None:
    faults.add("get_customer_data", FaultRule(kind="upstream", probability=0.0))
    resp = await registry.get_customer_data(GetCustomerDataRequest(cpf=happy_customer.cpf))
    assert resp.customer.name == happy_customer.name
