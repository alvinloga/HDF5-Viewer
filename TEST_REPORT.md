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

## DV-0003 pytest collection and isolation pre-acceptance — 2026-07-11

Revision: `35d0a73` (`test: stabilize Qt collection and config isolation`).

| Check | Command | Observed result |
|---|---|---|
| Qt/config regression tests | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py -q` | 3 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 133 tests collected in 1.09 seconds; command exited 0 |
| Repository config integrity | SHA-256 before/after GUI config test | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |
| Full execution diagnostic | `venv\Scripts\python.exe -m pytest -q` | 132 passed, 1 skipped, 11 teardown errors |

The full-execution errors are Windows `PermissionError` failures while deleting temporary HDF5 files that remain open after GUI/tab operations. They are assigned to DV-0004 (close/ownership regression coverage), not suppressed. Test order randomization is not configured in the repository, so the required order/seed rerun is not applicable yet.

The successful local environment is a project virtual environment derived from the existing `hdf5viewer_build` Conda environment. It is sufficient for collection diagnosis but is not the clean lock-validation environment required by DV-0002. DV-0003 remains unchecked until the same collection gate passes from the locked environment.

## Legacy resource-cleanup follow-up — 2026-07-11

Revision: working tree following `158c55d` (`docs: record pytest isolation pre-acceptance`). This follow-up is baseline test isolation only; it does not change the target Data Viewer source-session architecture.

| Check | Command | Observed result |
|---|---|---|
| Focused Windows handle regressions | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py::test_registry_cleanup_releases_open_hdf5_sources tests/test_comprehensive.py::TestTabOperations::test_open_file tests/test_comprehensive.py::TestFileOperations::test_open_hdf5_file tests/test_comprehensive.py::TestDataNavigation::test_node_double_click -q` | 4 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 134 tests collected in 1.32 seconds; command exited 0 |
| Full execution | `venv\Scripts\python.exe -m pytest -q` | 133 passed, 1 skipped, 3 existing NaN/Inf `RuntimeWarning`s; command exited 0 |
| Test parsing | `venv\Scripts\python.exe -m compileall -q tests` | passed |
| Repository config integrity | SHA-256 after the full run | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |

The fix explicitly closes the legacy registry entry before each affected xUnit teardown deletes its temporary HDF5 fixture, while an autouse fixture resets cached data sources and the event bus between tests. This closes the prior Windows temporary-file-handle failure without weakening product assertions. Ruff is not present in this diagnostic virtual environment, so lint/type checks remain blocked on DV-0002's clean, locked dev environment.

## DV-0002 Windows locked-environment evidence — 2026-07-11

Revision: working tree with `uv.lock` generated by uv `0.11.28` from `pyproject.toml`; lock SHA-256: `F44C592658057904746D776129076715CDE998FB699A797E256F432FA2C07734`.

| Check | Command | Observed result |
|---|---|---|
| Lock agreement | `uv lock --check` | passed; 55 packages resolved without a lock change |
| Clean install | `uv sync --locked --all-extras --python 3.12` | passed in a new virtual environment using uv-managed CPython `3.12.13`; 54 packages installed including runtime, dev, and packaging extras |
| Direct dependency imports | `python -c "import PyQt6.QtCore, numpy, h5py, pandas, scipy, nibabel, openpyxl, yaml, matplotlib, jsonschema, platformdirs"` | passed; Qt reports `6.11.0` |
| Package entry point | `python -m data_viewer` | passed; emitted the expected development-shell message |
| Target static checks | `ruff check data_viewer tests/conftest.py tests/test_test_environment.py`; `mypy data_viewer` | passed |
| Package build | `uv build --no-sources` | source distribution and wheel built successfully after modernizing the SPDX license metadata; no Setuptools license deprecation warning |
| Collection | `python -m pytest --collect-only -q` | 134 tests collected in 9.79 seconds; command exited 0 |
| Full execution | `python -m pytest -q` | 133 passed, 1 skipped, 3 existing NaN/Inf `RuntimeWarning`s; command exited 0 |

The same lock installed under a virtual environment based on the local Conda Python, but `PyQt6.QtCore` then failed to load. Repeating the install with uv-managed standalone CPython passed all direct imports; the cause is the local Conda native-library search path, not an unresolved PyQt6 dependency. Clean Windows verification is therefore valid only with standalone CPython/uv-managed Python, never a Conda-derived environment.

This is Windows evidence only. `uv.lock` is universal and includes Linux markers/artifacts, but a fresh Linux install/import/CI run remains unverified and keeps DV-0002 unchecked. Public binary packaging also remains blocked pending the PyQt6 GPL/commercial licensing decision. A full-repository `ruff check .` baseline reports 171 existing findings across legacy build, application, plugin, service, and test files; the target subset above passes and the broader lint debt is not suppressed by this evidence.

## DV-0002 and DV-0003 completion evidence — 2026-07-11

Revision: `ab9ea7e` (`test: stabilize locale and timezone isolation`); lock SHA-256: `F44C592658057904746D776129076715CDE998FB699A797E256F432FA2C07734`.

The historical Windows-only entry above is superseded by [GitHub Actions run 29151025813](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29151025813), which passed the same locked gate on both platforms.

| Platform | CPython | Locked CI result |
|---|---:|---|
| Windows Server 2025 | 3.12.10 | `uv lock --check`, locked sync, direct imports, target lint/type, compile, 139-test collection, 138 passed / 1 skipped, and sdist/wheel build all passed |
| Ubuntu latest | 3.12.13 | the same locked install, import, static, collection, full offscreen GUI, and package-build gate passed |

The test fixture now fixes `TZ=UTC` and locale `C`, config writes are redirected to `tmp_path`, Qt is offscreen, and data-source/event-bus singletons reset per test. Static test definitions and collected tests are both 139; runtime execution is 138 passed and 1 intentionally skipped. `config.json` remains SHA-256 `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` after the local full run.

DV-0002 and DV-0003 are complete. The public binary release remains blocked by the unresolved PyQt6 GPL/commercial distribution decision and all later v1 acceptance tasks. DV-0005 remains open because artifact-report upload, release dependency enforcement, and its deliberate-failure verification are not complete.

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
