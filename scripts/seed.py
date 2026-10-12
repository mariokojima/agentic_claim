"""Carrega os fixtures sintéticos no SQLite de domínio (data/claims.db).

Uso: uv run python scripts/seed.py [--db caminho]
"""

import argparse
from pathlib import Path

from claims_agents.core.settings import PROJECT_ROOT, get_settings
from claims_agents.tools.mocks.db import DomainDB, load_fixtures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    db_path = args.db or get_settings().domain_db_path
    customers, policies = load_fixtures(PROJECT_ROOT / "data" / "fixtures")
    db = DomainDB(db_path)
    db.seed(customers, policies)
    db.close()
    print(f"Seed concluído: {len(customers)} clientes, {len(policies)} apólices em {db_path}")


if __name__ == "__main__":
    main()
