#!/usr/bin/env python
"""Generate the release cantilever benchmark Markdown and CSV artifacts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engines.fea.cantilever_benchmark import write_cantilever_benchmark_artifacts  # noqa: E402


def main() -> None:
    results = write_cantilever_benchmark_artifacts(
        report_path=ROOT / "docs" / "cantilever-benchmark-report-2026-04-28.md",
        csv_path=ROOT / "docs" / "cantilever-benchmark-2026-04-28.csv",
    )
    print(f"Wrote cantilever benchmark for {len(results)} cases.")


if __name__ == "__main__":
    main()
