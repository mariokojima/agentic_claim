"""Runner de cenários de avaliação (seção 12). Gera reports/<data>_<suíte>/report.md.

Exemplos:
  uv run python scripts/run_scenarios.py --suite smoke                       # só regras, sem LLM
  uv run python scripts/run_scenarios.py --suite full --experiments all --allow-real-llm
  uv run python scripts/run_scenarios.py --suite full --experiments baseline,llm_full \\
      --allow-real-llm
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from claims_agents.core.settings import PROJECT_ROOT
from claims_agents.evaluation.config import EXPERIMENT_ORDER, load_experiments, load_scenarios
from claims_agents.evaluation.report import write_report
from claims_agents.evaluation.runner import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--suite", default="smoke", choices=["smoke", "full"])
    parser.add_argument(
        "--experiments",
        default="baseline",
        help=f"lista separada por vírgula ou 'all' ({', '.join(EXPERIMENT_ORDER)})",
    )
    parser.add_argument(
        "--allow-real-llm",
        action="store_true",
        help="permite experimentos com LLM real (custo; requer chave no .env)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="cenários em paralelo; >1 acelera, mas infla a latência medida por turno",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="código de saída 1 se algum cenário do primeiro experimento falhar",
    )
    args = parser.parse_args()
    logging.disable(logging.WARNING)

    names = EXPERIMENT_ORDER if args.experiments == "all" else args.experiments.split(",")
    scenarios = load_scenarios(args.suite)
    out = args.out or PROJECT_ROOT / "reports" / f"{datetime.now():%Y%m%d-%H%M%S}_{args.suite}"
    runs = []
    for experiment in load_experiments(names):
        print(f"▶ {experiment.name}: {len(scenarios)} cenário(s)...", flush=True)
        run = asyncio.run(
            run_experiment(
                experiment,
                scenarios,
                allow_real_llm=args.allow_real_llm,
                concurrency=args.concurrency,
            )
        )
        if run.skipped:
            print(f"  ↷ pulado: {run.skipped}")
        else:
            passed = sum(r.passed for r in run.results)
            print(f"  ✔ {passed}/{len(run.results)} cenários OK em {run.wall_s}s")
        runs.append(run)
    report, _ = write_report(args.suite, runs, out)
    print(f"\nRelatório: {report.relative_to(PROJECT_ROOT)}")
    latest = PROJECT_ROOT / "reports" / "latest.md"
    latest.write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    if args.fail_on_error and runs and not runs[0].skipped:
        return 0 if all(r.passed for r in runs[0].results) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
