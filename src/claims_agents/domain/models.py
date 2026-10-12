"""Entidades de domínio (dados sintéticos)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from claims_agents.domain.enums import ClaimType, CoverageType, DocumentType, PolicyStatus


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Customer(_Model):
    id: str
    name: str
    cpf: str
    phone: str
    email: str | None = None


class Vehicle(_Model):
    plate: str
    model: str
    year: int


class Policy(_Model):
    number: str
    customer_id: str
    status: PolicyStatus
    start_date: date
    end_date: date
    coverages: list[CoverageType]
    vehicle: Vehicle

    def is_in_force_on(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date

    def covers(self, coverage: CoverageType) -> bool:
        return coverage in self.coverages


class ClaimEventData(_Model):
    event_date: date
    event_time: time | None = None
    location: str
    description: str
    parties: list[str] = Field(default_factory=list)
    damages: str = ""
    has_injuries: bool = False
    has_third_parties: bool = False


class Claim(_Model):
    protocol: str
    customer_id: str
    policy_number: str
    claim_type: ClaimType = ClaimType.COLISAO
    event: ClaimEventData
    opened_at: datetime


class Document(_Model):
    file_id: str
    protocol: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    uri: str
    doc_type: DocumentType | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
