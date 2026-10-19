"""Mock de `open_claim`: valida cliente/apólice e gera protocolo sequencial."""

import json
from datetime import UTC, datetime

from claims_agents.core.errors import InvalidRequest, NotFound
from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.schemas import OpenClaimRequest, OpenClaimResponse

NAME = "open_claim"


class MockOpenClaim:
    def __init__(self, db: DomainDB, faults: FaultInjector | None = None) -> None:
        self.db = db
        self.faults = faults or FaultInjector()

    async def __call__(self, req: OpenClaimRequest) -> OpenClaimResponse:
        await self.faults.maybe_fail(NAME)
        rows = self.db.query(
            "SELECT customer_id FROM policies WHERE number = ?", (req.policy_number,)
        )
        if not rows:
            raise NotFound(f"Apólice {req.policy_number} não encontrada", tool=NAME)
        if rows[0]["customer_id"] != req.customer_id:
            raise InvalidRequest("Apólice não pertence ao cliente informado", tool=NAME)
        opened_at = datetime.now(UTC)
        with self.db.tx() as conn:
            seq = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] + 1
            protocol = f"SIN-{opened_at.year}-{seq:06d}"
            conn.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?)",
                (
                    protocol,
                    req.customer_id,
                    req.policy_number,
                    json.dumps({"claim_type": req.claim_type} | req.event.model_dump(mode="json")),
                    opened_at.isoformat(),
                ),
            )
        return OpenClaimResponse(protocol=protocol, opened_at=opened_at)
