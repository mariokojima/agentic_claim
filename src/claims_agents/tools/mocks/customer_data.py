"""Mock de `get_customer_data`."""

from claims_agents.core.errors import NotFound
from claims_agents.core.privacy import mask_cpf, only_digits
from claims_agents.domain import Policy
from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.schemas import (
    CustomerView,
    GetCustomerDataRequest,
    GetCustomerDataResponse,
    PolicyView,
)

NAME = "get_customer_data"


class MockGetCustomerData:
    def __init__(self, db: DomainDB, faults: FaultInjector | None = None) -> None:
        self.db = db
        self.faults = faults or FaultInjector()

    async def __call__(self, req: GetCustomerDataRequest) -> GetCustomerDataResponse:
        await self.faults.maybe_fail(NAME)
        rows = []
        if req.cpf:
            rows = self.db.query("SELECT * FROM customers WHERE cpf = ?", (only_digits(req.cpf),))
        if not rows and req.phone:
            rows = self.db.query(
                "SELECT * FROM customers WHERE phone = ?", (_norm_phone(req.phone),)
            )
        if not rows:
            raise NotFound("Cliente não encontrado", tool=NAME)
        row = rows[0]
        policies = [
            Policy.model_validate_json(r["data"])
            for r in self.db.query(
                "SELECT data FROM policies WHERE customer_id = ? ORDER BY number", (row["id"],)
            )
        ]
        return GetCustomerDataResponse(
            customer=CustomerView(
                id=row["id"], name=row["name"], cpf_masked=mask_cpf(row["cpf"]), phone=row["phone"]
            ),
            policies=[
                PolicyView(
                    number=p.number,
                    status=p.status,
                    start_date=p.start_date,
                    end_date=p.end_date,
                    coverages=p.coverages,
                    vehicle_plate=p.vehicle.plate,
                    vehicle_model=p.vehicle.model,
                )
                for p in policies
            ],
        )


def _norm_phone(phone: str) -> str:
    digits = only_digits(phone)
    if not digits.startswith("55"):
        digits = "55" + digits
    return "+" + digits
