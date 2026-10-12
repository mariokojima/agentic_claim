"""Mock de `validate_document`: validação determinística (ADR-0007) guiada pelo checklist."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from claims_agents.core.errors import NotFound
from claims_agents.core.privacy import only_digits
from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.schemas import (
    ValidateDocumentRequest,
    ValidateDocumentResponse,
    ValidationIssue,
)

NAME = "validate_document"


class MockValidateDocument:
    def __init__(
        self, db: DomainDB, checklist: dict[str, Any], faults: FaultInjector | None = None
    ) -> None:
        self.db = db
        self.checklist = checklist
        self.faults = faults or FaultInjector()

    async def __call__(self, req: ValidateDocumentRequest) -> ValidateDocumentResponse:
        await self.faults.maybe_fail(NAME)
        rows = self.db.query("SELECT * FROM files WHERE file_id = ?", (req.file_id,))
        if not rows:
            raise NotFound(f"Arquivo {req.file_id} não encontrado", tool=NAME)
        f = rows[0]
        rule = self._rule(req.context.claim_type, req.doc_type.value)
        metadata: dict[str, Any] = json.loads(f["metadata"])
        issues: list[ValidationIssue] = []

        if f["protocol"] != req.context.protocol:
            issues.append(_issue("wrong_protocol", "O arquivo não pertence a este protocolo."))
        if f["mime_type"] not in rule.get("mime_types", []):
            issues.append(
                _issue("invalid_mime", f"Formato {f['mime_type']} não aceito para {rule['label']}.")
            )
        if f["size_bytes"] > rule.get("max_size_bytes", float("inf")):
            issues.append(_issue("too_large", "Arquivo acima do tamanho máximo."))
        if f["size_bytes"] < rule.get("min_size_bytes", 0):
            issues.append(_issue("too_small", "Arquivo muito pequeno ou vazio."))
        dup = self.db.query(
            "SELECT file_id FROM files"
            " WHERE protocol = ? AND sha256 = ? AND file_id <> ? AND stored_at <= ?",
            (f["protocol"], f["sha256"], f["file_id"], f["stored_at"]),
        )
        if dup:
            issues.append(_issue("duplicate", "Este arquivo já foi enviado anteriormente."))
        for key in rule.get("required_metadata", []):
            if not metadata.get(key):
                issues.append(_issue("missing_metadata", f"Metadado obrigatório ausente: {key}."))
        issues.extend(self._consistency(rule.get("consistency", {}), metadata, req))
        return ValidateDocumentResponse(file_id=req.file_id, valid=not issues, issues=issues)

    def _rule(self, claim_type: str, doc_type: str) -> dict[str, Any]:
        for item in self.checklist.get(claim_type, []):
            if item["doc_type"] == doc_type:
                return dict(item)
        return {"label": doc_type, "mime_types": []}

    @staticmethod
    def _consistency(
        spec: dict[str, str], metadata: dict[str, Any], req: ValidateDocumentRequest
    ) -> list[ValidationIssue]:
        ctx = req.context
        issues: list[ValidationIssue] = []
        for key, check in spec.items():
            value = metadata.get(key)
            if value is None:
                continue
            if check == "customer_cpf" and ctx.customer_cpf:
                if only_digits(str(value)) != only_digits(ctx.customer_cpf):
                    issues.append(
                        _issue("cpf_mismatch", "O CPF do documento não confere com o do segurado.")
                    )
            elif check == "vehicle_plate" and ctx.vehicle_plate:
                if _norm_plate(str(value)) != _norm_plate(ctx.vehicle_plate):
                    issues.append(
                        _issue(
                            "plate_mismatch", "A placa do documento não confere com a da apólice."
                        )
                    )
            elif check == "not_before_event_date" and ctx.event_date:
                captured = _parse_date(value)
                if captured is None:
                    issues.append(_issue("invalid_date", "Data de captura inválida."))
                elif captured < ctx.event_date:
                    issues.append(
                        _issue("photo_before_event", "A foto é anterior à data do evento.")
                    )
        return issues


def _issue(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message)


def _norm_plate(plate: str) -> str:
    return "".join(ch for ch in plate.upper() if ch.isalnum())


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None
