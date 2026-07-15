# Performance budgets and baselines

DV-1001 establishes the Phase 0 performance harness. The release threshold policy is intentionally two-step:

1. collect reproducible Windows and Linux baselines on named hardware/runtime profiles;
2. encode numeric thresholds only after both baselines exist.

The harness records median latency, high-percentile latency, peak traced memory, runtime profile, and metric-specific counters. A missing threshold is informational rather than a pass/fail gate during Phase 0.

## Baseline command

Run from the repository root:

```powershell
venv\Scripts\python.exe tools\run_performance_baseline.py --iterations 7 --warmups 1
```

The command emits JSON with `config_source`, per-metric `reports`, `median_ms`, `p95_ms`, `peak_memory_bytes`, `samples_ms`, a path-free platform profile, and deterministic synthetic workload counters.

## Covered Phase 0 metrics

- `cold_launch`: subprocess import/startup probe.
- `open_metadata`: deterministic hierarchy metadata expansion.
- `expand_node_many_children`: deterministic hierarchy path expansion.
- `first_table_page`: deterministic first-page table generation.
- `table_scroll`: deterministic mid-table page slicing.
- `slice_2d`: deterministic 2D plane generation.
- `nifti_plane`: deterministic volume-plane proxy generation.
- `cancellation_latency`: cooperative cancellation token latency.
- `repeated_open_close_memory_growth`: repeated synthetic open/close allocation delta.
- `gzip_extraction`: deterministic gzip decompress probe.
- `plugin_chunk_throughput`: deterministic chunked table reduction.

The Phase 0 probes are intentionally stable and cheap enough for frequent local runs. Later packaged smoke and stress tasks should add artifact-level probes against real HDF5, CSV, NIfTI, gzip, workspace, and plugin fixtures. Thresholds must cite the Windows and Linux baseline reports used to set them.
