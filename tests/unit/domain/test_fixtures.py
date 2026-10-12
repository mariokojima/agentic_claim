from collections import Counter
from datetime import date

from claims_agents.core.privacy import is_valid_cpf
from claims_agents.domain import CoverageType, Customer, Policy, PolicyStatus


def test_at_least_ten_synthetic_customers(fixtures: tuple[list[Customer], list[Policy]]) -> None:
    customers, policies = fixtures
    assert len(customers) >= 10 and len(policies) >= 10
    assert all(is_valid_cpf(c.cpf) for c in customers)
    assert all(c.email is None or c.email.endswith(".invalid") for c in customers)
    assert len({c.cpf for c in customers}) == len(customers)
    assert len({c.phone for c in customers}) == len(customers)


def test_fixture_coverage_of_situations(fixtures: tuple[list[Customer], list[Policy]]) -> None:
    customers, policies = fixtures
    statuses = Counter(p.status for p in policies)
    assert {PolicyStatus.ATIVA, PolicyStatus.VENCIDA, PolicyStatus.CANCELADA} <= set(statuses)
    assert any(
        p.status == PolicyStatus.ATIVA and not p.covers(CoverageType.COLISAO) for p in policies
    )
    per_customer = Counter(p.customer_id for p in policies)
    assert any(n > 1 for n in per_customer.values())
    assert any(c.id not in per_customer for c in customers)


def test_policy_helpers(fixtures: tuple[list[Customer], list[Policy]]) -> None:
    policy = fixtures[1][0]
    assert policy.is_in_force_on(date(2026, 6, 1))
    assert not policy.is_in_force_on(date(2025, 1, 1))
