"""Mock de `store_files`: grava em disco local e registra metadados no SQLite."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from claims_agents.core.errors import NotFound
from claims_agents.tools.mocks.db import DomainDB
from claims_agents.tools.mocks.faults import FaultInjector
from claims_agents.tools.schemas import StoredFile, StoreFilesRequest, StoreFilesResponse

NAME = "store_files"


class MockStoreFiles:
    def __init__(
        self, db: DomainDB, storage_dir: Path, faults: FaultInjector | None = None
    ) -> None:
        self.db = db
        self.storage_dir = storage_dir
        self.faults = faults or FaultInjector()

    async def __call__(self, req: StoreFilesRequest) -> StoreFilesResponse:
        await self.faults.maybe_fail(NAME)
        if not self.db.query("SELECT 1 FROM claims WHERE protocol = ?", (req.protocol,)):
            raise NotFound(f"Protocolo {req.protocol} não encontrado", tool=NAME)
        folder = self.storage_dir / req.protocol
        folder.mkdir(parents=True, exist_ok=True)
        stored: list[StoredFile] = []
        now = datetime.now(UTC).isoformat()
        with self.db.tx() as conn:
            for f in req.files:
                file_id = f"file_{uuid.uuid4().hex[:12]}"
                path = folder / f"{file_id}_{Path(f.filename).name}"
                path.write_bytes(f.content)
                sha = hashlib.sha256(f.content).hexdigest()
                conn.execute(
                    "INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        file_id,
                        req.protocol,
                        f.filename,
                        f.mime_type,
                        len(f.content),
                        sha,
                        path.as_uri(),
                        f.doc_type.value if f.doc_type else None,
                        json.dumps(f.metadata, default=str),
                        now,
                    ),
                )
                stored.append(
                    StoredFile(
                        file_id=file_id,
                        filename=f.filename,
                        uri=path.as_uri(),
                        sha256=sha,
                        size_bytes=len(f.content),
                    )
                )
        return StoreFilesResponse(files=stored)
