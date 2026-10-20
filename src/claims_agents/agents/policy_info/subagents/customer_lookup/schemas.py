from pydantic import BaseModel


class LookupOutcome(BaseModel):
    found: bool
    policies: int = 0
