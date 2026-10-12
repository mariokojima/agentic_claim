from pydantic import BaseModel


class EligibilityDecision(BaseModel):
    eligible: bool
    reason: str
    policy_number: str | None = None
    vehicle_plate: str | None = None
