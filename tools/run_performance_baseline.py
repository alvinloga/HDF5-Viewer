"""Emit a reproducible Data Viewer Phase 0 performance baseline JSON report."""

from __future__ import annotations

import argparse
import gc
import gzip
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_viewer.performance import (  # noqa: E402
    BenchmarkBudget,
    BenchmarkMetric,
    BudgetConfig,
    SyntheticDatasetSpec,
    generate_hierarchy_paths,
    generate_table_rows,
    run_benchmark,
)
from data_viewer.tasks import CancellationToken  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic Phase 0 Data Viewer performance baseline probes.",
    )
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--rows", type=int, default=2048)
    parser.add_argument("--columns", type=int, default=16)
    parser.add_argument("--hierarchy-depth", type=int, default=4)
    parser.add_argument("--fanout", type=int, default=8)
    args = parser.parse_args(argv)

    spec = SyntheticDatasetSpec(
        rows=args.rows,
        columns=args.columns,
        hierarchy_depth=args.hierarchy_depth,
        fanout=args.fanout,
    )

    table_rows = generate_table_rows(spec)
    hierarchy_paths = generate_hierarchy_paths(spec)
    block = bytes((index % 251 for index in range(64 * 1024)))
    compressed = gzip.compress(block)

    reports = (
        run_benchmark(
            BenchmarkMetric.COLD_LAUNCH,
            lambda: _cold_launch_probe(),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.OPEN_METADATA,
            lambda: {"metadata_nodes": len(hierarchy_paths)},
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.FIRST_TABLE_PAGE,
            lambda: {"rows": len(table_rows[: min(256, len(table_rows))])},
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.TABLE_SCROLL,
            lambda: {"rows": len(table_rows[len(table_rows) // 2 : len(table_rows) // 2 + 128])},
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.EXPAND_NODE_MANY_CHILDREN,
            lambda: {"paths": len(hierarchy_paths)},
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.SLICE_2D,
            lambda: _slice_probe(rows=args.rows, columns=args.columns),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.NIFTI_PLANE,
            lambda: _nifti_plane_probe(size=max(args.columns, 8)),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.CANCELLATION_LATENCY,
            lambda: _cancellation_probe(),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.REPEATED_OPEN_CLOSE_MEMORY_GROWTH,
            lambda: _repeated_open_close_probe(spec),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.GZIP_EXTRACTION,
            lambda: {"bytes": len(gzip.decompress(compressed))},
            iterations=args.iterations,
            warmups=args.warmups,
        ),
        run_benchmark(
            BenchmarkMetric.PLUGIN_CHUNK_THROUGHPUT,
            lambda: _plugin_chunk_probe(table_rows, chunk_size=256),
            iterations=args.iterations,
            warmups=args.warmups,
        ),
    )
    budget = BenchmarkBudget(
        reports=reports,
        config=BudgetConfig(thresholds={}, source="phase-0-baseline"),
    )
    print(json.dumps(budget.to_json(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _cold_launch_probe() -> dict[str, int]:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import data_viewer; print(data_viewer.__version__)",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return {"processes": 1}


def _slice_probe(*, rows: int, columns: int) -> dict[str, int]:
    width = max(columns, 1)
    height = max(min(rows, 512), 1)
    plane = [[row * width + column for column in range(width)] for row in range(height)]
    center = plane[height // 2][width // 2]
    return {"height": height, "width": width, "center": center}


def _nifti_plane_probe(*, size: int) -> dict[str, int]:
    plane = [[(x + y) % 4096 for x in range(size)] for y in range(size)]
    return {"voxels": size * size, "sample": plane[size // 2][size // 2]}


def _cancellation_probe() -> dict[str, int]:
    token = CancellationToken()
    started = perf_counter()
    token.cancel()
    try:
        token.raise_if_cancelled(operation="performance.cancellation")
    except Exception:
        elapsed_us = int((perf_counter() - started) * 1_000_000)
    else:
        elapsed_us = -1
    return {"cancelled": int(token.is_cancelled), "elapsed_us": elapsed_us}


def _repeated_open_close_probe(spec: SyntheticDatasetSpec) -> dict[str, int]:
    before = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else 0
    for _ in range(10):
        rows = generate_table_rows(spec)
        assert rows
        del rows
    gc.collect()
    after = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else 0
    return {"allocated_block_delta": after - before}


def _plugin_chunk_probe(rows: tuple[dict[str, int], ...], *, chunk_size: int) -> dict[str, int]:
    total = 0
    chunks = 0
    for offset in range(0, len(rows), chunk_size):
        chunks += 1
        for row in rows[offset : offset + chunk_size]:
            total += row["column_0"]
    return {"chunks": chunks, "checksum": total}


if __name__ == "__main__":
    raise SystemExit(main())
