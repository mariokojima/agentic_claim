from pydantic import BaseModel


class BatchValidation(BaseModel):
    valid: int
    invalid: int
