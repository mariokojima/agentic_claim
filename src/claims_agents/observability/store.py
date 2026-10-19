"""Event store em SQLite (fonte dos KPIs) e registro de conversas do simulador."""

from __future__ import annotations

import builtins
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from claims_agents.observability.events import AgentEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, ts TEXT NOT NULL, conversation_id TEXT NOT NULL, agent TEXT NOT NULL,
    subagent TEXT, event TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL, tool TEXT,
    latency_ms INTEGER, tokens INTEGER, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_conv ON events(conversation_id, ts);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, phone TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


class EventStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def add(self, ev: AgentEvent) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ev.id,
                    ev.ts.isoformat(),
                    ev.conversation_id,
                    ev.agent,
                    ev.subagent,
                    ev.event,
                    ev.details,
                    ev.status,
                    ev.tool,
                    ev.latency_ms,
                    ev.tokens,
                    json.dumps(ev.data, default=str),
                ),
            )

    def list(
        self, conversation_id: str | None = None, limit: int = 200, event: str | None = None
    ) -> list[AgentEvent]:
        sql = "SELECT * FROM events WHERE 1=1"
        params: list[object] = []
        if conversation_id:
            sql += " AND conversation_id = ?"
            params.append(conversation_id)
        if event:
            sql += " AND event = ?"
            params.append(event)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_event(r) for r in reversed(rows)]

    def add_conversation(self, conversation_id: str, phone: str, created_at: datetime) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO conversations VALUES (?,?,?)",
                (conversation_id, phone, created_at.isoformat()),
            )

    def get_conversation(self, conversation_id: str) -> dict[str, str] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_conversations(self) -> builtins.list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT id FROM conversations ORDER BY created_at").fetchall()
        return [r["id"] for r in rows]

    def close(self) -> None:
        self._conn.close()


def _row_to_event(r: sqlite3.Row) -> AgentEvent:
    return AgentEvent(
        id=r["id"],
        ts=datetime.fromisoformat(r["ts"]),
        conversation_id=r["conversation_id"],
        agent=r["agent"],
        subagent=r["subagent"],
        event=r["event"],
        details=r["details"],
        status=r["status"],
        tool=r["tool"],
        latency_ms=r["latency_ms"],
        tokens=r["tokens"],
        data=json.loads(r["data"]),
    )
