from pydantic import BaseModel


class RegistrationOutcome(BaseModel):
    protocol: str
    opened_at: str
