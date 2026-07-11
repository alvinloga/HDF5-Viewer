# Testing and Acceptance Strategy

## 1. Evidence policy

Documentation, release notes, and PRs may claim only results produced by commands recorded for the current revision and environment. Collected test count is not passed test count. Coverage percentage is not correctness and must include the exact command/config/report artifact.

Current legacy evidence is recorded in root `TEST_REPORT.md`. It is not the target release result.

## 2. Test layers

| Layer | Purpose | Required tools/marker |
|---|---|---|
| pure unit | domain values, selections, patches, schema, algorithms | pytest; no Qt/file dependency unless intrinsic |
| adapter conformance | common DataSource behavior for every format | shared fixtures and parametrized suite |
| format integration | library-specific edge cases and malformed files | generated/golden fixtures |
| service integration | controllers, tasks, cache, workspace, save transactions | real temp files; controlled executors |
| GUI component | models, states, focus, signals, accessibility | pytest-qt, offscreen |
| end-to-end | open/view/edit/save/export/restore/plugin workflows | packaged or development application |
| performance | latency, memory, cancellation, bounded loading | reproducible benchmark datasets |
| package smoke | clean-machine launch and representative opens | Windows and Linux release artifacts |

Tests follow the pyramid: most behavior below GUI, a focused GUI suite, and a small critical end-to-end suite.

## 3. Determinism and isolation

- Tests use `tmp_path`; they never write repository `config.json` or user application directories.
- Set `QT_QPA_PLATFORM=offscreen` for headless GUI tests unless a real display test is explicitly marked.
- Locale, timezone, random seed, theme, and numeric tolerances are explicit.
- Test order must not matter. Singleton registries/configuration have reset fixtures.
- Tests do not require network access.
- Generated fixtures are preferred; binary golden files are minimal, documented, and license-safe.
- Timeouts replace unbounded waits. Signal waits use pytest-qt primitives.
- No `QThread.terminate()` in product or tests.

## 4. Standard commands

Target project commands use the committed universal lock:

```bash
uv sync --locked --all-extras
uv run pytest --collect-only -q
uv run pytest -m "not gui and not performance" -q
uv run pytest -m gui -q
uv run pytest --cov=data_viewer --cov-report=term-missing --cov-report=xml
uv run ruff check .
uv run mypy data_viewer
uv run python -m compileall -q data_viewer
```

Until migration, legacy commands remain:

```bash
python -m pytest --collect-only -q
python -m pytest tests/test_core.py -q
python -m compileall -q core gui plugins services utils main.py
```

Phase 0 must make the full collection command succeed before feature work proceeds.

## 5. Required fixture families

Each supported format includes:

- smallest valid file;
- empty resource/file where valid;
- scalar, 1D, 2D, high-dimensional resource;
- strings/unicode/non-ASCII names;
- booleans, signed/unsigned integers, floats, complex values where supported;
- missing, NaN, infinity and sparse/structured values where supported;
- representative hierarchical/multi-resource file;
- malformed/truncated/unsupported-version file;
- oversized metadata or adversarial nesting/archive case;
- generic gzip wrapper and corrupt/truncated gzip;
- non-ASCII path and space-containing path.

Fixture factories record creation parameters. Do not commit multi-megabyte scientific data merely for convenience.

## 6. DataSource conformance

The shared suite from `docs/DATASOURCE_API.md` verifies:

1. bounded probe and correct adapter selection;
2. direct-child pagination and stable resource IDs;
3. metadata/payload separation;
4. normalized selection and original-coordinate mapping;
5. capability honesty;
6. task cancellation and stale-result rejection;
7. lifecycle close with no use-after-close;
8. structured errors;
9. no uncontrolled whole-file read;
10. Windows/Linux path behavior.

Adapter completion requires both shared conformance and format-specific tests from `docs/FORMAT_SUPPORT.md`.

## 7. Safe editing fault matrix

Inject a failure before/after each persistence step: temp creation, write, flush, reopen, validation, replace, directory sync, final reopen. At every point assert:

- original validity;
- temporary/recovery artifact state;
- dirty/change-set state;
- actionable error;
- retry/Save As behavior;
- no unintended coordinates changed.

