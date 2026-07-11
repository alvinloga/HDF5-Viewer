# Data Viewer Verification Ledger

## Purpose

This file records commands actually run against specific repository states. It must not predict future results. Update it after meaningful baseline, checkpoint, and release verification.

## Legacy baseline — 2026-07-11

Environment: Windows workspace, active Python environment available to Codex. This baseline describes the legacy HDF5 Viewer code before Data Viewer implementation.

| Check | Command | Observed result | Meaning |
|---|---|---|---|
| Python compilation | `python -m compileall -q core gui plugins services utils main.py` | passed | Python files parsed; runtime behavior unproven |
| Core tests | `python -m pytest tests/test_core.py -q` | 5 passed | narrow core subset only |
| Full collection | `python -m pytest --collect-only -q` | interrupted by 4 GUI import/collection errors | active environment lacks a complete working PyQt6 test setup; full suite status unknown |
| Static definitions | repository scan | 128 test functions/methods found | not equivalent to collected or passing tests |

Known evidence problems:

- legacy documentation claimed 121 passing tests and 100% pass rate without reproducible current evidence;
- `.github/workflows/build.yml` builds artifacts but does not run the full test suite before release;
- runtime/build naming and version sources disagree (`HDF5Viewer`, About version, and git tags);
- unconstrained `requirements.txt` lacks target format dependencies;
- test isolation from repository/user configuration is unproven.

## Documentation architecture pass — 2026-07-11

Scope: product, architecture, API, format, editing, plugin, workspace, UI, testing, dependency, migration, ADR, and execution-plan documentation. No product behavior is claimed implemented by this pass.

Verification run in the workspace on 2026-07-11:

| Check | Result |
|---|---|
| `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |
| required-document inventory | passed: 19 required root/docs/tasks files exist |
| ADR inventory | passed: 9 accepted ADR files exist |
| executable task inventory | passed: 86 unique `DV-####` task IDs |
| local Markdown link scan | passed: every relative Markdown link resolves to an existing path |
| stale-claim scan | passed: remaining `121 tests` / `100% pass rate` matches are explicitly labeled historical and untrusted |

These checks validate documentation structure and consistency only. They do not validate product behavior.

## DV-0001 package skeleton — 2026-07-11

Revision: `c7852ab` (`chore: add installable Data Viewer package skeleton`).

| Check | Command | Observed result |
|---|---|---|
| Editable package install | `venv\Scripts\python.exe -m pip install -e ".[dev]"` | passed after installing a locally hash-verified PyQt6 wheel set into the project virtual environment |
| Package behavior | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 venv\Scripts\python.exe -m pytest tests/test_data_viewer_package.py -q` | 2 passed |
| Version source | `importlib.metadata.version("data-viewer") == data_viewer.__version__` | passed; both report `1.0.0.dev0` |
| Static checks | `venv\Scripts\ruff.exe check data_viewer tests/test_data_viewer_package.py`; `venv\Scripts\mypy.exe data_viewer` | passed |
| Wheel metadata | `PIP_NO_CACHE_DIR=1 venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation .` | passed; wheel metadata has the canonical version, Python constraint, runtime/dev/packaging groups |
| Legacy compilation | `venv\Scripts\python.exe -m compileall -q core gui plugins services utils main.py` | passed |

Known limits carried into DV-0002/DV-0003:

- this virtual environment temporarily inherits the pre-existing Conda base packages and is not a clean lock-validation environment;
- normal pytest autoload reaches `pytest-qt` but `PyQt6.QtCore` fails to load a Windows DLL in this environment;
- `python -m build` is shadowed by the legacy root `build.py`; metadata validation uses `pip wheel` until the legacy build entry is migrated.

DV-0001 is complete because its explicit package/metadata/install/version/legacy-compile acceptance checks pass. The known environment and collection failures remain release blockers and are not reported as passing tests.

## Checkpoint record format

For each checkpoint append:

```text
Revision:
Date / OS / Python:
Dependency lock hash:
Commands:
Results (pass/fail/skip with reasons):
Performance fixture and hardware:
Package artifact and checksum:
Known gaps:
```

## Release evidence requirements

Data Viewer v1 requires current-revision evidence for all gates in `docs/TESTING.md`: full collection, lint, type check, unit/integration/offscreen GUI, adapter conformance, safe-edit fault tests, plugin numerical tests, workspace tests, performance budgets, visual/accessibility review, and installed-artifact smoke tests on Windows and Linux.

No report may use “100%” unless it names the measured denominator and includes the artifact. A passing build is not a passing application.
