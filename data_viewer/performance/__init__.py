"""Performance benchmark harness and budget contracts for Data Viewer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import platform
import statistics
import time
import tracemalloc

from data_viewer.domain import JsonValue


class BenchmarkMetric(StrEnum):
    """Named v1 performance metrics tracked by the release budget."""

    COLD_LAUNCH = "cold_launch"
    OPEN_METADATA = "open_metadata"
    EXPAND_NODE_MANY_CHILDREN = "expand_node_many_children"
    FIRST_TABLE_PAGE = "first_table_page"
    TABLE_SCROLL = "table_scroll"
    SLICE_2D = "slice_2d"
    NIFTI_PLANE = "nifti_plane"
    CANCELLATION_LATENCY = "cancellation_latency"
    REPEATED_OPEN_CLOSE_MEMORY_GROWTH = "repeated_open_close_memory_growth"
    GZIP_EXTRACTION = "gzip_extraction"
    PLUGIN_CHUNK_THROUGHPUT = "plugin_chunk_throughput"


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Measured benchmark distribution for one metric on one runtime."""

    metric: BenchmarkMetric
    iterations: int
    median_ms: float
    p95_ms: float
    peak_memory_bytes: int
    samples_ms: tuple[float, ...]
    platform: Mapping[str, str]
    extra: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric", BenchmarkMetric(self.metric))
        object.__setattr__(self, "samples_ms", tuple(float(item) for item in self.samples_ms))
        object.__setattr__(self, "platform", dict(self.platform))
        object.__setattr__(self, "extra", dict(self.extra))
        if self.iterations < 1:
            raise ValueError("benchmark iterations must be positive")
        if len(self.samples_ms) != self.iterations:
            raise ValueError("sample count must match iterations")
        if self.median_ms < 0 or self.p95_ms < 0:
            raise ValueError("benchmark timings must be non-negative")
        if self.peak_memory_bytes < 0:
            raise ValueError("benchmark peak memory must be non-negative")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "metric": self.metric.value,
            "iterations": self.iterations,
            "median_ms": self.median_ms,
            "p95_ms": self.p95_ms,
            "peak_memory_bytes": self.peak_memory_bytes,
            "samples_ms": list(self.samples_ms),
            "platform": dict(self.platform),
            "extra": dict(self.extra),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkThreshold:
    """Optional numeric regression thresholds for one metric."""

    max_median_ms: float | None = None
    max_p95_ms: float | None = None
    max_peak_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.max_median_ms is not None and self.max_median_ms < 0:
            raise ValueError("median threshold must be non-negative")
        if self.max_p95_ms is not None and self.max_p95_ms < 0:
            raise ValueError("p95 threshold must be non-negative")
        if self.max_peak_memory_bytes is not None and self.max_peak_memory_bytes < 0:
            raise ValueError("memory threshold must be non-negative")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "max_median_ms": self.max_median_ms,
            "max_p95_ms": self.max_p95_ms,
            "max_peak_memory_bytes": self.max_peak_memory_bytes,
        }


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    """Versioned performance budget configuration.

    Empty thresholds are allowed during Phase 0 baseline collection. Once both
    Windows and Linux baselines exist, release tasks add numeric thresholds here
    or in a serialized equivalent.
    """

    thresholds: Mapping[BenchmarkMetric, BenchmarkThreshold]
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("budget source must not be empty")
        object.__setattr__(
            self,
            "thresholds",
            {
                BenchmarkMetric(metric): threshold
                for metric, threshold in self.thresholds.items()
            },
        )


@dataclass(frozen=True, slots=True)
class BenchmarkBudget:
    """Named collection of reports and budget evaluations."""

    reports: tuple[BenchmarkReport, ...]
    config: BudgetConfig

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "config_source": self.config.source,
            "reports": [report.to_json() for report in self.reports],
        }


@dataclass(frozen=True, slots=True)
class BudgetViolation:
    """One failed threshold comparison."""

    field: str
    observed: float
    limit: float

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "field": self.field,
            "observed": self.observed,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class BudgetEvaluation:
    """Structured budget result for a report."""

    metric: BenchmarkMetric
    passed: bool
    enforced: bool
    violations: tuple[BudgetViolation, ...] = ()

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "metric": self.metric.value,
            "passed": self.passed,
            "enforced": self.enforced,
            "violations": [violation.to_json() for violation in self.violations],
        }