Use property-based generation for supported dtype/shape/value combinations where practical. Windows locked destination and Linux permissions are platform-specific required tests.

## 8. Plugin testing

Every plugin passes the conformance suite in `docs/PLUGIN_API.md` plus numerical golden tests. Numerical tests specify:

- input dtype/shape and exact selection;
- missing/nonfinite policy;
- algorithm/reference formula;
- absolute/relative tolerance;
- full or sampled scope and seed;
- expected warnings and provenance.

Cancellation tests use sufficiently many chunks to prove cooperative interruption rather than racing a trivial completion.

## 9. Workspace testing

Use schema validation, golden round trips, moved/missing/changed source cases, degraded restoration, newer-version protection, and malicious-size/depth/path cases defined in `docs/WORKSPACE_FORMAT.md`. Round-trip comparison normalizes only timestamps/IDs that the test intentionally creates.

## 10. GUI acceptance

Automated GUI tests assert behavior, not fragile pixel coordinates:

- initial/loading/empty/ready/partial/error/disabled/dirty/read-only/conflicted/stale states;
- active tab/split context;
- keyboard navigation and shortcuts;
- no GUI-thread blocking for adapter/plugin/export tasks;
- visible progress/cancel/error details;
- close with dirty documents and active tasks;
- translation lookup and missing-string detection.

Deterministic visual snapshots supplement behavior tests for the matrix in `docs/UI_UX_SPEC.md`. Platform rendering differences use reviewed platform baselines, not a lax universal threshold.

## 11. Performance budgets

Phase 0 records hardware/OS/library versions and establishes numeric baselines. Release budgets must cover:

- cold application launch;
- opening large hierarchical metadata without recursive payload loading;
- expanding a node with many children;
- first table page and scroll latency;
- 2D slice and NIfTI plane navigation;
- cancellation latency;
- memory growth after repeated open/close;
- generic gzip extraction progress, disk budget, cancellation, and cleanup;
- plugin chunk throughput and peak memory.

Benchmarks use synthetic reproducible generators and report median plus high percentile. A regression threshold is encoded only after representative Windows/Linux baselines exist.

## 12. CI matrix and gates

Pull requests run:

- Windows latest, Python supported minimum and maximum;
- Ubuntu latest, Python supported minimum and maximum;
- lint, type check, compile, unit, adapter, integration, offscreen GUI;
- coverage artifact and JUnit report;
- dependency/lock consistency;
- documentation link/schema checks.

During migration, the lint/type gate is scoped to `data_viewer/` and the test-isolation/package harness that accompanies it; the legacy application remains protected by full compile and behavioral regression runs. The current 171-finding legacy Ruff baseline is tracked as migration debt, not hidden with global ignores. Each migrated module joins the strict lint/type scope in the same task that moves it into the target architecture.

Tag/release workflow additionally builds each platform artifact, installs/launches it in a clean runner, opens representative HDF5/CSV/NIfTI/workspace fixtures, captures diagnostics, and uploads checksums. Release creation depends on all tests and both package smoke jobs; build success alone is insufficient.

## 13. Definition of done for a task

A task is complete only when:

- acceptance criteria in `tasks/todo.md` pass;
- new/changed behavior has tests at the lowest useful layer;
- targeted tests and required wider suite pass;
- failure/cancellation/empty states are covered;
- public contract/docs are updated;
- no unrelated tests are weakened or deleted;
- commands and results are recorded in the PR/task note.

## 14. v1 release acceptance

All must pass on both Windows and Linux:

- every v1 format plus its `.gz` form opens representative data;
- editable formats complete safe edit, review, save, reopen, and unchanged-data verification;
- read-only formats block overwrite and offer explicit compatible exports;
- large-file workflows remain responsive and cancellable within established budgets;
- plugin numerical and visualization workflows preserve scope/provenance;
- workspace save/restore, relocation, degraded mode, and version protection work;
- UI matrix, keyboard, contrast, high DPI, localization, and diagnostics pass;
- packaged artifact launch/open/close smoke tests pass from a clean machine;
- documentation matches the shipped implementation and contains no future feature claims stated as present.
