from pydantic import BaseModel


class IntakeSummary(BaseModel):
    received: int
    stored: int
    untyped: int