@dataclass(frozen=True, slots=True)
class SyntheticDatasetSpec:
    """Deterministic synthetic benchmark dataset shape."""

    rows: int
    columns: int
    hierarchy_depth: int
    fanout: int

    def __post_init__(self) -> None:
        for label, value in (
            ("rows", self.rows),
            ("columns", self.columns),
            ("hierarchy_depth", self.hierarchy_depth),
            ("fanout", self.fanout),
        ):
            if value < 1:
                raise ValueError(f"synthetic {label} must be positive")


BenchmarkCallable = Callable[[], Mapping[str, JsonValue] | None]


def run_benchmark(
    metric: BenchmarkMetric,
    callback: BenchmarkCallable,
    *,
    iterations: int,
    warmups: int = 1,
) -> BenchmarkReport:
    """Measure a callback and report median, high percentile, and peak memory."""

    if iterations < 1:
        raise ValueError("benchmark iterations must be positive")
    if warmups < 0:
        raise ValueError("benchmark warmups must be non-negative")
    for _ in range(warmups):
        callback()

    samples: list[float] = []
    peak_memory = 0
    extra: Mapping[str, JsonValue] = {}
    for _ in range(iterations):
        tracemalloc.start()
        started = time.perf_counter()
        try:
            result = callback()
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        samples.append(elapsed_ms)
        peak_memory = max(peak_memory, peak)
        if result is not None:
            extra = dict(result)

    return BenchmarkReport(
        metric=BenchmarkMetric(metric),
        iterations=iterations,
        median_ms=statistics.median(samples),
        p95_ms=_percentile(samples, 95),
        peak_memory_bytes=peak_memory,
        samples_ms=tuple(samples),
        platform=platform_profile(),
        extra=extra,
    )


def evaluate_budget(
    report: BenchmarkReport,
    config: BudgetConfig,
) -> BudgetEvaluation:
    """Compare a benchmark report with an optional configured threshold."""

    threshold = config.thresholds.get(report.metric)
    if threshold is None:
        return BudgetEvaluation(
            metric=report.metric,
            passed=True,
            enforced=False,
        )
    violations: list[BudgetViolation] = []
    _check_limit(violations, "median_ms", report.median_ms, threshold.max_median_ms)
    _check_limit(violations, "p95_ms", report.p95_ms, threshold.max_p95_ms)
    _check_limit(
        violations,
        "peak_memory_bytes",
        float(report.peak_memory_bytes),
        float(threshold.max_peak_memory_bytes)
        if threshold.max_peak_memory_bytes is not None
        else None,
    )
    return BudgetEvaluation(
        metric=report.metric,
        passed=not violations,
        enforced=True,
        violations=tuple(violations),
    )


def generate_table_rows(spec: SyntheticDatasetSpec) -> tuple[dict[str, int], ...]:
    """Generate deterministic row dictionaries for table-page benchmarks."""

    return tuple(
        {
            f"column_{column}": row * spec.columns + column
            for column in range(spec.columns)
        }
        for row in range(spec.rows)
    )


def generate_hierarchy_paths(spec: SyntheticDatasetSpec) -> tuple[str, ...]:
    """Generate deterministic deep hierarchy paths without touching the filesystem."""

    paths = [""]
    for depth in range(spec.hierarchy_depth):
        paths = [
            f"{prefix}/node_{depth}_{index}"
            for prefix in paths
            for index in range(spec.fanout)
        ]
    return tuple(paths)


def platform_profile() -> dict[str, str]:
    """Return a path-free runtime profile suitable for benchmark reports."""

    return {
        "system": platform.system() or "unknown",
        "release": platform.release() or "unknown",
        "machine": platform.machine() or "unknown",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
    }


def _check_limit(
    violations: list[BudgetViolation],
    field: str,
    observed: float,
    limit: float | None,
) -> None:
    if limit is not None and observed > limit:
        violations.append(
            BudgetViolation(field=field, observed=observed, limit=limit)
        )


def _percentile(samples: list[float], percentile: int) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]


__all__ = [
    "BenchmarkBudget",
    "BenchmarkMetric",
    "BenchmarkReport",
    "BenchmarkThreshold",
    "BudgetConfig",
    "BudgetEvaluation",
    "BudgetViolation",
    "SyntheticDatasetSpec",
    "evaluate_budget",
    "generate_hierarchy_paths",
    "generate_table_rows",
    "platform_profile",
    "run_benchmark",
]
