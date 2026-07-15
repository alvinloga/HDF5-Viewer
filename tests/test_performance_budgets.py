"""Performance benchmark harness and budget gate contracts."""

from __future__ import annotations

from data_viewer.performance import (
    BenchmarkMetric,
    BenchmarkThreshold,
    BudgetConfig,
    SyntheticDatasetSpec,
    evaluate_budget,
    generate_hierarchy_paths,
    generate_table_rows,
    platform_profile,
    run_benchmark,
)
from tools.run_performance_baseline import main as run_performance_baseline


def test_benchmark_report_records_distribution_and_peak_memory() -> None:
    counter = {"value": 0}

    def measured() -> dict[str, int]:
        counter["value"] += 1
        payload = [counter["value"]] * 128
        return {"last_value": payload[-1]}

    report = run_benchmark(
        BenchmarkMetric.FIRST_TABLE_PAGE,
        measured,
        iterations=5,
        warmups=1,
    )

    assert report.metric is BenchmarkMetric.FIRST_TABLE_PAGE
    assert report.iterations == 5
    assert report.median_ms >= 0
    assert report.p95_ms >= report.median_ms
    assert report.peak_memory_bytes > 0
    assert report.extra["last_value"] == 6
    assert report.platform["python"]
    assert report.platform["system"]


def test_budget_gate_reports_structured_violations() -> None:
    report = run_benchmark(
        BenchmarkMetric.CANCELLATION_LATENCY,
        lambda: {"allocated": len([0] * 128)},
        iterations=3,
        warmups=0,
    )
    budget = BudgetConfig(
        thresholds={
            BenchmarkMetric.CANCELLATION_LATENCY: BenchmarkThreshold(
                max_median_ms=0,
                max_p95_ms=0,
                max_peak_memory_bytes=0,
            )
        },
        source="unit-test",
    )

    result = evaluate_budget(report, budget)

    assert result.passed is False
    assert {violation.field for violation in result.violations} == {
        "median_ms",
        "p95_ms",
        "peak_memory_bytes",
    }
    assert result.to_json()["metric"] == "cancellation_latency"


def test_budget_without_threshold_is_informational_until_baseline_exists() -> None:
    report = run_benchmark(
        BenchmarkMetric.PLUGIN_CHUNK_THROUGHPUT,
        lambda: {},
        iterations=2,
        warmups=0,
    )

    result = evaluate_budget(report, BudgetConfig(thresholds={}, source="phase-0"))

    assert result.passed is True
    assert result.enforced is False
    assert result.violations == ()


def test_synthetic_generators_are_reproducible_and_bounded() -> None:
    spec = SyntheticDatasetSpec(rows=4, columns=3, hierarchy_depth=2, fanout=2)

    assert generate_table_rows(spec) == generate_table_rows(spec)
    assert generate_table_rows(spec)[0] == {"column_0": 0, "column_1": 1, "column_2": 2}
    assert generate_hierarchy_paths(spec) == (
        "/node_0_0/node_1_0",
        "/node_0_0/node_1_1",
        "/node_0_1/node_1_0",
        "/node_0_1/node_1_1",
    )


def test_platform_profile_names_the_runtime_without_paths() -> None:
    profile = platform_profile()

    assert profile["system"]
    assert profile["python"]
    assert "Users" not in " ".join(profile.values())


def test_baseline_tool_reports_all_release_budget_metrics(capsys) -> None:
    assert (
        run_performance_baseline(
            [
                "--iterations",
                "1",
                "--warmups",
                "0",
                "--rows",
                "4",
                "--columns",
                "2",
                "--hierarchy-depth",
                "1",
                "--fanout",
                "2",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out

    for metric in BenchmarkMetric:
        assert f'"metric": "{metric.value}"' in output
