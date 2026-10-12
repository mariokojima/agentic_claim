from pydantic import BaseModel


class ComplementRequest(BaseModel):
    pending: list[str]
    problems: list[str]
