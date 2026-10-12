"""ToolRegistry: único ponto onde agentes obtêm tools (sempre pelas interfaces)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claims_agents.core.settings import Settings, load_config
from claims_agents.tools.interfaces import (
    GetCustomerData,
    OpenClaim,
    SendWhatsapp,
    StoreFiles,
    ValidateDocument,
)
from claims_agents.tools.resilience import ResilientTool, RetryPolicy, ToolObserver

TOOL_NAMES = (
    "get_customer_data",
    "send_whatsapp",
    "open_claim",
    "store_files",
    "validate_document",
)


@dataclass(frozen=True)
class ToolRegistry:
    get_customer_data: GetCustomerData
    send_whatsapp: SendWhatsapp
    open_claim: OpenClaim
    store_files: StoreFiles
    validate_document: ValidateDocument


def build_registry(
    settings: Settings,
    *,
    db_path: Path | None = None,
    storage_dir: Path | None = None,
    faults: Any | None = None,
    delivery: Any | None = None,
    observer: ToolObserver | None = None,
    checklist: dict[str, Any] | None = None,
) -> ToolRegistry:
    """Monta o registry conforme `settings.tools.impl` (mock | real), com resiliência aplicada."""
    from claims_agents.tools.mocks.claims import MockOpenClaim
    from claims_agents.tools.mocks.customer_data import MockGetCustomerData
    from claims_agents.tools.mocks.db import DomainDB
    from claims_agents.tools.mocks.faults import FaultInjector
    from claims_agents.tools.mocks.files import MockStoreFiles
    from claims_agents.tools.mocks.validation import MockValidateDocument
    from claims_agents.tools.mocks.whatsapp import MockSendWhatsapp
    from claims_agents.tools.real import NotImplementedTool

    faults = faults or FaultInjector()
    db = DomainDB(db_path or settings.domain_db_path)
    mocks: dict[str, Any] = {
        "get_customer_data": MockGetCustomerData(db, faults),
        "send_whatsapp": MockSendWhatsapp(db, faults, delivery),
        "open_claim": MockOpenClaim(db, faults),
        "store_files": MockStoreFiles(db, storage_dir or settings.storage_path, faults),
        "validate_document": MockValidateDocument(
            db, checklist if checklist is not None else load_config("documents_checklist"), faults
        ),
    }
    policy = RetryPolicy(
        timeout_s=settings.tools.default_timeout_s,
        max_retries=settings.tools.max_retries,
        backoff_base_s=settings.tools.backoff_base_s,
    )
    tools: dict[str, Any] = {}
    for name in TOOL_NAMES:
        impl = settings.tools.impl.get(name, "mock")
        inner = mocks[name] if impl == "mock" else NotImplementedTool(name)
        tools[name] = ResilientTool(name, inner, policy, observer)
    return ToolRegistry(**tools)
