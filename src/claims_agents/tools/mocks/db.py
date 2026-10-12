"""Banco SQLite dos mocks de domínio (clientes, apólices, sinistros, arquivos, mensagens)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from claims_agents.domain import Customer, Policy

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, cpf TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL UNIQUE, email TEXT
);
CREATE TABLE IF NOT EXISTS policies (
    number TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    protocol TEXT PRIMARY KEY, customer_id TEXT NOT NULL, policy_number TEXT NOT NULL,
    data TEXT NOT NULL, opened_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY, protocol TEXT NOT NULL, filename TEXT NOT NULL,
    mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
    uri TEXT NOT NULL, doc_type TEXT, metadata TEXT NOT NULL, stored_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, text TEXT NOT NULL,
    attachments TEXT NOT NULL, status TEXT NOT NULL, sent_at TEXT NOT NULL
);
"""


class DomainDB:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    def query(self, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(sql, params).fetchall())

    def close(self) -> None:
        self._conn.close()

    def seed(self, customers: list[Customer], policies: list[Policy]) -> None:
        with self.tx() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO customers VALUES (?,?,?,?,?)",
                [(c.id, c.name, c.cpf, c.phone, c.email) for c in customers],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO policies VALUES (?,?,?)",
                [(p.number, p.customer_id, p.model_dump_json()) for p in policies],
            )


def load_fixtures(fixtures_dir: Path) -> tuple[list[Customer], list[Policy]]:
    customers = [
        Customer.model_validate(c)
        for c in json.loads((fixtures_dir / "customers.json").read_text(encoding="utf-8"))
    ]
    raw_policies = json.loads((fixtures_dir / "policies.json").read_text(encoding="utf-8"))
    # "_note" documenta o propósito de cada fixture e não faz parte do modelo
    policies = [
        Policy.model_validate({k: v for k, v in p.items() if k != "_note"}) for p in raw_policies
    ]
    return customers, policies
