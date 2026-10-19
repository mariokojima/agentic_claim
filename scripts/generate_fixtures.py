"""Gera fixtures SINTÉTICOS determinísticos em data/fixtures/ (clientes e apólices).

Uso: uv run python scripts/generate_fixtures.py
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "fixtures"

ALL = ["COLISAO", "ROUBO_FURTO", "INCENDIO", "TERCEIROS", "VIDROS", "ASSISTENCIA_24H"]
NO_COLLISION = ["ROUBO_FURTO", "INCENDIO", "VIDROS", "ASSISTENCIA_24H"]

# (nome, [(status, início, fim, coberturas, placa, modelo, ano)], observação)
PEOPLE = [
    (
        "Ana Beatriz Sintética",
        [("ATIVA", "2026-01-15", "2027-01-14", ALL, "SNT1A23", "Onix 1.0", 2022)],
        "vigente, caminho feliz",
    ),
    (
        "Bruno Carvalho Teste",
        [("ATIVA", "2026-03-01", "2027-02-28", ALL, "TST2B34", "HB20 1.6", 2021)],
        "vigente, caminho feliz",
    ),
    (
        "Carla Dias Ficticia",
        [("VENCIDA", "2025-01-01", "2025-12-31", ALL, "FIC3C45", "Gol 1.0", 2018)],
        "apólice vencida",
    ),
    (
        "Diego Esteves Mock",
        [("ATIVA", "2026-02-10", "2027-02-09", NO_COLLISION, "MCK4D56", "Kwid 1.0", 2023)],
        "sem cobertura de colisão",
    ),
    (
        "Elisa Fontes Exemplo",
        [("CANCELADA", "2026-01-01", "2026-12-31", ALL, "EXP5E67", "Argo 1.3", 2022)],
        "apólice cancelada",
    ),
    (
        "Fabio Gomes Simulado",
        [
            ("VENCIDA", "2024-06-01", "2025-05-31", ALL, "SIM6F78", "Corolla 2.0", 2019),
            ("ATIVA", "2025-06-01", "2026-12-31", ALL, "SIM6F78", "Corolla 2.0", 2019),
        ],
        "múltiplas apólices (uma vencida, uma vigente)",
    ),
    (
        "Gabriela Hora Demo",
        [("SUSPENSA", "2026-01-01", "2026-12-31", ALL, "DEM7G89", "T-Cross 1.0", 2024)],
        "apólice suspensa",
    ),
    (
        "Heitor Ibanez Teste",
        [("ATIVA", "2026-11-01", "2027-10-31", ALL, "TST8H90", "Compass 1.3", 2025)],
        "vigência futura",
    ),
    ("Isabela Jardim Sintética", [], "cliente sem apólice"),
    (
        "João Lima Ficticio",
        [
            ("ATIVA", "2026-04-01", "2027-03-31", ALL, "FIC9J01", "Strada 1.3", 2023),
            ("ATIVA", "2026-05-01", "2027-04-30", NO_COLLISION, "FIC0J12", "Mobi 1.0", 2020),
        ],
        "dois veículos, só um com colisão",
    ),
    (
        "Karina Moura Mock",
        [
            (
                "ATIVA",
                "2026-01-01",
                "2026-12-31",
                ["COLISAO", "TERCEIROS"],
                "MCK1K23",
                "Polo 1.0",
                2022,
            )
        ],
        "vigente, cobertura mínima",
    ),
    (
        "Lucas Nunes Exemplo",
        [("ATIVA", "2026-07-01", "2027-06-30", ALL, "EXP2L34", "Renegade 1.3", 2024)],
        "vigente (cenários de fraude/injection)",
    ),
    (
        "Marina Okada Recente",
        [("ATIVA", "2026-10-10", "2027-10-09", ALL, "REC3M45", "Pulse 1.0", 2025)],
        "apólice recém-contratada (checagem corporativa)",
    ),
]


def make_cpf(rng: random.Random) -> str:
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        if len(set(base)) == 1:
            continue
        for size in (9, 10):
            total = sum(d * w for d, w in zip(base, range(size + 1, 1, -1), strict=True))
            base.append((total * 10) % 11 % 10)
        return "".join(map(str, base))


def main() -> None:
    rng = random.Random(20261012)
    customers, policies = [], []
    for i, (name, pols, note) in enumerate(PEOPLE, start=1):
        cid = f"CUST-{i:04d}"
        first = name.split()[0].lower().replace("ã", "a").replace("é", "e")
        customers.append(
            {
                "id": cid,
                "name": name,
                "cpf": make_cpf(rng),
                "phone": f"+55119000000{i:02d}",
                "email": f"{first}.{i:02d}@exemplo.invalid",
            }
        )
        for j, (status, start, end, cov, plate, model, year) in enumerate(pols, start=1):
            policies.append(
                {
                    "number": f"AUTO-{i:04d}-{j:02d}",
                    "customer_id": cid,
                    "status": status,
                    "start_date": start,
                    "end_date": end,
                    "coverages": cov,
                    "vehicle": {"plate": plate, "model": model, "year": year},
                    "_note": note,
                }
            )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "customers.json").write_text(
        json.dumps(customers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # "_note" documenta o propósito do fixture e é removido na carga
    (OUT / "policies.json").write_text(
        json.dumps(policies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(customers)} clientes e {len(policies)} apólices em {OUT}")


if __name__ == "__main__":
    main()
