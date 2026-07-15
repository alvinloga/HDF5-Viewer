# Data Viewer Verification Ledger

## Purpose

This file records commands actually run against specific repository states. It must not predict future results. Update it after meaningful baseline, checkpoint, and release verification.

## Legacy baseline 閳?2026-07-11

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
- legacy/historical runtime/build naming and version sources disagree (`HDF5Viewer`, About version, and git tags);
- unconstrained `requirements.txt` lacks target format dependencies;
- test isolation from repository/user configuration is unproven.

## Documentation architecture pass 閳?2026-07-11

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

## DV-0001 package skeleton 閳?2026-07-11

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

## DV-0003 pytest collection and isolation pre-acceptance 閳?2026-07-11

Revision: `35d0a73` (`test: stabilize Qt collection and config isolation`).

| Check | Command | Observed result |
|---|---|---|
| Qt/config regression tests | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py -q` | 3 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 133 tests collected in 1.09 seconds; command exited 0 |
| Repository config integrity | SHA-256 before/after GUI config test | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |
| Full execution diagnostic | `venv\Scripts\python.exe -m pytest -q` | 132 passed, 1 skipped, 11 teardown errors |

The full-execution errors are Windows `PermissionError` failures while deleting temporary HDF5 files that remain open after GUI/tab operations. They are assigned to DV-0004 (close/ownership regression coverage), not suppressed. Test order randomization is not configured in the repository, so the required order/seed rerun is not applicable yet.

The successful local environment is a project virtual environment derived from the existing legacy `hdf5viewer_build` Conda environment. It is sufficient for collection diagnosis but is not the clean lock-validation environment required by DV-0002. DV-0003 remains unchecked until the same collection gate passes from the locked environment.

## Legacy resource-cleanup follow-up 閳?2026-07-11

Revision: working tree following `158c55d` (`docs: record pytest isolation pre-acceptance`). This follow-up is baseline test isolation only; it does not change the target Data Viewer source-session architecture.

| Check | Command | Observed result |
|---|---|---|
| Focused Windows handle regressions | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py::test_registry_cleanup_releases_open_hdf5_sources tests/test_comprehensive.py::TestTabOperations::test_open_file tests/test_comprehensive.py::TestFileOperations::test_open_hdf5_file tests/test_comprehensive.py::TestDataNavigation::test_node_double_click -q` | 4 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 134 tests collected in 1.32 seconds; command exited 0 |
| Full execution | `venv\Scripts\python.exe -m pytest -q` | 133 passed, 1 skipped, 3 existing NaN/Inf `RuntimeWarning`s; command exited 0 |
| Test parsing | `venv\Scripts\python.exe -m compileall -q tests` | passed |
| Repository config integrity | SHA-256 after the full run | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |

The fix explicitly closes the legacy registry entry before each affected xUnit teardown deletes its temporary HDF5 fixture, while an autouse fixture resets cached data sources and the event bus between tests. This closes the prior Windows temporary-file-handle failure without weakening product assertions. Ruff is not present in this diagnostic virtual environment, so lint/type checks remain blocked on DV-0002's clean, locked dev environment.

## DV-0002 Windows locked-environment evidence 閳?2026-07-11

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

## DV-0002 and DV-0003 completion evidence 閳?2026-07-11

Revision: `ab9ea7e` (`test: stabilize locale and timezone isolation`); lock SHA-256: `F44C592658057904746D776129076715CDE998FB699A797E256F432FA2C07734`.

The historical Windows-only entry above is superseded by [GitHub Actions run 29151025813](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29151025813), which passed the same locked gate on both platforms.

| Platform | CPython | Locked CI result |
|---|---:|---|
| Windows Server 2025 | 3.12.10 | `uv lock --check`, locked sync, direct imports, target lint/type, compile, 139-test collection, 138 passed / 1 skipped, and sdist/wheel build all passed |
| Ubuntu latest | 3.12.13 | the same locked install, import, static, collection, full offscreen GUI, and package-build gate passed |

The test fixture now fixes `TZ=UTC` and locale `C`, config writes are redirected to `tmp_path`, Qt is offscreen, and data-source/event-bus singletons reset per test. Static test definitions and collected tests are both 139; runtime execution is 138 passed and 1 intentionally skipped. `config.json` remains SHA-256 `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` after the local full run.

DV-0002 and DV-0003 are complete. The public binary release remains blocked by the unresolved PyQt6 GPL/commercial distribution decision and all later v1 acceptance tasks. DV-0005 remains open because artifact-report upload, release dependency enforcement, and its deliberate-failure verification are not complete.

## DV-0004 legacy-test consolidation and deterministic fixtures 閳?2026-07-11

Revision: `d7ab9f5` (`test: add deterministic fixture factories`).

| Check | Command | Observed result |
|---|---|---|
| Exact-duplicate audit | AST-normalized body SHA-256 scan across `tests/test_*.py` | passed; the only exact duplicate was `tests/test_packaged.py::test_event_bus`, whose event registration, emitted value, deregistration, and two assertions exactly matched the retained `tests/test_all_features.py::test_event_bus` coverage |
| Fixture conformance | `python -m pytest tests/test_fixture_factories.py tests/test_all_features.py tests/test_packaged.py -q` | 16 passed; generated HDF5 reopens with hierarchy/attributes, NPY round-trips without pickle, and CSV bytes/rows are deterministic |
| Fixture quality | `python -m ruff check tests/fixtures tests/test_fixture_factories.py`; `python -m compileall -q tests/fixtures tests/test_fixture_factories.py` | passed |
| Local collection | `python -m pytest --collect-only -q` | 141 tests collected; command exited 0 |
| Local full execution | `python -m pytest -q` | 140 passed, 1 skipped, 3 pre-existing NumPy NaN/Inf warnings; command exited 0 |
| Windows CI | [GitHub Actions run 29151383533](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29151383533) | CPython 3.12.10: locked install, direct imports, target lint/type, compile, 141-test collection, 140 passed / 1 skipped, and sdist/wheel build all passed |
| Ubuntu CI | [GitHub Actions run 29151383533](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29151383533) | CPython 3.12.13: the same locked gate passed; 141-test collection and 140 passed / 1 skipped |

The reusable factories in `tests/fixtures/` generate only tiny test-owned HDF5, NPY, and UTF-8 CSV files and return immutable creation metadata. No opaque binary fixture was added. Similar-looking legacy tests remain because the AST audit found different executable bodies or assertions; only the proven duplicate was removed. The three NumPy warnings exercise intentional NaN/Inf input and remain visible rather than being suppressed.

## DV-0005 quality CI and release-gate evidence - 2026-07-13

Revision: `d045ae4` (`Revert "test: verify release gate blocks failed quality"`), after temporary failure commit `3f667e6` was reverted. Lock SHA-256 after LF normalization: `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`.

Implementation evidence:

- `.github/workflows/ci.yml` runs Windows and Ubuntu quality jobs with locked install, direct dependency smoke, scoped Ruff, scoped mypy, compile, collection, full offscreen pytest, sdist/wheel build, and always-uploaded quality evidence.
- `.github/workflows/build.yml` is a manual release gate that depends on the reusable quality workflow and remains intentionally blocked until packaged smoke tests and PyQt licensing are complete.
- `.github/scripts/write_quality_manifest.py` records secret-free CI metadata and hashes `uv.lock` after normalizing checkout line endings. `.gitattributes` pins `uv.lock` to LF for cross-platform consistency.

Local verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Regression proof before fix | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_ci_reporting.py -q` | failed as expected before the script fix: raw-byte lock hashes differed for LF and CRLF fixtures |
| CI reporting contract | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_ci_reporting.py -q` | 4 passed |
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_fixture_factories.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 4 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Target and legacy compile | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 145 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 144 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Final successful CI evidence: [GitHub Actions run 29230119484](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29230119484), revision `d045ae4c83eb81e90316387b92603747bca04a27`.

| Platform | Result |
|---|---|
| Windows | locked install, direct imports, scoped lint/type, compile, 145-test collection, 144 passed / 1 skipped, sdist/wheel build, and quality evidence upload all passed |
| Ubuntu | locked install, direct imports, scoped lint/type, compile, 145-test collection, 144 passed / 1 skipped, sdist/wheel build, and quality evidence upload all passed |

Downloaded artifact verification from run `29230119484`:

| Artifact | Manifest result | JUnit result | Package outputs |
|---|---|---|---|
| `data-viewer-quality-Windows-29230119484-1` | `git_sha=d045ae4c83eb81e90316387b92603747bca04a27`; `uv_lock_sha256=f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; matches local normalized hash | 145 tests, 0 failures, 0 errors, 1 skipped | `data_viewer-1.0.0.dev0.tar.gz`; `data_viewer-1.0.0.dev0-py3-none-any.whl` |
| `data-viewer-quality-Ubuntu-29230119484-1` | same commit and lock hash; matches local normalized hash | 145 tests, 0 failures, 0 errors, 1 skipped | `data_viewer-1.0.0.dev0.tar.gz`; `data_viewer-1.0.0.dev0-py3-none-any.whl` |

Deliberate failure verification:

| Run | Commit | Observed result |
|---|---|---|
| [Quality run 29229961154](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29229961154) | temporary commit `3f667e6` (`test: verify release gate blocks failed quality`) | Windows and Ubuntu both failed at `Run full offscreen regression suite`; each skipped `Build source distribution and wheel`; each still uploaded quality evidence |
| [Release gate run 29229983175](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29229983175) | same temporary failure commit | reusable `quality / Windows quality` and `quality / Ubuntu quality` failed; downstream `blocked` job was skipped, proving release jobs cannot run past failed quality |
| Revert commit | `d045ae4` | removed the intentional failing test with `git revert`; final run `29230119484` returned the branch to green |

DV-0005 is complete. The separate consolidated Checkpoint 0 record follows in the next section.

## Checkpoint 0 trustworthy-baseline evidence - 2026-07-13

Revision: `58756db` (`docs: record quality gate evidence`). Lock SHA-256 after LF normalization: `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`.

Scope covered: DV-0001 through DV-0005 are complete. This checkpoint proves the reproducible baseline, package skeleton, dependency lock, pytest isolation, deterministic fixture factories, and dual-platform quality/release gate. It does not claim any P1+ Data Viewer product feature is implemented.

Local Windows verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_fixture_factories.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 4 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Compile target and legacy compatibility paths | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 145 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 144 passed, 1 skipped, 3 NumPy NaN/Inf warnings from intentional edge-case tests |

Dual-platform CI evidence: [GitHub Actions run 29230437164](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29230437164), revision `58756dbb198d06fc022ec0ae3e00ce16d75c4deb`.

| Platform | CI result | Artifact verification |
|---|---|---|
| Windows | locked install, direct dependency import smoke, scoped lint/type, compile, 145-test collection, 144 passed / 1 skipped, sdist/wheel build, and quality evidence upload all passed | artifact `data-viewer-quality-Windows-29230437164-1`; manifest commit `58756dbb198d06fc022ec0ae3e00ce16d75c4deb`; lock hash matches local normalized hash; JUnit has 145 tests, 0 failures, 0 errors, 1 skipped |
| Ubuntu | the same quality gate passed | artifact `data-viewer-quality-Ubuntu-29230437164-1`; manifest commit `58756dbb198d06fc022ec0ae3e00ce16d75c4deb`; lock hash matches local normalized hash; JUnit has 145 tests, 0 failures, 0 errors, 1 skipped |

Known baseline gaps and owners:

| Gap | Status / owner task |
|---|---|
| `tests.test_comprehensive.TestTabOperations::test_detach_tab` is skipped because `TabManager._detach_tab` is not implemented | legacy limitation; target split/tab behavior is owned by P6 UI tasks, especially DV-0603 |
| Public binary release remains blocked by packaged smoke tests, SBOM/license evidence, and PyQt6 distribution decision | owned by P10/P11 release tasks, especially DV-1005 through DV-1104 |
| Target Data Viewer source adapters, plugin runtime, safe editing, workspace, comparison, performance, and packaging are not implemented by Checkpoint 0 | owned by P1 through P11 tasks in `tasks/todo.md` |
| Full-repository legacy Ruff debt is not eliminated | tracked as migration debt in `docs/TESTING.md` section 12; migrated modules join strict scope task-by-task |

Checkpoint 0 is complete. The next executable task is DV-0101, which begins P1 domain and runtime kernel work.

## DV-0101 immutable domain values - 2026-07-13

Revision: `6f99d0a` (`feat: add immutable domain resource metadata types`). Scope: `data_viewer/domain/resources.py`, `data_viewer/domain/capabilities.py`, `data_viewer/domain/metadata.py`, public exports, CI lint scope, and focused domain tests.

Implemented public values:

- `ResourceId` with canonical file URI factory, absolute normalized node paths, stable equality/hash, and explicit JSON round trip;
- `SourceFingerprint` and `ResourceNode` value types;
- `DataDomain`, `NodeKind`, and `SourceCapability` with stable serialized names;
- `FrozenJsonMapping`, `ColumnSpec`, `SpatialMetadata`, and `DataMetadata` with immutable JSON-compatible metadata and explicit serialization.

Local Windows verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Red test | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_domain_types.py -q` before implementation | failed during collection with `ModuleNotFoundError: No module named 'data_viewer.domain'` |
| Domain and CI reporting tests | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_domain_types.py tests/test_ci_reporting.py -q` | 14 passed |
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_domain_types.py tests/test_fixture_factories.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 8 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Compile target and legacy compatibility paths | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py tests/test_domain_types.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 155 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 154 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Known limits at revision `6f99d0a`: selections, payload values, structured errors, task state, and adapter/session protocols remained unimplemented and were owned by DV-0102 through DV-0105.

## DV-0102 normalized selections and payload values - 2026-07-13

Revision: `8f54af6` (`feat: add normalized selection payload values`). Scope: `data_viewer/domain/selection.py`, `data_viewer/domain/payload.py`, public exports, DataSource API clarification, CI lint scope, and focused selection/payload tests.

Implemented public values:

- `AxisSelection`, `SelectionSpec`, `NormalizedSelection`, and `NormalizedAxisSelection` for all/index/slice/hyperslab selections with original-coordinate mapping;
- `SelectionValidationError` and `SelectionValidationResult` for structured shape/page-specific validation failures;
- `TablePageSelection` and `NormalizedTablePage` for row paging, negative-offset normalization, total-row clipping, and selected columns;
- `ArrayPayload`, `TablePayload`, `TextPayload`, `StructuredPayload`, `VolumePayload`, `OperationScope`, `SampleSpec`, and `ReadResult`.

Local Windows verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Red test | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_selection_payload_types.py -q` before implementation | failed during collection with `ImportError: cannot import name 'ArrayPayload' from 'data_viewer.domain'` |
| Selection/payload, domain, and CI reporting tests | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_selection_payload_types.py tests/test_domain_types.py tests/test_ci_reporting.py -q` | 26 passed |
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_domain_types.py tests/test_fixture_factories.py tests/test_selection_payload_types.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 10 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Compile target and legacy compatibility paths | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py tests/test_selection_payload_types.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 167 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 166 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Known limits at revision `8f54af6`: structured error taxonomy, task state, adapter/session protocols, DocumentController ownership, and platform/cache/config primitives remained unimplemented and were owned by DV-0103 through DV-0107.

## DV-0103 structured errors and diagnostics values - 2026-07-13

Revision: `b48d476` (`feat: add structured error diagnostics values`). Scope: `data_viewer/domain/errors.py`, `data_viewer/app/diagnostics.py`, public exports, DataSource API clarification, CI lint scope, and focused error/diagnostics tests.

Implemented public values:

- `ErrorCode`, `ErrorCategory`, `ErrorSeverity`, `ErrorTargetKind`, `ErrorTarget`, and `ErrorCodeSpec` with stable mappings for source, plugin, task, workspace, editing, config, and internal errors;
- `DataViewerError` with safe user message, operation, resource/target, retryability, remediation, JSON-compatible details, cause ID, JSON serialization, and diagnostic log record conversion;
- `UserErrorMessage` for traceback-free UI routing;
- `DiagnosticsRedactor`, `DiagnosticEvent`, and `DiagnosticsSnapshot` for path-redacted diagnostic exports without raw tracebacks.

Local Windows verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Red test | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_error_diagnostics.py -q` before implementation | failed during collection with `ModuleNotFoundError: No module named 'data_viewer.app'` |
| Error/diagnostics, selection/payload, domain, and CI reporting tests | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_error_diagnostics.py tests/test_selection_payload_types.py tests/test_domain_types.py tests/test_ci_reporting.py -q` | 36 passed |
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_domain_types.py tests/test_error_diagnostics.py tests/test_fixture_factories.py tests/test_selection_payload_types.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 13 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Compile target and legacy compatibility paths | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py tests/test_error_diagnostics.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 177 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 176 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Known limits at revision `b48d476`: task state, adapter/session protocols, DocumentController ownership, and platform/cache/config primitives remained unimplemented and were owned by DV-0104 through DV-0107.

## DV-0104 cooperative task lifecycle primitives - 2026-07-13

Revision: `268f6fd` (`feat: add cooperative task lifecycle primitives`). Scope: `data_viewer/tasks/state.py`, `data_viewer/tasks/cancellation.py`, `data_viewer/tasks/dispatcher.py`, public task exports, CI lint scope, and focused task lifecycle tests.

Implemented public values:

- `TaskState`, `TaskProgress`, `TaskSnapshot`, `TaskRecord`, and `TaskTransitionError` with legal queued/running/cancelling/terminal transitions;
- `CancellationToken` with cooperative cancellation and `DataViewerError(TASK_CANCELLED)` checkpoints;
- `CallbackDispatcher` for injectable callback marshalling without importing Qt;
- immutable snapshots with owner/request-generation matching for later stale-result rejection.

Local Windows verification on Windows 11 `10.0.22621`, CPython `3.12.13` from `venv\lock-verify-cpython`:

| Check | Command | Observed result |
|---|---|---|
| Red test | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_task_lifecycle.py -q` before implementation | failed during collection with `ModuleNotFoundError: No module named 'data_viewer.tasks'` |
| Task lifecycle, error/diagnostics, selection/payload, domain, and CI reporting tests | `venv\lock-verify-cpython\Scripts\python.exe -m pytest tests/test_task_lifecycle.py tests/test_error_diagnostics.py tests/test_selection_payload_types.py tests/test_domain_types.py tests/test_ci_reporting.py -q` | 42 passed |
| Scoped lint | `venv\lock-verify-cpython\Scripts\ruff.exe check data_viewer .github/scripts tests/conftest.py tests/fixtures tests/test_ci_reporting.py tests/test_data_viewer_package.py tests/test_domain_types.py tests/test_error_diagnostics.py tests/test_fixture_factories.py tests/test_selection_payload_types.py tests/test_task_lifecycle.py tests/test_test_environment.py` | passed |
| Scoped type check | `venv\lock-verify-cpython\Scripts\mypy.exe data_viewer .github/scripts/write_quality_manifest.py` | passed; no issues in 17 source files |
| Workflow syntax | `C:\tmp\actionlint-1.7.12\extracted\actionlint.exe .github\workflows\ci.yml .github\workflows\build.yml` | passed |
| Compile target and legacy compatibility paths | `venv\lock-verify-cpython\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py tests/test_task_lifecycle.py` | passed |
| Full collection | `venv\lock-verify-cpython\Scripts\python.exe -m pytest --collect-only -q` | 183 tests collected |
| Full execution | `venv\lock-verify-cpython\Scripts\python.exe -m pytest -q` | 182 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Known limits: SourceAdapter/Session registry, DocumentController ownership, and platform/cache/config primitives remain unimplemented and are owned by DV-0105 through DV-0107.

## DV-0105 SourceAdapter registry and conformance harness - 2026-07-13

Revision: `49a034d` (`feat: add source adapter registry contract`). Scope: `data_viewer/sources/api.py`, `data_viewer/sources/registry.py`, public source exports, reusable fake adapter conformance helpers, CI lint scope, and focused source registry tests.

Implemented public values and behavior:

- `ReadRequest`, `ProbeResult`, `NodePage`, `SourceAdapter`, and `SourceSession` for DataSource API v1;
- `SourceRegistry` with bounded header reads, deterministic probe ordering, unsupported-source diagnostics, ambiguous top-confidence diagnostics, duplicate adapter-ID/extension diagnostics, and API-version validation;
- `ManagedSourceSession` with close idempotence and method-level `SOURCE_CLOSED` enforcement after close;
- reusable fake adapter conformance coverage for metadata/list/read/cancel/error/close behavior without exposing raw format-library objects.

Local Windows verification using the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Red test | `python -m pytest tests/test_source_registry.py tests/test_ci_reporting.py -q` before implementation | failed during collection with `ModuleNotFoundError: No module named 'data_viewer.sources'` |
| Source registry and CI reporting tests | `venv\Scripts\python.exe -m pytest tests/test_source_registry.py tests/test_ci_reporting.py -q` | 10 passed |
| P1 focused regression subset | `venv\Scripts\python.exe -m pytest tests/test_domain_types.py tests/test_error_diagnostics.py tests/test_task_lifecycle.py tests/test_source_registry.py tests/test_ci_reporting.py -q` | 36 passed |
| Compile target and conformance paths | `venv\Scripts\python.exe -m compileall -q data_viewer .github/scripts core gui plugins services utils main.py tests/conformance tests/test_source_registry.py` | passed |

Local limitations for this workstation environment:

- `uv` is not on the current PowerShell PATH;
- `.venv` exists but does not contain pytest;
- repository `venv` contains pytest and PyQt6 but lacks `hypothesis`, `ruff`, and `mypy`, so local full collection, full execution, lint, and type checks were deferred to the locked GitHub Actions matrix for the final DV-0105 revision.

Final CI evidence: [GitHub Actions run 29238330052](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29238330052), revision `41ef91dd1c3801d6efda719660a28465513f9a0a` (`docs: record source registry evidence`).

| Platform | CI result | Artifact verification |
|---|---|---|
| Windows | locked install, direct dependency import smoke, scoped lint/type, compile, 189-test collection, 188 passed / 1 skipped, sdist/wheel build, and quality evidence upload all passed | artifact `data-viewer-quality-Windows-29238330052-1`; manifest commit `41ef91dd1c3801d6efda719660a28465513f9a0a`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit has 189 tests, 0 failures, 0 errors, 1 skipped |
| Ubuntu | the same quality gate passed | artifact `data-viewer-quality-Ubuntu-29238330052-1`; manifest commit `41ef91dd1c3801d6efda719660a28465513f9a0a`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit has 189 tests, 0 failures, 0 errors, 1 skipped |

Known limits: DocumentController source-session ownership, source close waiting on explicit I/O leases, and platform/cache/config primitives remain unimplemented and are owned by DV-0106 and DV-0107.

## DV-0106 DocumentController ownership and request versioning - 2026-07-14

Revision: `bd49e88` (`fix: drop unused ReadRequest import in document controller test`) (implementation baseline is `609c373`).
Scope: `data_viewer/app/documents.py`, `data_viewer/app/active_context.py`, `data_viewer/app/__init__.py`, `data_viewer/sources/...` contract touchpoints, `tests/test_document_controller.py`, `tests/test_ci_reporting.py`, `.github/workflows/ci.yml`.

Implemented behavior:

- `DocumentController` owns one active source session and owns clean close semantics while waiting for active I/O tasks to finish;
- resource identity and request generation remain stable per document context; navigation returns incremented request generations that reject stale results;
- controller dirty flags and active-task hooks are emitted from controller context without direct GUI coupling;
- stale tasks are isolated from GUI widgets through `ActiveContext`, and public cancellation/close transitions are reflected via structured snapshots.

Local Windows verification on this workspace (not CI-locked Python):

| Check | Command | Observed result |
|---|---|---|
| DocumentController focused regression suite | `python -m pytest tests/test_document_controller.py -q` | failed during collection in this workspace: `ModuleNotFoundError: No module named 'PyQt6.QtWidgets'` from legacy GUI fixture |
| CI reporting contract test subset | `python -m pytest tests/test_ci_reporting.py -k document -q` | deselected due file selection |

Dual-platform CI evidence: [GitHub Actions run 29311841031](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29311841031), head `bd49e88`.

| Platform | CI result |
|---|---|
| Windows | passed (quality lane, full offscreen regression suite, and quality artifact upload) |
| Ubuntu | passed (quality lane, full offscreen regression suite, and quality artifact upload) |

Known limits remain: request-generation and lifecycle primitives are implemented for documents; platform/cache/config primitives are still owned by DV-0107.

## DV-0107 platform paths, cache, config, and logging primitives - 2026-07-14

Revision: `6e58508` (`fix: harden infra typed parsing and formatter init`).

| Check | Command | Observed result |
|---|---|---|
| Compilation/syntax check | `python -m compileall -q data_viewer/infrastructure tests/test_infrastructure_paths.py tests/test_infrastructure_config.py tests/test_infrastructure_cache.py tests/test_infrastructure_logging.py` | passed |
| Targeted infrastructure script checks | `.venv\\Scripts\\python.exe -c` inline smoke checks for path resolution, config load/save/recover, bounded cache put/get/evict/expire/persist, and redacted logging output | passed |
| Targeted pytest for infrastructure tests | `.venv\\Scripts\\python.exe -m pytest tests/test_infrastructure_cache.py tests/test_infrastructure_config.py tests/test_infrastructure_logging.py tests/test_infrastructure_paths.py -q` | 13 passed |
| Scope lint/type checks | `.venv\\Scripts\\ruff.exe check data_viewer tests/test_infrastructure_cache.py tests/test_infrastructure_config.py tests/test_infrastructure_logging.py tests/test_infrastructure_paths.py`; `.venv\\Scripts\\mypy.exe data_viewer/infrastructure tests/test_infrastructure_cache.py tests/test_infrastructure_config.py tests/test_infrastructure_logging.py tests/test_infrastructure_paths.py` | passed |
| Full collection | `.venv\\Scripts\\python.exe -m pytest --collect-only -q` | 208 tests collected |
| Full execution | `.venv\\Scripts\\python.exe -m pytest -q` | 207 passed, 1 skipped |
| Documentation/task ledger updates | `tasks/todo.md`, `CHANGELOG.md`, `TEST_REPORT.md` | updated |

Known gaps:

- This workspace still reports three NumPy NaN/Inf warnings from `test_edge_cases.py::test_nan_inf_data` (intentionally preserved for coverage).
- `save_config` merge utility currently serializes `AppConfig` as v1 without unknown-key passthrough in this pass.

## DV-0108 checkpoint 1 kernel evidence - 2026-07-14

Revision: `5678bc9` (`test: refresh DV-0107 verification evidence with full local run`)

| Check | Command | Observed result |
|---|---|---|
| Focused kernel/ownership slice | `.venv\\Scripts\\python.exe -m pytest tests/test_document_controller.py tests/test_source_registry.py tests/test_task_lifecycle.py tests/test_integration.py -q` | 24 passed |
| Compile | `.venv\\Scripts\\python.exe -m compileall -q data_viewer tests` | passed |
| Lint | `.venv\\Scripts\\ruff.exe check data_viewer tests/test_infrastructure_cache.py tests/test_infrastructure_config.py tests/test_infrastructure_logging.py tests/test_infrastructure_paths.py tests/test_document_controller.py tests/test_source_registry.py tests/test_task_lifecycle.py tests/test_integration.py` | passed |
| Type check | `.venv\\Scripts\\mypy.exe data_viewer tests/test_infrastructure_cache.py tests/test_infrastructure_config.py tests/test_infrastructure_logging.py tests/test_infrastructure_paths.py tests/test_document_controller.py tests/test_source_registry.py tests/test_task_lifecycle.py tests/test_integration.py` | passed |
| Full collection | `.venv\\Scripts\\python.exe -m pytest --collect-only -q` | 208 tests collected |
| Full execution | `.venv\\Scripts\\python.exe -m pytest -q` | 207 passed, 1 skipped |

Known gaps:

- This checkpoint is based on local Windows `CPython 3.12` in `.venv`; Linux parity evidence is still pending in CI before release gating.

## DV-0202 lazy HDF5 hierarchy and metadata - 2026-07-14

Revision: working tree for `data_viewer/sources/hdf5/session.py` and `tests/test_hdf5_adapter.py` updates.

| Check | Command | Observed result |
|---|---|---|
| Focused HDF5 regression suite | `.venv\\Scripts\\python.exe -m pytest tests/test_hdf5_adapter.py -k "hdf5_"` | 13 passed |
| Focused full HDF5 adapter suite | `.venv\\Scripts\\python.exe -m pytest tests/test_hdf5_adapter.py` | 13 passed |

Known gaps:

- Linux verification for this task is not yet run locally.

## DV-0203 direct bounded HDF5 reads - 2026-07-14

Revision: `071f09d`

| Check | Command | Observed result |
|---|---|---|
| Windows verification environment | `.venv\\Scripts\\python.exe --version` | CPython 3.12 (uv-managed virtual environment) |
| HDF5 adapter focused suite | `.venv\\Scripts\\python.exe -m pytest tests/test_hdf5_adapter.py -q` | 18 passed |
| Scoped lint | `.venv\\Scripts\\ruff.exe check data_viewer/sources/hdf5/session.py tests/test_hdf5_adapter.py` | passed |
| Full suite (local evidence) | `.venv\\Scripts\\python.exe -m pytest -q` | 225 passed, 1 skipped |

Notes:

- Added direct bounded selection test coverage for scalar, empty, 1D, 2D, high-dimensional, compound, string, complex, and boolean values.
- Added a selection-key spy assertion proving one dataset indexing call with the normalized key equivalent.
- Existing CI environment cannot import legacy Qt in plain Anaconda Python; all task evidence here is from repository `.venv` where PyQt6 imports are available.

## DV-0204 minimal target Qt bootstrap and shell - 2026-07-14

Revision: `eeed173682c9e46b0e1b378820028c5bb5dfec21`

Environment: Windows 11, `Python 3.12.13` from `.venv` (`uv`-managed CPython), Qt offscreen.

| Check | Command | Observed result |
|---|---|---|
| Lint | `.venv\\Scripts\\ruff.exe check data_viewer/__main__.py data_viewer/gui/app.py data_viewer/gui/shell.py data_viewer/gui/commands.py tests/test_data_viewer_package.py tests/test_gui_shell.py` | passed |
| Type check (targeted, import boundaries) | `.venv\\Scripts\\mypy.exe --follow-imports=skip data_viewer/__main__.py data_viewer/gui/app.py data_viewer/gui/commands.py data_viewer/gui/shell.py` | no issues found |
| Targeted CLI bootstrap tests | `.venv\\Scripts\\python.exe -m pytest tests/test_data_viewer_package.py -q` | 4 passed |
| Targeted shell GUI tests | `.venv\\Scripts\\python.exe -m pytest tests/test_gui_shell.py -q` | 4 passed |
| Combined target suite | `.venv\\Scripts\\python.exe -m pytest tests/test_data_viewer_package.py tests/test_gui_shell.py -q` | 8 passed |
| Target app command contract | `.venv\\Scripts\\python.exe -m data_viewer --version` | `Data Viewer 1.0.0.dev0` |
| Full regression suite (targeted scope) | `.venv\\Scripts\\python.exe -m pytest -q` | 231 passed, 1 skipped |
| Syntax check | `.venv\\Scripts\\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- Linux verification for this task remains to be completed in CI cross-platform run.
- This task does not add read/write format coverage beyond the minimal bootstrap shell.

## DV-0205 HDF5 vertical views and active workspace metadata sync - 2026-07-14

Revision: commit `f26a11a` on branch `codex/data-viewer-foundation`.

| Check | Command | Observed result |
|---|---|---|
| Focused shell navigation/tests | `.venv\\Scripts\\python.exe -m pytest tests/test_gui_shell.py -q` | 8 passed |
| Full suite verification | `.venv\\Scripts\\python.exe -m pytest -q` | 235 passed, 1 skipped |

Notes:

- Added status label object names for structured bottom/status assertions.
- Added coverage for lazy hierarchy expansion/load-more, workspace path/shape/dtype/slice synchronization on enter-open, and status-driven row-limit pagination behavior.
- Kept existing metadata/array behavior intact in `_open_resource_in_workspace` while aligning status updates with `metadata` + `read` flow.

Known gaps:

- Linux verification is still pending for this task in CI before DV-0206 evidence can be marked complete.

## DV-0206 Record Checkpoint 2 HDF5 vertical evidence - 2026-07-14

Revision: working tree for `tests/test_gui_shell.py`.

| Check | Command | Observed result |
|---|---|---|
| HDF5 adapter conformance | `.venv\Scripts\python.exe -m pytest tests/test_hdf5_adapter.py -q` | 18 passed |
| Targeted shell evidence tests | `.venv\Scripts\python.exe -m pytest tests/test_gui_shell.py -q` | 10 passed |
| Full suite verification | `.venv\Scripts\python.exe -m pytest -q` | 237 passed, 1 skipped |
| Lint gate for target file | `.venv\Scripts\ruff.exe check tests/test_gui_shell.py` | passed |

Notes:

- Added evidence coverage for large lazy tree pagination under a 640-group hierarchy and idempotent repeated open/close cycles on one shell.
- The large-tree test verifies no uncontrolled root-level eager traversal by asserting that children load only by explicit activation and that final load state stabilizes without a lingering load-more placeholder.
- The repeated open/close test confirms background tasks and open documents are drained between cycles.

Known gaps:

- `pytest -q` still reports pre-existing NumPy warnings in `tests/test_edge_cases.py::test_nan_inf_data` (3 warnings, unchanged).
- Linux verification is still pending for this task in CI.


## DV-0301 patch/change-set and validation primitives - 2026-07-14

Revision: working tree on `138c36b698e1805754b7e4e5981e45643744920e` with task-local edits in `data_viewer/editing/` and two new tests.

| Check | Command | Observed result |
|---|---|---|
| Targeted unit tests | `.venv\Scripts\python.exe -m pytest tests/test_editing_patches.py tests/test_editing_validation.py -q` | 12 passed |
| Static lint | `.venv\Scripts\ruff.exe check data_viewer/editing/patches.py data_viewer/editing/validation.py data_viewer/editing/history.py data_viewer/editing/__init__.py tests/test_editing_patches.py tests/test_editing_validation.py` | passed |
| Syntax check | `.venv\Scripts\python.exe -m compileall -q data_viewer/editing tests/test_editing_patches.py tests/test_editing_validation.py` | passed |

Notes:

- This task implements immutable patch/change-set models and edit validation without changing public contract surfaces required by DV-0301 scope.
- No production behavior in release-critical formatting or plugin integration paths was modified in this patch; changes are limited to safe-edit value validation primitives.

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

No report may use 閳?00%閳?unless it names the measured denominator and includes the artifact. A passing build is not a passing application.


## DV-0302 save/conflict state and review model - 2026-07-14

Revision: working tree on `data_viewer/editing/session.py`, `data_viewer/editing/review.py`, and `data_viewer/app/documents.py` before task commit; base commit `0baa01e`.

| Check | Command | Observed result |
|---|---|---|
| Windows target verification environment | `.venv\\Scripts\\python.exe --version` | `Python 3.12.13` |
| Focused editing/session unit suite | `.venv\\Scripts\\python.exe -m pytest tests/test_editing_session.py tests/test_document_controller.py -q` | 14 passed |
| Full local suite | `.venv\\Scripts\\python.exe -m pytest -q` | 257 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Lint gate (edited files + touched tests) | `.venv\\Scripts\\ruff.exe check data_viewer/editing/session.py data_viewer/editing/review.py data_viewer/app/documents.py tests/test_editing_session.py tests/test_document_controller.py` | passed |
| Syntax check | `.venv\\Scripts\\python.exe -m compileall -q data_viewer/editing/session.py data_viewer/editing/review.py data_viewer/app/documents.py tests/test_editing_session.py tests/test_document_controller.py` | passed |

Notes:

- End-to-end save/replace persistence and atomic write/verify are intentionally out of scope in this task; DV-0303 is still open.
- `mypy` on this exact file set reports unrelated pre-existing project type issues in `data_viewer/editing/validation.py`, `tests/conformance/source_adapter.py`, and existing test typing contracts.

## DV-0303 verified atomic replacement service - 2026-07-14

Revision: working tree based on `f89b844` (task-local edits in `data_viewer/persistence/` and two new tests).

| Check | Command | Observed result |
|---|---|---|
| Targeted persistence + recovery unit tests | `.venv\Scripts\python.exe -m pytest tests/test_persistence_recovery.py tests/test_persistence_transaction.py -q` | 23 passed |
| Lint gate (changed modules + tests) | `.venv\Scripts\ruff.exe check data_viewer/persistence/recovery.py data_viewer/persistence/transaction.py tests/test_persistence_recovery.py tests/test_persistence_transaction.py` | passed |
| Type check (targeted + follow-imports skip) | `.venv\Scripts\mypy.exe --follow-imports=skip data_viewer/persistence/recovery.py data_viewer/persistence/transaction.py tests/test_persistence_recovery.py tests/test_persistence_transaction.py` | Success: no issues found in 4 source files |
| Syntax check | `.venv\Scripts\python.exe -m compileall -q data_viewer/persistence tests/test_persistence_recovery.py tests/test_persistence_transaction.py` | passed |
| Full suite regression verification | `.venv\Scripts\python.exe -m pytest -q` | 280 passed, 1 skipped (3 existing NumPy warnings unchanged in `tests/test_edge_cases.py::test_nan_inf_data`) |

Notes:

- Added `.dvtrx` recovery marker handling tests and transaction fault-injection matrix covering TEMP_CREATE/WRITE/FLUSH/REOPEN_TEMP/VALIDATE_TEMP/REPLACE/FSYNC_DIR/REOPEN_FINAL/VALIDATE_FINAL.
- Recovery marker loading now converts malformed payloads into `WORKSPACE_INVALID` for startup-safety robustness.
- Windows atomic directory fsync is skipped in `FilesystemAdapter.sync_directory` to avoid lock issues while preserving Linux behavior.

Known gaps:

- Linux verification is still pending in local execution for this task; expected to be covered in workflow evidence.


## DV-0304 HDF5 persistence strategies - 2026-07-14

Revision: working tree based on `codex/data-viewer-foundation` with task-local edits in `data_viewer/sources/hdf5/` and `tests/test_hdf5_adapter.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused HDF5 adapter and persistence suite | `.venv\Scripts\python.exe -m pytest tests/test_hdf5_adapter.py -q` | 24 passed |
| Editing/persistence regression subset | `.venv\Scripts\python.exe -m pytest tests/test_hdf5_adapter.py tests/test_persistence_recovery.py tests/test_persistence_transaction.py tests/test_editing_patches.py tests/test_editing_session.py -q` | 58 passed |
| Lint gate | `.venv\Scripts\ruff.exe check data_viewer/sources/hdf5/session.py data_viewer/sources/hdf5/__init__.py tests/test_hdf5_adapter.py` | passed |
| Type check for touched source | `.venv\Scripts\mypy.exe --ignore-missing-imports --follow-imports=skip data_viewer/sources/hdf5/session.py` | Success: no issues found in 1 source file |
| Syntax check | `.venv\Scripts\python.exe -m compileall -q data_viewer/sources/hdf5/session.py tests/test_hdf5_adapter.py` | passed |
| Full local suite | `.venv\Scripts\python.exe -m pytest -q` | 286 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- HDF5 sessions now expose `EDIT_PATCH` and `ATOMIC_REWRITE` capabilities.
- Plain numeric cell patches use in-place writes only after source-fingerprint validation, old-value fingerprint checks, same-directory backup creation, flush/fsync, and changed-coordinate reread verification.
- Attribute patches and compound cell patches route through the verified atomic replacement service, then reopen and validate changed values plus representative unchanged data.
- Injected in-place verification failure preserves a recovery backup path and returns an integrity-warning error with `change_log_retained=true`.

Known gaps:

- This is local Windows evidence only; Linux verification remains pending in CI.

## DV-0305 export plan and receipt service - 2026-07-14

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/exporting/` and `tests/test_exporting.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused export tests | `.venv\Scripts\python.exe -m pytest tests/test_exporting.py -q` | 7 passed |
| Lint gate | `.venv\Scripts\ruff.exe check data_viewer/exporting tests/test_exporting.py` | passed |
| Type check | `.venv\Scripts\mypy.exe --follow-imports=skip data_viewer/exporting tests/test_exporting.py` | Success: no issues found in 5 source files |
| Syntax check | `.venv\Scripts\python.exe -m compileall -q data_viewer/exporting tests/test_exporting.py` | passed |
| Full local suite | `.venv\Scripts\python.exe -m pytest -q` | 293 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added `ExportPlan`, explicit v1 export scopes, target formats, and raw/display/scaled value modes.
- Added `ExportReceipt` with source fingerprint, resource/selection provenance, parameters, target, application version, warnings, bytes written, and success/failure/cancelled outcomes.
- Added `ExportService` with atomic target replacement, explicit overwrite refusal, cooperative cancellation receipts, NPY/CSV/JSON/TXT/binary output paths, and CSV spreadsheet formula escaping.

Known gaps:

- This is local Windows evidence only; Linux verification remains pending in CI.
- UI export dialogs, background queueing, and packaged smoke coverage remain later tasks.

## DV-0306 edit review, save, conflict, and export UI - 2026-07-14

Revision: working tree on `codex/data-viewer-foundation` with task-local edits in `data_viewer/gui/shell.py`, `data_viewer/app/documents.py`, `data_viewer/sources/registry.py`, and `tests/test_gui_shell.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused GUI edit/save/conflict/export tests | `.venv\Scripts\python.exe -m pytest tests/test_gui_shell.py -q` | 13 passed |
| Editing/save/export regression subset | `.venv\Scripts\python.exe -m pytest tests/test_gui_shell.py tests/test_document_controller.py tests/test_hdf5_adapter.py tests/test_exporting.py -q` | 52 passed |
| Lint gate | `.venv\Scripts\python.exe -m ruff check data_viewer\app\documents.py data_viewer\sources\registry.py data_viewer\gui\shell.py tests\test_gui_shell.py` | passed |
| Type check | `.venv\Scripts\python.exe -m mypy --ignore-missing-imports --follow-imports=skip data_viewer\app\documents.py data_viewer\sources\registry.py data_viewer\gui\shell.py tests\test_gui_shell.py` | Success: no issues found in 4 source files |
| Syntax check | `.venv\Scripts\python.exe -m compileall -q data_viewer\app\documents.py data_viewer\sources\registry.py data_viewer\gui\shell.py tests\test_gui_shell.py` | passed |
| Full local suite | `.venv\Scripts\python.exe -m pytest -q` | 296 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added shell-visible edit state, read-only hint, review/save/save-as/export controls, and bottom-panel task details so dirty/read-only/conflict states are not color-only.
- Added `DocumentController.save_edits()` and a managed-session `apply_change_set` bridge so GUI save executes real adapter persistence when supported instead of reaching into widget or adapter internals.
- Added active-payload export from the workspace through `ExportPlan`/`ExportService`, returning receipt-backed success/failure diagnostics.
- Added offscreen GUI coverage for dirty review/save/export, conflict-safe disabled save choices, dirty close cleanup, and shell screenshot rendering.

Known gaps:

- This is local Windows evidence only; Linux verification remains pending in CI/checkpoint evidence.
- Screenshot smoke is local/offscreen only; cross-platform themed visual review and fully interactive file-picker dialogs remain pending in checkpoint evidence.
## DV-0307 Checkpoint 3 persistence evidence - 2026-07-14

Checkpoint 3 is recorded against GitHub Actions run [29350463978](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29350463978), head `0a52f2a5b7da06796e669eed3577bd2e7faa072c` on branch `codex/data-viewer-foundation`.

Earlier CI attempts for this checkpoint failed and were superseded before evidence was accepted:

- run `29348960113`: lint failed on a stale HDF5 adapter import;
- run `29349219902`: full target mypy exposed existing target-package type gaps;
- run `29350184061`: CI PyQt typing exposed optional Qt handles that local stubs did not report.

| Platform | Job | Result | Manifest/JUnit evidence |
|---|---|---|---|
| Ubuntu | [87145070154](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29350463978/job/87145070154) | passed | artifact `data-viewer-quality-Ubuntu-29350463978-1`; manifest commit `0a52f2a5b7da06796e669eed3577bd2e7faa072c`; CPython `3.12.13`; runner `Linux x86_64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `297` tests, `0` failures, `0` errors, `1` skipped |
| Windows | [87145070244](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29350463978/job/87145070244) | passed | artifact `data-viewer-quality-Windows-29350463978-1`; manifest commit `0a52f2a5b7da06796e669eed3577bd2e7faa072c`; CPython `3.12.10`; runner `Windows AMD64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `297` tests, `0` failures, `0` errors, `1` skipped |

Downloaded artifact hashes checked from `C:\tmp\dv-ci-29350463978`:

| Platform | Artifact | SHA-256 |
|---|---|---|
| Ubuntu | `data_viewer-1.0.0.dev0-py3-none-any.whl` | `C3C71816B697230B7A266E6FC487F8A61FDE0573937D3992FE1A4875A1652B8F` |
| Ubuntu | `data_viewer-1.0.0.dev0.tar.gz` | `23E1796310EAC5D68D69DCBF3140C21EA35F957471BA8A4E8AE2D382A6802F59` |
| Windows | `data_viewer-1.0.0.dev0-py3-none-any.whl` | `E01FFF03CFA419C4CC69778CCD752BF708CCCAFF1CF73770746D5B714FD21CC2` |
| Windows | `data_viewer-1.0.0.dev0.tar.gz` | `75EA09C4AFEE69A46527193E6D85AD9E09BC38CB4C425880A5096DA560D95528` |

Evidence coverage:

- HDF5 edit persistence tests cover in-place cell patches, multi-cell preservation, verified replacement for attributes and compound cells, stale fingerprint rejection, and recovery backup/integrity warning behavior.
- Generic atomic transaction and recovery tests cover success, cancellation, disk budget, source-fingerprint conflict, failure injection across transaction steps, marker retention/cleanup, and final validation type safety.
- Export tests cover explicit scope/value-mode planning, NPY/CSV/JSON/TXT/binary service outcomes, overwrite refusal, cancellation receipts, unsupported-conversion failure, CSV formula-cell escaping, and receipt round trips.
- GUI shell tests cover dirty/read-only/conflict text states, save review/save execution, export receipt path, conflict-safe disabled save choices, dirty close cleanup, and offscreen screenshot rendering.

Known gaps:

- This is a Checkpoint 3 quality/evidence gate, not a v1 release gate. Packaged application smoke, full format matrix, plugin numerical matrix, workspace/compare matrix, visual DPI/theme matrix, SBOM/license evidence, and public release artifacts remain later tasks.

## DV-0401 NPY adapter and writer - 2026-07-14

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/sources/numpy/`, default registry wiring in `data_viewer/gui/shell.py`, shared conformance helper typing in `tests/conformance/source_adapter.py`, and `tests/test_numpy_adapter.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused NPY adapter/writer suite | `venv\Scripts\python.exe -m pytest tests\test_numpy_adapter.py -q` | 7 passed |
| NPY plus related registry/controller/GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_numpy_adapter.py tests\test_source_registry.py tests\test_document_controller.py tests\test_gui_shell.py -q` | 34 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\numpy data_viewer\gui\shell.py tests\test_numpy_adapter.py tests\conformance\source_adapter.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_numpy_adapter.py` | Success: no issues found in 49 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall -q data_viewer\sources\numpy data_viewer\gui\shell.py tests\test_numpy_adapter.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 303 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI evidence for the committed task revision:

| Platform | Job | Result | Manifest/JUnit evidence |
|---|---|---|---|
| Ubuntu | [87151579987](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29352393742/job/87151579987) | passed | artifact `data-viewer-quality-Ubuntu-29352393742-1`; manifest commit `46dc36ae552f28ba1964bed67f5a0ae17a9b4587`; CPython `3.12.13`; runner `Linux x86_64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `304` tests, `0` failures, `0` errors, `1` skipped |
| Windows | [87151580171](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29352393742/job/87151580171) | passed | artifact `data-viewer-quality-Windows-29352393742-1`; manifest commit `46dc36ae552f28ba1964bed67f5a0ae17a9b4587`; CPython `3.12.10`; runner `Windows AMD64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `304` tests, `0` failures, `0` errors, `1` skipped |

Downloaded artifact hashes checked from `C:\tmp\dv-ci-29352393742`:

| Platform | Artifact | SHA-256 |
|---|---|---|
| Ubuntu | `data_viewer-1.0.0.dev0-py3-none-any.whl` | `905D20E75549EB0DFF55993D58BA8C9CE3CFC3582D36A7FC949A984253194EBB` |
| Ubuntu | `data_viewer-1.0.0.dev0.tar.gz` | `85BB68563C39B77E825A127C071163DBC11387FD30F838E5B35989378A05FAC3` |
| Windows | `data_viewer-1.0.0.dev0-py3-none-any.whl` | `0F0140FF1BBB7226F59824FA80BD66ED4F80B1A82A614F251EAA2E63C61D7E91` |
| Windows | `data_viewer-1.0.0.dev0.tar.gz` | `30E542425A27D6DDB5EF9E77431C2627C6310FFCB4E9932DAAD71E61EC422147` |

Notes:

- Added `NPYAdapter` and `NPYSourceSession` with a synthetic root and one stable `/array` resource so flat NPY sources follow the same DataSource API ownership model as other adapters.
- Every NPY load path uses `allow_pickle=False`; object arrays fail with a structured `SOURCE_MALFORMED` error and no unsafe override.
- Read behavior covers shared conformance, scalar arrays, zero-length arrays, structured dtypes, Fortran order, byte-order preservation, normalized selections, budget refusal, cancellation, and missing-resource errors.
- NPY save uses reviewed `CellPatch` change sets, source-fingerprint conflict detection, full temporary `.npy` writing, `allow_pickle=False` reopen validation, shape/dtype/patch verification, and atomic replacement through `AtomicReplacementService`.
- The default target shell registry now registers HDF5 and NPY adapters.

Known gaps:

- This is DV-0401 task evidence only, not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0402 through DV-0411 finish.
- Scalar cell editing is still constrained by the current `CellPatch` coordinate contract, which disallows empty coordinates; scalar read/metadata behavior is covered here, and scalar edit support should be handled by a later edit-contract refinement if required.

## DV-0402 NPZ adapter and archive-rebuild writer - 2026-07-15

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/sources/npz/`, default registry wiring in `data_viewer/gui/shell.py`, and `tests/test_npz_adapter.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused NPZ adapter/writer suite | `venv\Scripts\python.exe -m pytest tests\test_npz_adapter.py -q` | 11 passed |
| NPY plus NPZ source regression subset | `venv\Scripts\python.exe -m pytest tests\test_numpy_adapter.py tests\test_npz_adapter.py -q` | 18 passed |
| Source registry/controller/GUI/NPY/NPZ regression subset | `venv\Scripts\python.exe -m pytest tests\test_source_registry.py tests\test_document_controller.py tests\test_gui_shell.py tests\test_numpy_adapter.py tests\test_npz_adapter.py -q` | 45 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\npz data_viewer\gui\shell.py tests\test_npz_adapter.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_npz_adapter.py` | Success: no issues found in 52 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall data_viewer\sources\npz data_viewer\gui\shell.py tests\test_npz_adapter.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 314 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added `NPZAdapter` and `NPZSourceSession` with one synthetic root, derived container nodes for slash-delimited member paths, and stable array resources such as `/array` and `/group/a`.
- NPZ open validates ZIP metadata before exposing resources: empty archives, non-`.npy` members, path traversal, absolute paths, duplicate normalized paths, encrypted entries, per-member size budget, total size budget, and extreme compression ratios fail with structured errors.
- Member header inspection rejects object dtypes before data reads; every member load uses `np.load(..., allow_pickle=False)`.
- Read behavior covers shared conformance, synthetic hierarchy listing, metadata provenance, normalized selections, and per-request byte budgets.
- NPZ save uses reviewed `CellPatch` change sets, source-fingerprint conflict detection, full temporary archive rebuild, `allow_pickle=False` reopen validation, changed-coordinate verification, representative unchanged-value verification, and atomic replacement through `AtomicReplacementService`.
- The default target shell registry now registers HDF5, NPY, and NPZ adapters.

Dual-platform CI evidence for the committed task revision:

| Platform | Job | Result | Manifest/JUnit evidence |
|---|---|---|---|
| Ubuntu | [87158465328](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29354452506/job/87158465328) | passed | artifact `data-viewer-quality-Ubuntu-29354452506-1`; manifest commit `f56632905becd03960c4b84fbe644e4627978507`; CPython `3.12.13`; runner `Linux x86_64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `315` tests, `0` failures, `0` errors, `1` skipped |
| Windows | [87158465343](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29354452506/job/87158465343) | passed | artifact `data-viewer-quality-Windows-29354452506-1`; manifest commit `f56632905becd03960c4b84fbe644e4627978507`; CPython `3.12.10`; runner `Windows AMD64`; lock hash `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`; JUnit `315` tests, `0` failures, `0` errors, `1` skipped |

Known gaps:

- This is DV-0402 task evidence only, not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0403 through DV-0411 finish.

## DV-0403 delimited import preview and CSV/TSV adapter - 2026-07-15

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/sources/delimited/`, default registry/table rendering wiring in `data_viewer/gui/shell.py`, shared table conformance support in `tests/conformance/source_adapter.py`, and `tests/test_delimited_adapter.py`.

| Check | Command | Observed result |
|---|---|---|
| Focused delimited adapter/preview suite | `venv\Scripts\python.exe -m pytest tests\test_delimited_adapter.py -q` | 9 passed |
| Delimited plus table-render GUI smoke | `venv\Scripts\python.exe -m pytest tests\test_delimited_adapter.py tests\test_gui_shell.py::test_opening_csv_file_updates_table_workspace -q` | 10 passed |
| Source registry/controller/GUI/NPY/NPZ/delimited regression subset | `venv\Scripts\python.exe -m pytest tests\test_source_registry.py tests\test_document_controller.py tests\test_gui_shell.py tests\test_numpy_adapter.py tests\test_npz_adapter.py tests\test_delimited_adapter.py -q` | 55 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\delimited data_viewer\gui\shell.py tests\test_delimited_adapter.py tests\test_gui_shell.py tests\conformance\source_adapter.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_delimited_adapter.py tests\test_gui_shell.py` | Success: no issues found in 57 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall data_viewer\sources\delimited data_viewer\gui\shell.py tests\test_delimited_adapter.py tests\test_gui_shell.py tests\conformance\source_adapter.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 324 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added `DelimitedTextAdapter`, `DelimitedSourceSession`, `DelimitedTextOptions`, and `preview_delimited_source` for CSV/TSV table sources.
- Opening uses bounded preview with explicit confirmed options: encoding, delimiter, quote/escape behavior, header row, skipped rows, comment prefix, decimal/thousands separators, missing tokens, and dtype overrides.
- Default decoding is strict UTF-8 with UTF-8 BOM detection; invalid bytes fail with `SOURCE_MALFORMED` and no replacement-character fallback.
- The adapter exposes one stable `/table` resource with `TABLE` domain, column schema metadata, paged row reads, selected-column reads, and stable zero-based data-row identity through `TablePayload.source_row()`.
- Format tests cover delimiter defaults, quoted values, BOM, Unicode, malformed quotes, invalid decoding, missing values, dtype overrides, selected columns, large-offset paged reads, missing sources, wrong resources, cancellation, and table-source conformance.
- The target shell registry now registers CSV/TSV and can render paged `TablePayload` data in the workspace table model.

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending the committed branch run.
- This is DV-0403 adapter/read evidence only. Verified CSV/TSV source overwrite, dialect-preserving rewrite, conflict handling, and transaction fault tests remain owned by DV-0404.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0404 through DV-0411 finish.

## DV-0404 CSV/TSV verified writer - 2026-07-15

Revision: working tree on `codex/data-viewer-foundation` with task-local writer additions in `data_viewer/sources/delimited/writer.py`, `DelimitedSourceSession.apply_change_set()`, and focused CSV/TSV writer tests in `tests/test_delimited_adapter.py`.

| Check | Command | Observed result |
|---|---|---|
| Initial failing writer test | `venv\Scripts\python.exe -m pytest tests\test_delimited_adapter.py -q` | failed as expected before implementation: 4 new writer tests failed because `DelimitedSourceSession` had no `apply_change_set` |
| Focused delimited adapter/writer suite | `venv\Scripts\python.exe -m pytest tests\test_delimited_adapter.py -q` | 14 passed |
| Source/edit/persistence regression subset | `venv\Scripts\python.exe -m pytest tests\test_source_registry.py tests\test_document_controller.py tests\test_numpy_adapter.py tests\test_npz_adapter.py tests\test_delimited_adapter.py tests\test_persistence_transaction.py -q` | 63 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\delimited tests\test_delimited_adapter.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_delimited_adapter.py` | Success: no issues found in 57 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall data_viewer\sources\delimited tests\test_delimited_adapter.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 329 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added a delimited writer that accepts reviewed `CellPatch` changesets for the stable `/table` resource and applies patches by original zero-based data-row coordinate and schema column index.
- Save uses the shared `AtomicReplacementService`: write a sibling temporary file, flush, reopen/validate the candidate, atomically replace, reopen/validate the destination, then refresh session fingerprint and preview metadata.
- Confirmed CSV/TSV dialect and encoding are reused for output; tests cover CSV quoting, TSV tab dialect, missing-token preservation, dtype conversion, CRLF preservation, and no-final-newline preservation.
- Validation rejects stale source fingerprints, wrong source/resource, non-cell patches, invalid table coordinates, old-value conflicts, row-count drift, column-count drift, and patched-value mismatch with structured `DataViewerError` values.
- Failure injection at the replacement step leaves the original delimited source unchanged in the focused task test; broader transaction failure-step behavior remains covered by `tests/test_persistence_transaction.py`.

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0405 through DV-0411 finish.

## DV-0405 TXT text/table dual-mode adapter and writer - 2026-07-15

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/sources/text/`, TXT registration in the target shell registry, text workspace rendering in `data_viewer/gui/shell.py`, and tests in `tests/test_text_adapter.py` plus `tests/test_gui_shell.py`.

| Check | Command | Observed result |
|---|---|---|
| Initial failing TXT adapter test | `venv\Scripts\python.exe -m pytest tests\test_text_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.text` did not exist |
| Focused TXT adapter/writer suite | `venv\Scripts\python.exe -m pytest tests\test_text_adapter.py -q` | 5 passed |
| TXT plus GUI smoke | `venv\Scripts\python.exe -m pytest tests\test_text_adapter.py tests\test_gui_shell.py::test_opening_txt_file_updates_text_workspace -q` | 6 passed |
| Source/text/delimited/registry/GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_text_adapter.py tests\test_delimited_adapter.py tests\test_source_registry.py tests\test_gui_shell.py -q` | 40 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\text data_viewer\gui\shell.py tests\test_text_adapter.py tests\test_gui_shell.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_text_adapter.py tests\test_gui_shell.py` | Success: no issues found in 61 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall data_viewer\sources\text data_viewer\gui\shell.py tests\test_text_adapter.py tests\test_gui_shell.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 335 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added `TXTAdapter` and `TextSourceSession`; `.txt` defaults to strict UTF-8 or UTF-8-BOM text mode and does not infer whitespace-delimited scientific notation as a table.
- Text mode exposes one stable `/text` resource with `TEXT` domain, `STREAMING_READ`, `EDIT_PATCH`, `ATOMIC_REWRITE`, and `SAVE_AS` capabilities.
- Text reads are bounded through page-style `ReadRequest` offsets/limits and return `TextPayload` with offset and completion provenance.
- Text persistence accepts reviewed `TextPatch` ranges, validates old text fingerprints, writes a complete replacement through `AtomicReplacementService`, validates the candidate, refreshes the session fingerprint, and preserves untouched bytes including line endings and final-newline state.
- Explicit table mode requires caller-provided `DelimitedTextOptions` and delegates to the CSV/TSV delimited session/writer, preserving the no-silent-table-inference rule.
- The target shell now registers `TXTAdapter` and renders `TextPayload` as a one-column workspace preview.

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0406 through DV-0411 finish.

## DV-0406 JSON structured adapter - 2026-07-15

Revision: working tree on `codex/data-viewer-foundation` with task-local additions in `data_viewer/sources/json/`, JSON registration and structured-preview rendering in `data_viewer/gui/shell.py`, and tests in `tests/test_json_adapter.py` plus `tests/test_gui_shell.py`.

| Check | Command | Observed result |
|---|---|---|
| Initial failing JSON adapter test | `venv\Scripts\python.exe -m pytest tests\test_json_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.json` did not exist |
| Focused JSON adapter suite | `venv\Scripts\python.exe -m pytest tests\test_json_adapter.py -q` | 5 passed |
| JSON plus GUI smoke | `venv\Scripts\python.exe -m pytest tests\test_json_adapter.py tests\test_gui_shell.py::test_opening_json_file_updates_structured_workspace -q` | 6 passed |
| JSON/registry/GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_json_adapter.py tests\test_source_registry.py tests\test_gui_shell.py -q` | 27 passed |
| Lint gate | `venv\Scripts\ruff.exe check data_viewer\sources\json data_viewer\gui\shell.py tests\test_json_adapter.py tests\test_gui_shell.py` | passed |
| Type check | `venv\Scripts\python.exe -m mypy data_viewer tests\test_json_adapter.py tests\test_gui_shell.py` | Success: no issues found in 64 source files |
| Syntax check | `venv\Scripts\python.exe -m compileall data_viewer\sources\json data_viewer\gui\shell.py tests\test_json_adapter.py tests\test_gui_shell.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 341 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Notes:

- Added `JSONAdapter` and `JSONSourceSession`; `.json` opens as read-only `STRUCTURED` data using strict UTF-8 or UTF-8-BOM only.
- Stable resource paths use JSON Pointer escaping for object keys and array indices, including `/` as `~1` and `~` as `~0`.
- Scalar JSON roots are valid structured resources, and object/array nodes expose direct children through paginated hierarchy listing.
- Duplicate object keys are detected while parsing; Data Viewer uses Python/std-json last-value semantics and surfaces a warning instead of claiming duplicate keys were losslessly represented.
- File-size, nesting-depth, collection-length, and string-length budgets raise structured `BUDGET_EXCEEDED` errors before payload use.
- The target shell now registers `JSONAdapter` and renders `StructuredPayload` as a one-column structured JSON preview.

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0407 through DV-0411 finish.

## DV-0407 restricted YAML adapter - 2026-07-15

Revision: working tree based on `2abf707` before committing `feat: add yaml structured adapter`.

Implementation evidence:

- `data_viewer/sources/yaml` adds a read-only YAML/YML adapter and source session using `yaml.safe_load` only.
- The adapter exposes structured resources through JSON Pointer paths, maps nonstring YAML keys to display-safe path tokens, and records original key type/display metadata.
- Unsafe/custom tags, malformed YAML, recursive aliases, over-budget file size, nesting depth, collection length, scalar length, and alias counts fail with structured `DataViewerError` values.
- Alias and merge-key counts are exposed in metadata so the resolved safe-load tree is not mistaken for original YAML spelling.
- The target shell registry includes `YAMLAdapter`, and GUI smoke coverage proves YAML structured payloads render through the existing structured preview path.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Existing dependency sync | `venv\Scripts\python.exe -m pip install PyYAML==6.0.3` | passed; installed the version already present in `uv.lock` because the local `venv` lacked the declared dependency |
| YAML focused tests | `venv\Scripts\python.exe -m pytest tests\test_yaml_adapter.py -q` | 5 passed |
| YAML GUI smoke | `venv\Scripts\python.exe -m pytest tests\test_gui_shell.py::test_opening_yaml_file_updates_structured_workspace -q` | 1 passed |
| Structured-source regression subset | `venv\Scripts\python.exe -m pytest tests\test_yaml_adapter.py tests\test_json_adapter.py tests\test_gui_shell.py::test_opening_json_file_updates_structured_workspace tests\test_gui_shell.py::test_opening_yaml_file_updates_structured_workspace -q` | 12 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\yaml data_viewer\gui\shell.py tests\test_yaml_adapter.py tests\test_gui_shell.py` | passed |
| YAML type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\yaml` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 347 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_yaml_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 65 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token even though SSH git push works.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0408 through DV-0411 finish.

## DV-0408 MATLAB MAT adapter - 2026-07-15

Revision: working tree based on `fe712ce` before committing `feat: add mat source adapter`.

Implementation evidence:

- `data_viewer/sources/mat` adds a read-only MAT adapter and source session.
- Legacy MAT files dispatch through SciPy `loadmat`; HDF5-backed v7.3-style `.mat` files dispatch through h5py.
- The session exposes one stable hierarchy rooted at `/`, with variables as direct children and nested cell/struct/HDF5 group entries as escaped path nodes.
- Legacy internal keys `__globals__`, `__header__`, and `__version__`, and HDF5 `#refs#`, are hidden from the default tree and reported as metadata instead.
- Numeric, logical, and complex arrays read as `ArrayPayload`; char arrays read as `TextPayload`; sparse/reference/unsupported values read as structured summaries.
- HDF5 v7.3 traversal has cycle and node-count protection; hard-link cycles are surfaced without recursive expansion.
- MAT is registered in the target shell registry but exposes no source editing or atomic rewrite capability.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Existing dependency sync | `venv\Scripts\python.exe -m pip install scipy==1.18.0` | passed; installed the version already present in `uv.lock` because the local `venv` lacked the declared dependency |
| Initial failing MAT adapter test | `venv\Scripts\python.exe -m pytest tests\test_mat_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.mat` did not exist |
| MAT focused tests | `venv\Scripts\python.exe -m pytest tests\test_mat_adapter.py -q` | 4 passed |
| MAT and registry regression subset | `venv\Scripts\python.exe -m pytest tests\test_mat_adapter.py tests\test_source_registry.py -q` | 10 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\mat data_viewer\gui\shell.py tests\test_mat_adapter.py` | passed |
| MAT type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\mat` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 351 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_mat_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 68 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token even though SSH git push works.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0409 through DV-0411 finish.

## DV-0409 safe XLSX adapter - 2026-07-15

Revision: working tree based on `268ed2b` before committing `feat: add xlsx source adapter`.

Implementation evidence:

- `data_viewer/sources/xlsx` adds a read-only XLSX adapter and source session using openpyxl.
- The adapter registers `.xlsx` only; `.xlsm` is not claimed.
- Workbooks open with `keep_links=False`; the root metadata records that external links are disabled and macros are unsupported.
- Formula view and cached-value view are opened separately. Formula cells expose formula text plus cached-value availability without executing formulas.
- The resource tree exposes `/sheets/<name>` table resources plus cell, table, merged-range, and defined-name inspection nodes.
- Sheet reads are bounded page/full table reads with Excel-column identities and `None` values for blank cells inside the used range.
- Encrypted/OLE-style workbooks fail with `SOURCE_ENCRYPTED`; malformed ZIP/workbook inputs fail with structured source errors.
- XLSX is registered in the target shell registry but exposes no source editing or atomic rewrite capability.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Existing dependency sync | `venv\Scripts\python.exe -m pip install openpyxl==3.1.5` | passed; installed the version already present in `uv.lock` because the local `venv` lacked the declared dependency |
| Initial failing XLSX adapter test | `venv\Scripts\python.exe -m pytest tests\test_xlsx_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.xlsx` did not exist |
| XLSX focused tests | `venv\Scripts\python.exe -m pytest tests\test_xlsx_adapter.py -q` | 4 passed |
| XLSX and registry regression subset | `venv\Scripts\python.exe -m pytest tests\test_xlsx_adapter.py tests\test_source_registry.py -q` | 10 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\xlsx data_viewer\gui\shell.py tests\test_xlsx_adapter.py` | passed |
| XLSX type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\xlsx` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 355 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_xlsx_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 72 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token even though SSH git push works.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0410 and DV-0411 finish.

## DV-0410 NIfTI adapter and coordinate model - 2026-07-15

Revision: working tree based on `2c642d9` before committing `feat: add nifti source adapter`.

Implementation evidence:

- `data_viewer/sources/nifti` adds a read-only NIfTI adapter and source session using NiBabel proxy loading.
- The adapter claims `.nii` and native `.nii.gz`; `.nii.gz` is validated as native NIfTI gzip rather than generic wrapped gzip.
- NIfTI metadata records raw shape/dtype, affine, axis codes, voxel sizes, xyzt units, intent, scaling, proxy type, header summary, and no-resampling provenance.
- Bounded volume reads slice `image.dataobj` directly and return `VolumePayload` with source-coordinate provenance; ordinary slice reads do not call full-volume materialization.
- `voxel_to_world` and `world_to_voxel` expose exact affine and inverse-affine coordinate mapping without silent canonicalization, reorientation, or resampling.
- NIfTI is registered in the target shell registry but exposes no source editing or atomic rewrite capability.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Existing dependency sync | `venv\Scripts\python.exe -m pip install nibabel==5.4.2` | passed; installed the version already present in `uv.lock` because the local `venv` lacked the declared dependency |
| Initial failing NIfTI adapter test | `venv\Scripts\python.exe -m pytest tests\test_nifti_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.nifti` did not exist |
| NIfTI focused tests | `venv\Scripts\python.exe -m pytest tests\test_nifti_adapter.py -q` | 4 passed |
| NIfTI and registry regression subset | `venv\Scripts\python.exe -m pytest tests\test_nifti_adapter.py tests\test_source_registry.py -q` | 10 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\nifti data_viewer\gui\shell.py tests\test_nifti_adapter.py` | passed |
| NIfTI type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\nifti` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 359 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_nifti_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 75 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token even though SSH git push works.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix is still incomplete until DV-0411 finishes.

## DV-0411 NetCDF/Zarr product-path removal - 2026-07-15

Revision: working tree based on `d3bd62a` before committing `chore: remove netcdf zarr product paths`.

Implementation evidence:

- Legacy startup no longer imports or registers `plugins.external.netcdf_source.NetCDFSource` or `plugins.external.zarr_source.ZarrSource`.
- Obsolete external NetCDF/Zarr source modules were removed from `plugins/external`.
- Legacy folder explorer defaults no longer advertise `.zarr` as an openable directory format.
- `requirements.txt` no longer contains optional NetCDF/Zarr dependency claims.
- The target Data Viewer registry returns ordinary `SOURCE_UNSUPPORTED` for `.nc`, `.nc4`, `.netcdf`, and `.zarr` inputs.
- Case-insensitive repository search was reviewed. Remaining `NetCDF`/`Zarr` mentions are limited to explicit v1 exclusion/specification text, historical task planning, and DV-0411 regression tests.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing scope test | `venv\Scripts\python.exe -m pytest tests\test_format_scope.py -q` | failed as expected before implementation: legacy `.zarr` filtering, legacy startup imports, requirements claims, and external source files still existed |
| Format scope regression tests | `venv\Scripts\python.exe -m pytest tests\test_format_scope.py -q` | 5 passed |
| Format scope and registry regression subset | `venv\Scripts\python.exe -m pytest tests\test_format_scope.py tests\test_source_registry.py -q` | 11 passed |
| Case-insensitive inventory search | `rg -n -i "netcdf|zarr" .` | reviewed; remaining hits are v1 exclusion/specification, historical planning, or regression-test assertions |
| Strong product-path search | `rg -n -i "plugins\.external\.(netcdf|zarr)|NetCDFSource|ZarrSource|netCDF4|zarr>=" .` | reviewed; remaining hits only appear inside DV-0411 regression-test assertions |
| Scoped lint | `venv\Scripts\python.exe -m ruff check main.py core\registry.py gui\sidebar\folder_explorer.py tests\test_format_scope.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 364 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer main.py core\registry.py gui\sidebar\folder_explorer.py tests\test_format_scope.py tests\test_nifti_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 75 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q main.py core gui data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending because the current Codex shell reports an invalid GitHub CLI token even though SSH git push works.
- This is not Checkpoint 4 evidence. The full uncompressed format matrix still needs DV-0412 evidence recording.

## DV-0412 Checkpoint 4 uncompressed format evidence - 2026-07-15

Checkpoint 4 is recorded against GitHub Actions run [29364690093](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29364690093), head `98fb32babd8bdcfab8d1ee3a147244453dca42a2` on branch `codex/data-viewer-foundation`.

Format inventory:

- `docs/FORMAT_INVENTORY.md` records the current v1 uncompressed format matrix for HDF5, NPY, NPZ, CSV, TSV, TXT, MAT, NIfTI, XLSX, JSON, and YAML/YML.
- The inventory records safe-edit formats separately from read-only plus export/Save As formats.
- NetCDF and Zarr are recorded as excluded from v1; DV-0411 removed remaining product paths.
- Outer `.gz` composition remains out of this checkpoint and starts at DV-0501.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 364 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer main.py core\registry.py gui\sidebar\folder_explorer.py tests\test_format_scope.py tests\test_nifti_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 75 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q main.py core gui data_viewer tests` | passed |

Dual-platform CI verification:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub CLI auth | `gh auth status` | logged in as `alvinloga`; SSH git protocol; repo-scoped token available |
| Latest branch run | `gh run list --branch codex/data-viewer-foundation --limit 10` | latest run `29364690093` for `98fb32b` started after DV-0411 push |
| CI watch | `gh run watch 29364690093 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29364690093 --json status,conclusion,headSha,jobs,url` | status `completed`, conclusion `success`, head SHA `98fb32babd8bdcfab8d1ee3a147244453dca42a2` |
| Artifact download | `gh run download 29364690093 --dir .tmp\ci-29364690093` | downloaded Windows and Ubuntu quality artifacts |
| Windows quality job | downloaded `ci-reports\Windows\manifest.json` and `pytest.xml` | CPython 3.12.10, Windows/AMD64, run attempt 1, 365 tests, 0 failures, 0 errors, 1 skipped |
| Ubuntu quality job | downloaded `ci-reports\Ubuntu\manifest.json` and `pytest.xml` | CPython 3.12.13, Linux/x86_64, run attempt 1, 365 tests, 0 failures, 0 errors, 1 skipped |
| Build artifacts | downloaded `artifacts\Windows` and `artifacts\Ubuntu` | both platforms produced `data_viewer-1.0.0.dev0.tar.gz` and `data_viewer-1.0.0.dev0-py3-none-any.whl` |

Known gaps:

- This is a Checkpoint 4 uncompressed-format evidence gate, not a v1 release gate.
- Outer gzip composition, UI redesign/workspace/compare, plugin infrastructure and catalog, packaged application installers, SBOM/license evidence, and public GitHub release artifacts remain later tasks.

## DV-0501 compound format detection and gzip stream wrapper - 2026-07-15

Revision: working tree based on `b150ad2` before committing `feat: add gzip stream wrapper`.

Implementation evidence:

- `data_viewer/sources/gzip` adds a composable generic gzip wrapper adapter for stream-capable inner formats.
- The default target registry registers generic gzip for `.csv.gz`, `.tsv.gz`, `.txt.gz`, `.json.gz`, `.yaml.gz`, and `.yml.gz`.
- `.nii.gz` remains native NIfTI and is not claimed by the generic gzip wrapper.
- Probing validates gzip framing, reads a bounded decompressed prefix, and then delegates validation to the inner adapter using the virtual inner suffix.
- Opening a stream-capable gzip source creates a lifecycle-bound decompressed stream session and maps all inner `ResourceId` values back to the original `.gz` source URI.
- Generic gzip results are read-only in v1; read results carry a gzip wrapper warning.
- Corrupt/truncated gzip and false-extension inputs return structured source errors.
- Random-access gzip wrappers such as HDF5/NPY/NPZ/MAT/XLSX remain outside DV-0501 and are owned by DV-0502.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing gzip wrapper test | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.gzip` did not exist |
| Gzip focused tests | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py -q` | 5 passed |
| Gzip related regression subset | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py tests\test_json_adapter.py tests\test_source_registry.py tests\test_gui_shell.py -q` | 33 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\gzip data_viewer\sources\json\adapter.py data_viewer\sources\delimited\adapter.py data_viewer\gui\shell.py tests\test_gzip_adapter.py` | passed |
| Gzip type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\gzip` | passed |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer\sources\gzip data_viewer\sources\json data_viewer\sources\delimited data_viewer\gui\shell.py tests\test_gzip_adapter.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 369 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_gzip_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 77 source files |
| Full compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending after commit/push.
- This is not Checkpoint 5 evidence. Random-access gzip extraction, full gzip matrix integration, UI read-only messaging, and checkpoint ledger remain DV-0502 through DV-0504.

## DV-0502 managed random-access extraction cache - 2026-07-15

Revision: working tree based on `4c43cc9` before committing `feat: add gzip extraction cache`.

Implementation evidence:

- `data_viewer/sources/gzip/cache.py` adds `ManagedExtractionCache` with `ExtractionLimits`.
- Random-access gzip extraction uses canonical cache keys derived from resolved file URI, compressed size, mtime, and compressed-prefix hash.
- Extraction enforces free-disk, decompressed-size, and compression-ratio budgets before committing cache entries.
- Cancellation and failed extraction remove `.incomplete` files and leave no committed cache entry.
- Startup cleanup removes abandoned `.incomplete` files and expired indexed cache entries.
- `GzipAdapter` can now use the managed extraction cache for random-access inner adapters while preserving outer `.gz` resource identity and read-only gzip warnings.
- Existing stream-capable gzip behavior from DV-0501 remains unchanged.
- NPY gzip random-access fixture coverage proves decompressed cache open/read, cache reuse, source-fingerprint invalidation, budget failure, cancellation cleanup, and expired-entry janitor behavior.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing extraction-cache test | `venv\Scripts\python.exe -m pytest tests\test_gzip_extraction_cache.py -q` | failed as expected before implementation: collection failed because `data_viewer.sources.gzip.cache` did not exist |
| NPY gzip probe regression | `venv\Scripts\python.exe -m pytest tests\test_gzip_extraction_cache.py -q` after adding probe assertion | failed as expected until `NPYAdapter.probe()` no longer required the virtual inner path to exist |
| Gzip extraction focused tests | `venv\Scripts\python.exe -m pytest tests\test_gzip_extraction_cache.py tests\test_gzip_adapter.py tests\test_numpy_adapter.py -q` | 18 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\sources\gzip data_viewer\sources\numpy\adapter.py tests\test_gzip_extraction_cache.py tests\test_gzip_adapter.py` | passed |
| Gzip cache type check | `venv\Scripts\python.exe -m mypy data_viewer\sources\gzip` | passed |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer\sources\gzip data_viewer\sources\numpy tests\test_gzip_extraction_cache.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 375 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_gzip_extraction_cache.py tests\test_gzip_adapter.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 78 source files |
| Full compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |

Known gaps:

- This is local Windows task evidence only; dual-platform CI evidence is pending after commit/push.
- This is not Checkpoint 5 evidence. Full gzip format integration, read-only UX messaging, nested-compression warnings, dual-platform full matrix evidence, and checkpoint ledger remain DV-0503 through DV-0504.

## DV-0503 full gzip registry integration - 2026-07-15

Revision: working tree based on `b120bba` before committing the DV-0503 implementation.

Implementation evidence:

- The default target registry now composes generic gzip support for every non-NIfTI v1 source adapter: HDF5, NPY, NPZ, CSV, TSV, TXT, MAT, XLSX, JSON, YAML, and YML.
- `.nii.gz` remains routed to the native NIfTI adapter and is not labeled as a generic gzip wrapper.
- Stream-capable text-like gzip wrappers continue to use lifecycle-bound stream decompression.
- Random-access gzip wrappers use the managed extraction cache lazily, so constructing the registry does not create platform cache directories until a random-access gzip source is opened.
- Generic gzip sessions preserve outer `.gz` resource identity, strip edit/atomic-rewrite capabilities, and expose read-only gzip metadata.
- `.npz.gz` and `.xlsx.gz` open through the generic wrapper but expose inefficient nested-compression warnings.
- Export target inference treats `.npz.gz` and `.xlsx.gz` as ordinary binary paths rather than proposed nested-compression output formats.
- NPY session close now releases mmap handles through the array base chain, allowing Windows cleanup of lifecycle-bound gzip temp views.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial full gzip matrix test | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py::test_default_registry_opens_every_v1_gzip_form -q` | failed as expected before DV-0503 registry/probe integration because random-access virtual inner paths were not accepted and the default registry did not yet cover every gzip form |
| Full gzip matrix regression | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py::test_default_registry_opens_every_v1_gzip_form -q` | 1 passed |
| Gzip/read-only/export/GUI subset | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py tests\test_gzip_extraction_cache.py tests\test_exporting.py tests\test_gui_shell.py -q` | 37 passed |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_gzip_adapter.py tests\test_gzip_extraction_cache.py tests\test_exporting.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 78 source files |
| Full compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 377 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `5e83dca73b910a6dea61d20b3f6a5757905cc75c` |
| GitHub Actions run | `gh run watch 29367905118 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29367905118 --json status,conclusion,headSha,jobs,url` | head SHA `5e83dca73b910a6dea61d20b3f6a5757905cc75c`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29367905118` |
| Windows quality job | GitHub Actions run `29367905118` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m37s |
| Ubuntu quality job | GitHub Actions run `29367905118` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m39s |

Known gaps:

- This is DV-0503 task evidence, not consolidated Checkpoint 5 evidence. Checkpoint 5 recording remains DV-0504.

## Checkpoint 5 gzip evidence - 2026-07-15

Checkpoint 5 is recorded against GitHub Actions run [29368227262](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29368227262), head `ff641e528f55f4098b5e7086a0b3a3bf186f9b83` on branch `codex/data-viewer-foundation`.

Scope covered:

- DV-0501 implemented bounded compound gzip detection and stream-capable wrappers for text-like formats.
- DV-0502 implemented managed random-access gzip extraction with cache identity, budget, cancellation, invalidation, and cleanup coverage.
- DV-0503 integrated the default registry matrix for every v1 gzip form while preserving native NIfTI `.nii.gz` routing.
- Generic gzip wrappers are read-only in v1 and preserve outer `.gz` resource identity.
- `.npz.gz` and `.xlsx.gz` are readable but flagged as inefficient nested compression and are not inferred as export formats.
- Random-access gzip cache creation is lazy; constructing the default registry does not touch platform cache directories.
- Windows mmap cleanup for NPY gzip temp views is covered by the DV-0503 regression path.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Full gzip matrix regression | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py::test_default_registry_opens_every_v1_gzip_form -q` | 1 passed |
| Gzip/read-only/export/GUI subset | `venv\Scripts\python.exe -m pytest tests\test_gzip_adapter.py tests\test_gzip_extraction_cache.py tests\test_exporting.py tests\test_gui_shell.py -q` | 37 passed |
| Target lint | `venv\Scripts\python.exe -m ruff check data_viewer tests\test_gzip_adapter.py tests\test_gzip_extraction_cache.py tests\test_exporting.py tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 78 source files |
| Full compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 377 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification:

| Check | Command/source | Observed result |
|---|---|---|
| Latest branch run | `gh run list --branch codex/data-viewer-foundation --limit 3` | latest run `29368227262` for `ff641e5` started after the DV-0503 evidence commit |
| CI watch | `gh run watch 29368227262 --exit-status --interval 10` | completed successfully |
| Artifact download | `gh run download 29368227262 --dir .tmp\ci-29368227262` | downloaded Windows and Ubuntu quality artifacts |
| Windows manifest | downloaded `ci-reports\Windows\manifest.json` | CPython 3.12.10, Windows/AMD64, run attempt 1, lock SHA-256 `f44c592658057904746d776129076715cde998fb699a797e256f432fa2c07734`, git SHA `ff641e528f55f4098b5e7086a0b3a3bf186f9b83` |
| Ubuntu manifest | downloaded `ci-reports\Ubuntu\manifest.json` | CPython 3.12.13, Linux/x86_64, run attempt 1, same lock SHA-256 and git SHA |
| Windows pytest XML | downloaded `ci-reports\Windows\pytest.xml` | 378 tests, 0 failures, 0 errors, 1 skipped, 56.585 seconds |
| Ubuntu pytest XML | downloaded `ci-reports\Ubuntu\pytest.xml` | 378 tests, 0 failures, 0 errors, 1 skipped, 48.142 seconds |
| Build artifacts | downloaded `artifacts\Windows` and `artifacts\Ubuntu` | both platforms produced `data_viewer-1.0.0.dev0.tar.gz` and `data_viewer-1.0.0.dev0-py3-none-any.whl` |

Known gaps:

- This is a Checkpoint 5 gzip evidence gate, not a v1 release gate.
- UI system rebuild, plugin platform/catalog, workspace/compare features, hardening, packaged application installers, SBOM/license evidence, manual Windows/Linux acceptance, and public GitHub release artifacts remain later tasks.

## DV-0601 semantic themes, metrics, typography, and SVG icons - 2026-07-15

Revision: working tree based on `52bd499` before committing the DV-0601 implementation.

Implementation evidence:

- `data_viewer/gui/theme.py` adds centralized semantic light/dark palettes for the UI/UX required color roles.
- Palette validation includes WCAG contrast checks for primary/secondary text and focus indicators against ordinary shell surfaces.
- Compact desktop metrics encode the 4 px spacing scale, 28/32/36 px control heights, 26-30 px row-height range, and 4/6 px radius system.
- Typography tokens resolve platform UI and monospace font roles through Qt instead of hard-coded web fonts.
- A bundled `dv-line` monochrome SVG icon family exposes accessible titles and uses `currentColor` strokes rather than emoji or Unicode pseudo-icons.
- `build_application_stylesheet()` derives the target Qt stylesheet from semantic tokens, and the target application bootstrap applies the default light theme.
- `scan_ui_token_violations()` provides the repository palette/icon scan used by the DV-0601 tests.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing theme contract test | `venv\Scripts\python.exe -m pytest tests\test_gui_theme.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.gui.theme'` |
| Theme contract tests | `venv\Scripts\python.exe -m pytest tests\test_gui_theme.py -q` | 7 passed |
| GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_theme.py tests\test_gui_shell.py tests\test_gui_interaction.py -q` | 33 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_theme.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 79 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_theme.py` | passed |
| Focused shell subset | `venv\Scripts\python.exe -m pytest tests\test_gui_theme.py tests\test_gui_shell.py -q` | 24 passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 384 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `2f8c4246ddcdbf34421cb6c2e2853af5606567c9` |
| GitHub Actions run | `gh run watch 29369411175 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29369411175 --json status,conclusion,headSha,jobs,url` | head SHA `2f8c4246ddcdbf34421cb6c2e2853af5606567c9`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29369411175` |
| Windows quality job | GitHub Actions run `29369411175` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m54s |
| Ubuntu quality job | GitHub Actions run `29369411175` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m31s |

Known gaps:

- Broader shell layout/state rebuild, command registry, standard state components, localization, and visual screenshot matrix remain DV-0602 through DV-0608.

## DV-0602 command registry and ActiveContext - 2026-07-15

Revision: working tree based on `dcd363d` before committing the DV-0602 implementation.

Implementation evidence:

- `data_viewer/app/commands.py` adds a stable application-level command registry with command IDs, labels, shortcuts, semantic action names, and enabled/disabled evaluations.
- The default command registry covers the UI/UX shortcut baseline: open file/workspace, save, Save As, export, close view, command palette, find, global search, split view, toggle bottom panel, undo, and redo.
- `ActiveContextSnapshot` now records explicit document, resource, request generation, active split, active view, selection label, dirty, active-task, undo/redo, and bottom-panel state.
- `ActiveContext` adds typed update methods for active view, edit state, task state, and bottom-panel visibility without importing or scanning GUI widgets.
- Command availability is derived from `ActiveContextSnapshot`, with machine-stable command IDs and human-readable disabled reasons.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing command registry test | `venv\Scripts\python.exe -m pytest tests\test_command_registry.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.app.commands'` |
| Command registry focused tests | `venv\Scripts\python.exe -m pytest tests\test_command_registry.py -q` | 3 passed |
| App/GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_command_registry.py tests\test_gui_theme.py tests\test_gui_shell.py -q` | 27 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app data_viewer\gui tests\test_command_registry.py tests\test_gui_theme.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 80 source files |
| Compile | `venv\Scripts\python.exe -m compileall -q data_viewer\app data_viewer\gui tests\test_command_registry.py tests\test_gui_theme.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 387 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `9d4788700d3ceffd23b3c47da7de1cc38eaaddea` |
| GitHub Actions run | `gh run watch 29370245596 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29370245596 --json status,conclusion,headSha,jobs,url` | head SHA `9d4788700d3ceffd23b3c47da7de1cc38eaaddea`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29370245596` |
| Windows quality job | GitHub Actions run `29370245596` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m1s |
| Ubuntu quality job | GitHub Actions run `29370245596` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m36s |

Known gaps:

- The command registry is not yet fully bound into the rebuilt shell command bar; broader shell panel/layout work remains DV-0603.

## DV-0603 shell workbench structure - 2026-07-15

Revision: working tree based on `18b72e2` before committing the DV-0603 implementation.

Implementation evidence:

- `data_viewer/gui/shell.py` binds the DV-0602 command registry into a native Qt command bar with stable action object names, shortcuts, disabled reasons, and shell callbacks.
- The shell keeps one authoritative `navigation_region` structure tree while adding `workspace_tabs`, an explicit `active_split_label`, and an `ActiveContext` snapshot owned outside widget internals.
- The inspector is now organized as Overview, Attributes, Statistics, and Plugins tabs while preserving the existing `inspector_region` overview object name.
- The bottom workbench panel is now a Tasks/Output/Problems tab set, preserving the existing `bottom_region` output log and adding task/problem surfaces.
- The status bar exposes source, legacy path, mode, shape, dtype, scope, task, coordinates, read-only, and edit labels as named automation/test surfaces.
- The shell minimum size is reduced to a 1024×720 guard so the 1024×768 acceptance target can be exercised without fixed-width assumptions.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing shell contract test | `venv\Scripts\python.exe -m pytest tests\test_gui_shell.py::test_shell_workbench_structure_matches_ui_contract -q` | failed as expected before implementation: `assert None is not None` for missing `command_bar` |
| Focused shell contract test | `venv\Scripts\python.exe -m pytest tests\test_gui_shell.py::test_shell_workbench_structure_matches_ui_contract -q` | 1 passed |
| Shell regression suite | `venv\Scripts\python.exe -m pytest tests\test_gui_shell.py -q` | 18 passed |
| UI/command/theme regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_shell.py tests\test_command_registry.py tests\test_gui_theme.py -q` | 28 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui data_viewer\app tests\test_gui_shell.py tests\test_command_registry.py tests\test_gui_theme.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui data_viewer\app tests\test_gui_shell.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 80 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 388 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `5dcb3944f6fca0513323562e0362bfa856f674a9` |
| GitHub Actions run | `gh run watch 29371379700 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29371379700 --json status,conclusion,headSha,jobs,url` | head SHA `5dcb3944f6fca0513323562e0362bfa856f674a9`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29371379700` |
| Windows quality job | GitHub Actions run `29371379700` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m57s |
| Ubuntu quality job | GitHub Actions run `29371379700` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m37s |

Known gaps:

- Layout persistence hooks, screenshot matrix expansion, and richer split/tab behavior remain dependent P6/P9 tasks.

## DV-0604 standard async and content state components - 2026-07-15

Revision: working tree based on `6fddb89` before committing the DV-0604 implementation.

Implementation evidence:

- `data_viewer/gui/state_components.py` adds `StateKind`, `StateAction`, `StateViewModel`, `default_state_model()`, `error_state_model()`, and `StandardStateWidget`.
- The standard state vocabulary covers initial, loading, empty, ready, partial, error, disabled, dirty, read-only, conflicted, and stale states.
- State rendering exposes text labels, accessible names/descriptions, selectable summaries/details, and keyboard-reachable buttons instead of color-only state cues.
- Error states separate safe summary/details from retry actions; disabled actions carry explicit reason tooltips and accessible descriptions.
- No fake-data skeletons are introduced; default loading state uses a named cancellable action and clear target text.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing state-component test | `venv\Scripts\python.exe -m pytest tests\test_gui_state_components.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.gui.state_components'` |
| Focused state component tests | `venv\Scripts\python.exe -m pytest tests\test_gui_state_components.py -q` | 3 passed |
| GUI/theme/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_state_components.py tests\test_gui_theme.py tests\test_gui_shell.py -q` | 28 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_state_components.py tests\test_gui_theme.py tests\test_gui_shell.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_state_components.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 81 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 391 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `440dd9b7bfe79efa49bc76537165d500a3dffb7e` |
| GitHub Actions run | `gh run watch 29372242943 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29372242943 --json status,conclusion,headSha,jobs,url` | head SHA `440dd9b7bfe79efa49bc76537165d500a3dffb7e`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29372242943` |
| Windows quality job | GitHub Actions run `29372242943` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m11s |
| Ubuntu quality job | GitHub Actions run `29372242943` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m27s |

Known gaps:

- Broad shell/view replacement of ad-hoc state labels remains follow-up integration work after the reusable state component contract is available.

## DV-0605 base view contracts and widgets - 2026-07-15

Revision: working tree based on `847562f` before committing the DV-0605 implementation.

Implementation evidence:

- `data_viewer/gui/views.py` adds stable `ViewKind` and `BaseViewContract` values for workspace views and later plugin/result routing.
- `TableViewWidget` renders `TablePayload` through a virtual `QAbstractTableModel`, keeps row numbers as headers, and exposes page scope/source-row coordinates without adding source-row data columns.
- `ArrayViewWidget` renders only explicit 0D/1D/2D bounded projections, exposes original-to-result shape and normalized slice text, and rejects implicit high-dimensional flattening.
- `TextViewWidget` renders `TextPayload` as read-only text with offset coordinates and a visible partial-preview banner when `is_complete=False`; line numbers remain presentation metadata and are not injected into source text.
- `ImageViewWidget` renders 2D array projections with preserved aspect/zoom/interpolation labels and cursor display-to-source coordinate/value provenance.
- Base contracts include result channels so later plugin result renderers can target workspace table/array/text/image views without depending on concrete shell internals.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing base-view test | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.gui.views'` |
| Focused base view tests | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | 5 passed |
| GUI view/state/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py tests\test_gui_state_components.py tests\test_gui_shell.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_base_views.py tests\test_gui_state_components.py tests\test_gui_shell.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_base_views.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 82 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 396 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `f501c03f4e7d060abfc2b3d24b21375160d3ab71` |
| GitHub Actions run | `gh run watch 29373250702 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29373250702 --json status,conclusion,headSha,jobs,url` | head SHA `f501c03f4e7d060abfc2b3d24b21375160d3ab71`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29373250702` |
| Ubuntu quality job | GitHub Actions run `29373250702` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m29s |
| Windows quality job | GitHub Actions run `29373250702` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m10s |

Known gaps:

- The shell still uses its existing internal table model; replacing shell rendering with these reusable base views is a follow-up integration slice.
- Full image rendering, large-scroll performance instrumentation, and volume/NIfTI view specialization remain later P6/P8 work.

## DV-0606 import/save/export/options dialog primitives - 2026-07-15

Revision: working tree based on `f79cef1` before committing the DV-0606 implementation.

Implementation evidence:

- `data_viewer/gui/dialogs.py` adds `PathValidationWidget`, `SaveSummaryDialog`, `DestructiveConfirmationDialog`, and `ImportOptionsDialog`.
- Path validation reports inline errors, supports open/save/export modes, preserves long paths through selectable text and full-path tooltips, and does not launch platform file dialogs in tests.
- Save summary dialogs are application-modal, require reviewed patches, and show target URI, persistence strategy, affected resources, patch kinds, warnings, and a safe Cancel default.
- Destructive confirmations name the specific resource and consequence, avoid generic confirmation wording, and keep Cancel as the default button.
- Import options are preview-first and nonmodal; applying options is not the default action and the dialog does not mutate the source file.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing dialog test | `venv\Scripts\python.exe -m pytest tests\test_gui_dialogs.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.gui.dialogs'` |
| Focused dialog tests | `venv\Scripts\python.exe -m pytest tests\test_gui_dialogs.py -q` | 5 passed |
| GUI dialog/state/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_dialogs.py tests\test_gui_state_components.py tests\test_gui_shell.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_dialogs.py tests\test_gui_state_components.py tests\test_gui_shell.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_dialogs.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 83 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 401 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `6ca2f7ad8501dd1c370c2f6e821114209eafe54b` |
| GitHub Actions run | `gh run watch 29374040718 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29374040718 --json status,conclusion,headSha,jobs,url` | head SHA `6ca2f7ad8501dd1c370c2f6e821114209eafe54b`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29374040718` |
| Windows quality job | GitHub Actions run `29374040718` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m9s |
| Ubuntu quality job | GitHub Actions run `29374040718` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m41s |

Known gaps:

- These are reusable dialog primitives; full shell command wiring, platform file picker adapters, and localization catalog integration remain follow-up P6 tasks.

## DV-0607 accessibility/localization baseline slice - 2026-07-15

Revision: working tree based on `fa61e2a` before committing the first DV-0607 implementation slice.

Implementation evidence:

- `data_viewer/gui/i18n.py` adds centralized English (`en-US`) and Simplified Chinese (`zh-CN`) UI string resources with a missing-entry gate.
- `data_viewer/gui/accessibility.py` adds accessible-name audit helpers, focus-chain inspection, and 4 px grid high-DPI metric scaling.
- `DataViewerShell` accepts a locale for initial shell text, uses centralized strings for command-row buttons, tabs, panels, placeholders, and status defaults, and installs deterministic keyboard focus order from path input through primary command buttons.
- `SaveSummaryDialog`, `DestructiveConfirmationDialog`, `ImportOptionsDialog`, and standard state defaults now accept a locale while preserving English default behavior for existing callers.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing localization/accessibility test | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.gui.accessibility'`; after adding dialog/state assertions failed as expected with `SaveSummaryDialog.__init__() got an unexpected keyword argument 'locale'` |
| Focused localization/accessibility tests | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py -q` | 6 passed |
| GUI localization/dialog/state/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py tests\test_gui_dialogs.py tests\test_gui_state_components.py tests\test_gui_shell.py -q` | 32 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_i18n_accessibility.py tests\test_gui_dialogs.py tests\test_gui_state_components.py tests\test_gui_shell.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_i18n_accessibility.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 85 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 407 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `46e40b032fac9d704f10acc6364827ab9618572e` |
| GitHub Actions run | `gh run watch 29375321115 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29375321115 --json status,conclusion,headSha,jobs,url` | head SHA `46e40b032fac9d704f10acc6364827ab9618572e`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29375321115` |
| Windows quality job | GitHub Actions run `29375321115` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m03s |
| Ubuntu quality job | GitHub Actions run `29375321115` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m47s |

Known gaps:

- DV-0607 is not complete yet: base data view labels, plot screen-reader summary contracts, automated missing-string scans beyond the new catalog gate, and DPI screenshot evidence remain follow-up work before `tasks/todo.md` can be checked.

## DV-0607 base-view and plot accessibility contract slice - 2026-07-15

Revision: working tree based on `db7b1e3` before committing the second DV-0607 implementation slice.

Implementation evidence:

- `data_viewer/gui/views.py` now accepts a locale for base table/array/text/image view chrome and routes initial scope/coordinate/shape/slice labels through the centralized UI string catalog.
- `data_viewer/gui/accessibility.py` adds `PlotAccessibilitySummary`, establishing the v1 screen-reader summary contract for future PlotSpec renderers: title, axes, series, range, warnings, and data-table availability.
- `data_viewer/gui/i18n.py` adds English and Simplified Chinese entries for base-view chrome and plot accessibility summary text.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing base-view/plot accessibility test | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py -q` | failed as expected before implementation: `ImportError: cannot import name 'PlotAccessibilitySummary'` |
| Focused localization/accessibility tests | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py -q` | 7 passed |
| GUI localization/base-view/state/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py tests\test_gui_base_views.py tests\test_gui_state_components.py tests\test_gui_shell.py -q` | 33 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui tests\test_gui_i18n_accessibility.py tests\test_gui_base_views.py tests\test_gui_state_components.py tests\test_gui_shell.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_i18n_accessibility.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 85 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 408 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `7a862c6216a9d1954c3d69aa6900081b9bcdf3f2` |
| GitHub Actions run | `gh run watch 29376044598 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29376044598 --json status,conclusion,headSha,jobs,url` | head SHA `7a862c6216a9d1954c3d69aa6900081b9bcdf3f2`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29376044598` |
| Windows quality job | GitHub Actions run `29376044598` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m56s |
| Ubuntu quality job | GitHub Actions run `29376044598` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m30s |

Known gaps:

- DV-0607 is still not checked: an automated missing-string scan for remaining shell/runtime literals and DPI screenshot evidence are still required before marking the task complete.

## DV-0607 final accessibility/localization baseline evidence - 2026-07-15

Revision: working tree based on `94e6304` before committing the final DV-0607 test/status slice.

Implementation evidence:

- `tests/test_gui_i18n_accessibility.py` now includes a deterministic simulated 200% offscreen shell render in Simplified Chinese and saves a screenshot artifact in the pytest temp directory for layout evidence.
- The DV-0607 automated baseline now covers catalog completeness, English/Simplified Chinese shell/dialog/state/view text, accessible names, focus order, missing accessible-name audit behavior, compact high-DPI metric scaling, and plot screen-reader summary text.
- `tasks/todo.md` marks DV-0607 complete after the local verification below.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Focused localization/accessibility tests | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py -q` | 8 passed |
| GUI localization/shell regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_i18n_accessibility.py tests\test_gui_shell.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_gui_i18n_accessibility.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\gui tests\test_gui_i18n_accessibility.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 85 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 409 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Completion commit | `git push origin codex/data-viewer-foundation` | pushed `eb7b825cfc499fa98a084e22cbd98fdd447e4243` |
| GitHub Actions run | `gh run watch 29376618677 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29376618677 --json status,conclusion,headSha,jobs,url` | head SHA `eb7b825cfc499fa98a084e22cbd98fdd447e4243`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29376618677` |
| Windows quality job | GitHub Actions run `29376618677` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m03s |
| Ubuntu quality job | GitHub Actions run `29376618677` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m33s |

## Checkpoint 6 UI system and shell evidence - 2026-07-15

Revision: working tree based on `812cdc7` before committing DV-0608.

Checkpoint scope:

- DV-0601 semantic themes, compact metrics, typography roles, and monochrome SVG icons.
- DV-0602 command registry and non-widget `ActiveContext`.
- DV-0603 workbench shell with navigation, tabs/splits, inspector, bottom panel, and status bar.
- DV-0604 standard async/content state components.
- DV-0605 virtual table/array/text/image base views.
- DV-0606 import/save/export/options dialog primitives.
- DV-0607 English/Simplified Chinese localization baseline, accessibility helpers, focus order, high-DPI screenshot baseline, and plot screen-reader summary contract.

Local and CI evidence already recorded in the per-task sections above:

| Task | Completion/evidence commit | CI run |
|---|---|---|
| DV-0601 | `2f8c424`, `dcd363d` | `29369411175`, `29369689375` |
| DV-0602 | `9d47887`, `18b72e2` | `29370245596`, `29370489644` |
| DV-0603 | `5dcb394`, `6fddb89` | `29371379700`, `29371644606` |
| DV-0604 | `440dd9b`, `847562f` | `29372242943`, `29372523096` |
| DV-0605 | `f501c03`, `f79cef1` | `29373250702`, `29373512979` |
| DV-0606 | `6ca2f7a`, `fa61e2a` | `29374040718`, `29374307559` |
| DV-0607 | `46e40b0`, `7a862c6`, `eb7b825`, `812cdc7` | `29375321115`, `29376044598`, `29376618677`, `29376793970` |

DV-0608 verification:

| Check | Command | Observed result |
|---|---|---|
| Checkpoint documentation/status update | manual review of `tasks/todo.md`, `CHANGELOG.md`, and this section | DV-0608 checked; Checkpoint 6 evidence summarized without changing product code |

Known gaps moving into P7:

- P6 provides UI foundations and contracts; plugin discovery, compatibility forms, runner/result rendering, and reference plugins remain P7/P8 tasks.
- Full manual visual acceptance matrices are release-gate work in P11; current P6 evidence is automated offscreen and CI-based.

## DV-0701 plugin manifest schema and built-in registry - 2026-07-15

Revision: working tree based on `edafa2e` before committing the DV-0701 implementation.

Implementation evidence:

- `data_viewer/plugins/api.py` defines the public Plugin API v1 constants and initial typed runtime/result contracts (`PLUGIN_API_VERSION`, `ResultKind`, `InputDescriptor`, `DataChunk`, `InputAccess`, `PluginContext`, `ResultProvenance`, `PluginResult`, `DataViewerPlugin`).
- `data_viewer/plugins/manifests.py` validates untrusted `plugin.json` dictionaries/files before plugin code import, rejects unknown keys, enforces schema/API version 1, reverse-DNS IDs, semantic versions, packaged built-in entry points, input specs, closed parameter schemas, and result kinds.
- `data_viewer/plugins/registry.py` discovers only trusted built-in manifest paths, records invalid manifests and duplicate IDs as structured diagnostics, returns deterministic ordering, and imports entry points lazily only when `load_plugin_class()` is called.
- No reference analysis plugin is added in this task; executable reference plugin/conformance work remains DV-0705.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing plugin registry test | `venv\Scripts\python.exe -m pytest tests\test_plugin_registry.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.plugins'` |
| Focused plugin registry tests | `venv\Scripts\python.exe -m pytest tests\test_plugin_registry.py -q` | 16 passed |
| Plugin/package regression subset | `venv\Scripts\python.exe -m pytest tests\test_plugin_registry.py tests\test_data_viewer_package.py tests\test_packaged.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\test_plugin_registry.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\test_plugin_registry.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 89 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 425 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `02a6d63ca826bc8e76de96725149f75df2068a04` |
| GitHub Actions run | `gh run watch 29377713330 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29377713330 --json status,conclusion,headSha,jobs,url` | head SHA `02a6d63ca826bc8e76de96725149f75df2068a04`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29377713330` |
| Windows quality job | GitHub Actions run `29377713330` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m52s |
| Ubuntu quality job | GitHub Actions run `29377713330` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m31s |

Known gaps:

- Compatibility evaluation, parameter forms, plugin runner/input access, typed result validation, and reference plugin conformance are later P7 tasks.

## DV-0702 plugin compatibility evaluator and parameter form - 2026-07-15

Revision: working tree based on `628f2cc` before committing the DV-0702 implementation.

Implementation evidence:

- `data_viewer/plugins/compatibility.py` evaluates a built-in plugin manifest against selected resource candidates before Run is enabled, including input count, required dependencies, domain, ndim bounds, dtype family, selection support, random-access capability, and non-chunked memory-budget checks with exact disabled reasons.
- `data_viewer/plugins/parameters.py` validates the supported v1 parameter-schema subset, returns immutable default/value mappings, rejects unknown/missing/invalid values, and keeps plugin inputs JSON-safe for later runner work.
- `data_viewer/gui/plugin_forms.py` renders the supported parameter types with standard Qt widgets, keyboard focus, accessible names/descriptions, round-trip validation, and no plugin-created dialogs.
- Multi-input alignment, optional dependency checks, runner input access, and result materialization remain later P7 tasks.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing compatibility/form test | `venv\Scripts\python.exe -m pytest tests\test_plugin_compatibility_parameters.py -q` | failed as expected before implementation because `data_viewer.plugins.compatibility` did not exist |
| Focused compatibility/form tests | `venv\Scripts\python.exe -m pytest tests\test_plugin_compatibility_parameters.py -q` | 6 passed |
| Plugin P7 regression subset | `venv\Scripts\python.exe -m pytest tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 23 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins data_viewer\gui\plugin_forms.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins data_viewer\gui\plugin_forms.py tests\test_plugin_compatibility_parameters.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 92 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 432 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Completion commits | `git push origin codex/data-viewer-foundation` | pushed implementation commit `3d25170df75a4be055e755e41ff8b5e9e97219ed` and CI typing fix `ee05230ee1e3303bb82bc3692d39c2dec362a8c3` |
| Initial CI run | `gh run watch 29378889971 --exit-status --interval 10` | failed in Windows and Ubuntu type-checking because CI mypy caught a reused Qt widget variable name in `plugin_forms.py`; fixed by `ee05230ee1e3303bb82bc3692d39c2dec362a8c3` |
| Final GitHub Actions run | `gh run watch 29379097065 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29379097065 --json status,conclusion,headSha,jobs,url` | head SHA `ee05230ee1e3303bb82bc3692d39c2dec362a8c3`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29379097065` |
| Windows quality job | GitHub Actions run `29379097065` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m08s |
| Ubuntu quality job | GitHub Actions run `29379097065` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m33s |

Known gaps:

- Plugin runner/input access, result validation/materialization, multi-input shape/alignment semantics, and reference plugin conformance remain later P7 tasks.

## DV-0703 plugin runner and budgeted input access - 2026-07-15

Revision: working tree based on `4107f6a` before committing the DV-0703 implementation.

Implementation evidence:

- `data_viewer/plugins/runner.py` adds `PluginRunRequest`, `PluginInputBinding`, `BudgetedInputAccess`, and `PluginRunner` as a deterministic synchronous runner core that can later be scheduled by the task/threading layer without changing Plugin API v1.
- Plugin input access routes all metadata and payload reads through `DocumentController`, so plugins do not receive source sessions, adapters, or format-library handles and document-owned I/O leases remain authoritative.
- Bounded `read()` and first-axis `iter_chunks()` create explicit `ReadRequest` values with per-read `max_bytes`; chunk iteration checks cancellation before scheduling the next source read and does not flatten high-dimensional arrays.
- Runner execution creates/uses a `TaskRecord`, reports progress through task snapshots, maps cooperative cancellation to `CANCELLED`, preserves source/budget `DataViewerError` failures without partial results, maps unexpected plugin exceptions to safe `PLUGIN_FAILED` errors with raw cause only in diagnostics, and rejects stale generation results.
- Result schema validation/materialization and GUI/thread-pool scheduling remain later P7 tasks.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing runner test | `venv\Scripts\python.exe -m pytest tests\test_plugin_runner.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.plugins.runner'` |
| Focused runner tests | `venv\Scripts\python.exe -m pytest tests\test_plugin_runner.py -q` | 4 passed |
| Plugin P7 regression subset | `venv\Scripts\python.exe -m pytest tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 27 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\test_plugin_runner.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 93 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 436 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `03e1c4780829fd51b516fb53c0d5c85354b76568` |
| GitHub Actions run | `gh run watch 29379856832 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29379856832 --json status,conclusion,headSha,jobs,url` | head SHA `03e1c4780829fd51b516fb53c0d5c85354b76568`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29379856832` |
| Windows quality job | GitHub Actions run `29379856832` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m19s |
| Ubuntu quality job | GitHub Actions run `29379856832` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m52s |

Known gaps:

- Result schema validation/materialization, GUI/thread-pool scheduling, reference plugin conformance, and full multi-input result semantics remain later P7 tasks.

## DV-0704 typed plugin results, PlotSpec, and provenance - 2026-07-15

Revision: working tree based on `959a076` before committing the DV-0704 implementation.

Implementation evidence:

- `data_viewer/plugins/results.py` adds typed v1 result payloads for summary, table, array/image, declarative plot specs, and collections.
- Summary and table results must be JSON-safe; table rows must match declared columns; array/image results reject object dtype and require axes/source-selection provenance; image payloads must be 2D.
- `PlotSpec`/`PlotMark` are declarative data objects only, validate supported mark kinds and finite equal-length x/y values, and provide accessible summaries for future renderers.
- `ValidatedPluginResult.to_export_record()` includes result ID, plugin ID/version/API version, inputs, parameters, kind, materialization, computation scope, sampled flag, and warnings for workspace/export provenance.
- `BoundedResultStore` provides bounded in-memory array materialization for oversized array-like results until persistent result storage is introduced.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing result test | `venv\Scripts\python.exe -m pytest tests\test_plugin_results.py -q` | failed as expected before implementation: `ModuleNotFoundError: No module named 'data_viewer.plugins.results'` |
| Focused result tests | `venv\Scripts\python.exe -m pytest tests\test_plugin_results.py -q` | 4 passed |
| Plugin P7 regression subset | `venv\Scripts\python.exe -m pytest tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 31 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\test_plugin_results.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 94 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 440 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `56098ac910f9fedaa15ae6d196197d9cf13ecac4` |
| GitHub Actions run | `gh run watch 29380543601 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29380543601 --json status,conclusion,headSha,jobs,url` | head SHA `56098ac910f9fedaa15ae6d196197d9cf13ecac4`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29380543601` |
| Windows quality job | GitHub Actions run `29380543601` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m55s |
| Ubuntu quality job | GitHub Actions run `29380543601` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m38s |

Known gaps:

- Reference plugin conformance, concrete plugin implementations, and GUI renderer integration remain later P7/P8 tasks.

## DV-0705 plugin conformance kit and reference plugin - 2026-07-15

Revision: working tree based on `f4e346e` before committing the DV-0705 implementation.

Implementation evidence:

- `tests/conformance/plugin.py` adds reusable Plugin API v1 conformance helpers for packaged built-ins: manifest compatibility, disabled input-count reason, parameter defaults/validation, runner execution, result/provenance validation, cancellation without partial results, expected numerical payloads, and forbidden import scanning through Python AST.
- `data_viewer/plugins/builtin/dataset_profile/plugin.json` adds the packaged `org.dataviewer.dataset_profile` reference manifest discovered by the built-in registry without importing plugin code at startup.
- `data_viewer/plugins/builtin/dataset_profile/plugin.py` implements a chunked Dataset Profile reference plugin that uses only `PluginContext`/`InputAccess`, emits progress, checks cooperative cancellation, computes finite/missing/nonfinite/range/mean summary fields, returns a JSON-safe summary result, and records Plugin API v1 provenance.
- `pyproject.toml` includes the Dataset Profile `plugin.json` as package data so wheel/sdist discovery can find the packaged built-in manifest.
- `tests/test_builtin_dataset_profile_plugin.py` demonstrates discovery, lazy loading, compatibility, immutable empty parameter schema, bounded chunking, progress, cancellation, numerical golden behavior, empty/all-missing edge inputs, nonnumeric incompatibility reasons, result/provenance validation, and forbidden-import checks.
- This is the P7 reference/conformance slice. The fuller P8 statistics and visualization catalog remains future work.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing conformance/reference test | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_profile_plugin.py -q` | failed as expected before implementation: registry returned no `org.dataviewer.dataset_profile` manifest |
| Focused reference plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_profile_plugin.py -q` | 6 passed |
| Plugin P7 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 37 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 97 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 446 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for `data_viewer/plugins/builtin/dataset_profile/plugin.json` | wheel built successfully; `plugin.json` present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `3781a4616f8f5ffdd1c96e54a3be8acba5a1f04d` |
| GitHub Actions run | `gh run watch 29381483677 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29381483677 --json status,conclusion,headSha,jobs,url` | head SHA `3781a4616f8f5ffdd1c96e54a3be8acba5a1f04d`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29381483677` |
| Windows quality job | GitHub Actions run `29381483677` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m47s |
| Ubuntu quality job | GitHub Actions run `29381483677` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m39s |

Known gaps:

- DV-0705 provides the reusable conformance kit and one reference plugin only. P8 still owns the complete statistics/visualization plugin catalog and GUI renderer integration.

## Checkpoint 7 plugin platform evidence - 2026-07-15

Revision: working tree based on `342e926` before committing DV-0706.

Checkpoint scope:

- DV-0701 Plugin API v1 public skeleton, strict manifest validation, deterministic packaged built-in registry, structured diagnostics, duplicate-ID handling, and lazy entry-point import.
- DV-0702 single-input compatibility decisions, exact disabled reasons, immutable parameter validation/defaults, and standard keyboard-accessible Qt parameter forms.
- DV-0703 document-backed budgeted `InputAccess`, runner task integration, bounded reads/chunks, cooperative cancellation, stale-result rejection, and safe plugin error mapping.
- DV-0704 typed result validators, declarative plot payloads, provenance/export records, and bounded result materialization.
- DV-0705 reusable conformance helpers and packaged `org.dataviewer.dataset_profile` reference plugin with discovery, parameters, chunking, cancellation/progress, numerical golden, edge-input, result/provenance, forbidden-import, and package-data coverage.

Local and CI evidence already recorded in the per-task sections above:

| Task | Completion/evidence commit | CI run |
|---|---|---|
| DV-0701 | `02a6d63`, `628f2cc` | `29377713330` |
| DV-0702 | `3d25170`, `ee05230`, `4107f6a` | `29379097065`, `29379294866` |
| DV-0703 | `03e1c47`, `959a076` | `29379856832`, `29380056827` |
| DV-0704 | `56098ac`, `f4e346e` | `29380543601`, `29380735005` |
| DV-0705 | `3781a46`, `342e926` | `29381483677`, `29381616206` |

DV-0706 verification:

| Check | Command | Observed result |
|---|---|---|
| Checkpoint documentation/status update | manual review of `tasks/todo.md`, `CHANGELOG.md`, and this section | DV-0706 checked; Checkpoint 7 evidence summarized without changing product code |

Known gaps moving into P8:

- P7 provides the plugin platform foundation and one reference plugin. The production statistics/visualization catalog, concrete plot renderers, and full plugin UI routing remain P8 work.
- Third-party plugin installation, signing, process isolation, marketplace distribution, and permission systems remain explicitly out of v1 scope.

## DV-0801 Dataset Profile and Descriptive Statistics plugins - 2026-07-15

Revision: working tree based on `ee78aa5` before committing the DV-0801 implementation.

Implementation evidence:

- `data_viewer/plugins/builtin/dataset_profile/plugin.py` extends Dataset Profile with `estimated_bytes` and `value_semantics`, preserving chunked `InputAccess` execution and provenance-complete summary output.
- The same module adds `DescriptiveStatisticsPlugin`, a second built-in analysis plugin that produces `TableResultPayload` rows for count, missing/nonfinite counts, mean, sample standard deviation, configurable quantiles, median, and extrema.
- `data_viewer/plugins/builtin/descriptive_statistics/plugin.json` adds the packaged `org.dataviewer.descriptive_statistics` manifest with immutable parameters: `axis`, `nan_policy`, `quantile_low`, and `quantile_high`.
- `pyproject.toml` includes the Descriptive Statistics manifest as package data so wheel/sdist discovery can find both built-in statistics plugins.
- `tests/test_builtin_statistics_plugins.py` adds numerical golden coverage for Dataset Profile complex-magnitude semantics, flattened descriptive statistics, axis-0 descriptive statistics, manifest discovery ordering, provenance parameters, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing statistics plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py -q` | failed as expected before implementation: `org.dataviewer.descriptive_statistics` not discovered and Dataset Profile missing `estimated_bytes`/`value_semantics` |
| Focused statistics plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py -q` | 11 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 42 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 97 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 451 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for `data_viewer/plugins/builtin/dataset_profile/plugin.json` and `data_viewer/plugins/builtin/descriptive_statistics/plugin.json` | wheel built successfully; both `plugin.json` files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Implementation commit | `git push origin codex/data-viewer-foundation` | pushed `203796b59b28757a6d6e287acd1e4d51d8db940d` |
| GitHub Actions run | `gh run watch 29382422774 --exit-status --interval 10` | completed successfully |
| Run metadata | `gh run view 29382422774 --json status,conclusion,headSha,jobs,url` | head SHA `203796b59b28757a6d6e287acd1e4d51d8db940d`; run URL `https://github.com/alvinloga/HDF5-Viewer/actions/runs/29382422774` |
| Windows quality job | GitHub Actions run `29382422774` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 2m08s |
| Ubuntu quality job | GitHub Actions run `29382422774` | locked install, direct dependency smoke, target lint/type, compile, collection, full offscreen regression suite, sdist/wheel build, and evidence upload all passed in 1m28s |

Known gaps:

- Distribution/outlier summaries, correlation/covariance, dataset comparison, plot plugins, and GUI renderer integration remain later P8 tasks.

## DV-0802 Distribution Summary plugin - 2026-07-15

Revision: implementation commit `79c5318ae54751f34de1707cff78c2879712276a`.

Implementation evidence:

- `data_viewer/plugins/builtin/dataset_profile/plugin.py` adds `DistributionSummaryPlugin`, a built-in analysis plugin that uses chunked `InputAccess`, produces table results, and records full/sampled provenance.
- `data_viewer/plugins/builtin/distribution_summary/plugin.json` adds the packaged `org.dataviewer.distribution_summary` manifest with immutable parameters: `bins`, `nan_policy`, `sample_size`, and `seed`.
- `pyproject.toml` includes the Distribution Summary manifest as package data so wheel/sdist discovery can find all three current statistics plugins.
- `tests/test_builtin_distribution_summary_plugin.py` adds numerical golden coverage for histogram bins, IQR/MAD robust spread, skewness, excess kurtosis, constant input, empty/nonfinite input, explicit deterministic sampling metadata, manifest ordering, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing distribution plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_distribution_summary_plugin.py -q` | failed as expected before implementation: `org.dataviewer.distribution_summary` not discovered |
| Focused distribution plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_distribution_summary_plugin.py -q` | 5 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 47 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 97 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 456 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for Dataset Profile, Descriptive Statistics, and Distribution Summary `plugin.json` files | wheel built successfully; all three `plugin.json` files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29383105678 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `79c5318ae54751f34de1707cff78c2879712276a`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29383105678 |
| Ubuntu quality | GitHub Actions job `87250747799` | success; started `2026-07-15T02:02:21Z`, completed `2026-07-15T02:03:52Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87250747806` | success; started `2026-07-15T02:02:21Z`, completed `2026-07-15T02:04:19Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Correlation/covariance, dataset comparison, plot plugins, and GUI renderer integration remain later P8 tasks.

## DV-0803 Correlation/Covariance plugin - 2026-07-15

Revision: implementation commit `8e5b0b688858062c20f9178b33e8aa0f5f4c8d29`.

Implementation evidence:

- `data_viewer/plugins/builtin/dataset_profile/plugin.py` adds `CorrelationCovariancePlugin`, a built-in analysis plugin that uses chunked `InputAccess`, produces labeled symmetric table rows for both correlation and covariance, records full-scope provenance, and returns constant-variable warnings.
- `data_viewer/plugins/builtin/correlation_covariance/plugin.json` adds the packaged `org.dataviewer.correlation_covariance` manifest with immutable parameters: `variables_axis`, `variable_start`, `variable_count`, `missing_policy`, and `max_variables`.
- `pyproject.toml` includes the Correlation/Covariance manifest as package data so wheel/sdist discovery can find all four current statistics plugins.
- `tests/test_builtin_correlation_covariance_plugin.py` adds numerical golden coverage for known matrices, contiguous variable-range selection, listwise and pairwise missing-data alignment counts, constant-variable warnings, variable-count budget refusal, manifest discovery, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing correlation plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_correlation_covariance_plugin.py -q` | failed as expected before implementation: `org.dataviewer.correlation_covariance` not discovered |
| Focused correlation plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_correlation_covariance_plugin.py -q` | 7 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 54 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 97 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 463 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for Dataset Profile, Descriptive Statistics, Distribution Summary, and Correlation/Covariance `plugin.json` files | wheel built successfully; all four `plugin.json` files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29384243369 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `8e5b0b688858062c20f9178b33e8aa0f5f4c8d29`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29384243369 |
| Windows quality | GitHub Actions job `87254090309` | success; started `2026-07-15T02:30:22Z`, completed `2026-07-15T02:32:22Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Ubuntu quality | GitHub Actions job `87254090327` | success; started `2026-07-15T02:30:22Z`, completed `2026-07-15T02:32:18Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Dataset comparison, plot plugins, correlation heatmap, missing-data map, and GUI renderer integration remain later P8 tasks.

## DV-0804 Dataset Compare plugin - 2026-07-15

Revision: implementation commit `6cd5798b491194d59dbfdf4198e7e417600e8d0c`.

Implementation evidence:

- `data_viewer/plugins/builtin/dataset_profile/plugin.py` adds `DatasetComparePlugin`, a built-in two-input analysis plugin that refuses shape mismatches before metric computation, produces compatibility/count/error table rows, and records both input descriptors in result provenance.
- `data_viewer/plugins/builtin/dataset_compare/plugin.json` adds the packaged `org.dataviewer.dataset_compare` manifest with immutable parameters: `missing_policy` and `relative_error_mode`.
- `pyproject.toml` includes the Dataset Compare manifest as package data so wheel/sdist discovery can find all five current statistics plugins.
- `tests/test_builtin_dataset_compare_plugin.py` adds coverage for packaged discovery, identical arrays, near/different arrays with zero/nonfinite rules, no-broadcast shape refusal, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing dataset compare tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_compare_plugin.py -q` | failed as expected before implementation: `org.dataviewer.dataset_compare` not discovered |
| Focused dataset compare tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_compare_plugin.py -q` | 5 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_dataset_compare_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 59 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_dataset_compare_plugin.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_dataset_compare_plugin.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 97 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 468 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for Dataset Profile, Descriptive Statistics, Distribution Summary, Correlation/Covariance, and Dataset Compare `plugin.json` files | wheel built successfully; all five `plugin.json` files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29384924387 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `6cd5798b491194d59dbfdf4198e7e417600e8d0c`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29384924387 |
| Windows quality | GitHub Actions job `87256081306` | success; started `2026-07-15T02:47:03Z`, completed `2026-07-15T02:49:10Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Ubuntu quality | GitHub Actions job `87256081369` | success; started `2026-07-15T02:47:01Z`, completed `2026-07-15T02:48:34Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Plot plugins, correlation heatmap, missing-data map, and GUI renderer integration remain later P8 tasks.

## DV-0805 Declarative line/scatter/histogram/box plot plugins - 2026-07-15

Revision: implementation commits `deb3839d7084f41fc782353e4e25f2d813a96e28` and `a0281cd1e3a8009a507b12cb94c54ce9cbb670fe`.

Implementation evidence:

- `data_viewer/plugins/builtin/plots/plugin.py` adds `LinePlotPlugin`, `ScatterPlotPlugin`, `HistogramPlotPlugin`, and `BoxPlotPlugin`. Each returns a renderer-owned `PlotSpec` with finite coordinates only, explicit warnings for omitted nonfinite points, provenance-complete parameters, optional deterministic point/value sampling, and JSON-safe `data_table` metadata for copy/export/table alternatives.
- `data_viewer/plugins/builtin/{line_plot,scatter_plot,histogram_plot,box_plot}/plugin.json` add independent packaged built-in visualization manifests with immutable scalar parameters supported by Plugin API v1.
- `pyproject.toml` includes the four plot manifests as package data and packages the new `data_viewer.plugins.builtin.plots` implementation module.
- `tests/test_builtin_plot_plugins.py` adds coverage for packaged discovery, line PlotSpec/accessibility/export metadata, deterministic scatter sampling, histogram/box goldens, empty-finite refusal, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing plot plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_plot_plugins.py -q` | failed as expected before implementation: plot plugin manifests/module not discovered |
| Focused plot plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_plot_plugins.py -q` | 6 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_plot_plugins.py tests\test_builtin_dataset_compare_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_dataset_profile_plugin.py tests\test_plugin_results.py tests\test_plugin_runner.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py -q` | 65 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_dataset_compare_plugin.py tests\test_builtin_plot_plugins.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_dataset_profile_plugin.py tests\test_builtin_statistics_plugins.py tests\test_builtin_distribution_summary_plugin.py tests\test_builtin_correlation_covariance_plugin.py tests\test_builtin_dataset_compare_plugin.py tests\test_builtin_plot_plugins.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 100 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 474 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for all current built-in plugin manifests and `data_viewer/plugins/builtin/plots/plugin.py` | wheel built successfully; all nine `plugin.json` files plus the plot implementation module present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Initial GitHub Actions run | `gh run watch 29386141056 --exit-status --interval 10` | failed in Windows/Ubuntu type-check for head SHA `deb3839d7084f41fc782353e4e25f2d813a96e28`; fixed by `a0281cd1e3a8009a507b12cb94c54ce9cbb670fe` after matching the CI mypy target locally |
| GitHub Actions run | `gh run view 29386336372 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `a0281cd1e3a8009a507b12cb94c54ce9cbb670fe`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29386336372 |
| Ubuntu quality | GitHub Actions job `87260308308` | success; started `2026-07-15T03:21:42Z`, completed `2026-07-15T03:23:15Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87260308313` | success; started `2026-07-15T03:21:42Z`, completed `2026-07-15T03:23:45Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Concrete Qt plot renderer widgets, image/slice navigator, correlation heatmap, missing-data map, and NIfTI viewer remain later P8 tasks.

## DV-0806 Image and multidimensional slice navigator - 2026-07-15

Revision: implementation commits `97587ab3676898b7ec6a0c600f414de01e1dd3e4` and `00722c8261a08ee3083311d96fd15d0d072c8004`.

Implementation evidence:

- `data_viewer/gui/views.py` adds `MultidimensionalSliceNavigatorWidget`, a workspace image projection view that reuses the base image view contract while exposing explicit high-dimensional axis/index navigation state, raw/display mode labels, linked-slice status, bounded-read provenance, preserved aspect/zoom/interpolation metadata, and cursor-to-original-source coordinate reporting.
- `tests/test_gui_base_views.py` adds offscreen GUI coverage for axis/index control state, linked-slice and raw/display labels, bounded-read bytes/scope metadata, and high-dimensional cursor coordinate mapping through fixed and displayed axes.
- `CHANGELOG.md` records the new DV-0806 workspace view behavior.
- `tasks/todo.md` marks DV-0806 complete after local verification and successful Windows/Ubuntu CI.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing slice navigator tests | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | failed as expected before implementation: `MultidimensionalSliceNavigatorWidget` could not be imported |
| Focused base view tests | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | 7 passed |
| GUI regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py tests\test_gui_shell.py tests\test_gui_i18n_accessibility.py tests\test_gui_state_components.py -q` | 36 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui\views.py tests\test_gui_base_views.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 100 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_gui_base_views.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 476 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| Initial GitHub Actions run | `gh run view 29387036554 --json status,conclusion,headSha,jobs,url` | failed in Windows/Ubuntu type-check for head SHA `97587ab3676898b7ec6a0c600f414de01e1dd3e4`; fixed by `00722c8261a08ee3083311d96fd15d0d072c8004` after guarding nullable Qt layout items |
| GitHub Actions run | `gh run view 29387169818 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `00722c8261a08ee3083311d96fd15d0d072c8004`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29387169818 |
| Windows quality | GitHub Actions job `87262742621` | success; started `2026-07-15T03:42:10Z`, completed `2026-07-15T03:44:11Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Ubuntu quality | GitHub Actions job `87262742625` | success; started `2026-07-15T03:42:10Z`, completed `2026-07-15T03:43:46Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Concrete Qt plot rendering, correlation heatmap, missing-data map, NIfTI orthogonal viewer, and full shell wiring for advanced linked slice interactions remain later P8 tasks.

## DV-0807 Correlation heatmap and missing-data map plugins - 2026-07-15

Revision: implementation commit `086fcdd6ba1b9743212f1510faccf8241b5df4cc`.

Implementation evidence:

- `data_viewer/plugins/builtin/plots/plugin.py` adds `CorrelationHeatmapPlugin` and `MissingDataMapPlugin`. Both produce renderer-owned heatmap `PlotSpec` results with labeled coordinates, optional finite heatmap intensity values, exportable data-table metadata, and no GUI/Matplotlib ownership inside plugin code.
- `data_viewer/plugins/results.py` extends `PlotMark` with optional finite `values` matching `x`/`y` length, preserving existing line/scatter/histogram/box construction while allowing heatmap cell intensities.
- `data_viewer/plugins/builtin/correlation_heatmap/plugin.json` and `data_viewer/plugins/builtin/missing_data_map/plugin.json` add independent packaged built-in visualization manifests. `pyproject.toml` includes both manifests in package data.
- `docs/PLUGIN_API.md` documents the optional heatmap values channel and the concrete DV-0807 catalog behavior.
- `tests/test_builtin_heatmap_plugins.py` covers packaged discovery, labeled correlation heatmap value/range/legend/table metadata, missing-data map deterministic observation sampling and 0/1 legend semantics, and forbidden-import boundaries.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing heatmap plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_heatmap_plugins.py -q` | failed as expected before implementation: heatmap plugin manifests were not discovered |
| Focused heatmap plugin tests | `venv\Scripts\python.exe -m pytest tests\test_builtin_heatmap_plugins.py -q` | 4 passed |
| Plugin P7/P8 regression subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_heatmap_plugins.py tests\test_builtin_plot_plugins.py tests\test_builtin_correlation_covariance_plugin.py tests\test_plugin_results.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py -q` | 48 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\plugins tests\conformance\plugin.py tests\test_builtin_heatmap_plugins.py tests\test_builtin_plot_plugins.py tests\test_plugin_results.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer\plugins tests\test_builtin_heatmap_plugins.py tests\test_builtin_plot_plugins.py tests\test_plugin_results.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 100 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 480 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for `correlation_heatmap/plugin.json`, `missing_data_map/plugin.json`, and `data_viewer/plugins/builtin/plots/plugin.py` | wheel built successfully; required files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29387945897 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `086fcdd6ba1b9743212f1510faccf8241b5df4cc`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29387945897 |
| Ubuntu quality | GitHub Actions job `87265016663` | success; started `2026-07-15T04:01:35Z`, completed `2026-07-15T04:03:08Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87265016664` | success; started `2026-07-15T04:01:35Z`, completed `2026-07-15T04:03:32Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- NIfTI orthogonal viewer, result renderer widgets, and final P8 plugin catalog evidence remain later tasks.

## DV-0808 NIfTI orthogonal viewer and inspector - 2026-07-15

Revision: implementation commit `fba69cda8cbeaed68c8c0a5ecc9e8ddef15c3e24`.

Implementation evidence:

- `data_viewer/gui/views.py` adds `NiftiOrthogonalViewerWidget`, a bounded `VolumePayload` workspace view with axial/coronal/sagittal orientation labels, linked crosshair metadata, voxel-to-world affine projection, 4D volume/time index status, display-only window/level state, explicit no-resampling status, and a read-only affine/spatial inspector.
- The widget consumes already-bounded `VolumePayload` instances and does not open NIfTI files, access NiBabel proxies, infer active resources from GUI fields, or resample source data.
- `tests/test_gui_base_views.py` adds offscreen GUI coverage for known affine voxel/world coordinates, RAS/LPI orientation labels, 4D volume index display, scaled/display value semantics, window/level labels, and affine/header inspector text.
- `CHANGELOG.md` and `docs/PLUGIN_API.md` update the user-visible state and P8 remaining-work language.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing NIfTI viewer tests | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | failed as expected before implementation: `NiftiOrthogonalViewerWidget` could not be imported |
| Focused base view tests | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py -q` | 9 passed |
| GUI/NIfTI regression subset | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py tests\test_nifti_adapter.py tests\test_gui_shell.py tests\test_gui_i18n_accessibility.py -q` | 39 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\gui\views.py tests\test_gui_base_views.py tests\test_nifti_adapter.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_gui_base_views.py tests\test_nifti_adapter.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 100 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 482 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29388571926 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `fba69cda8cbeaed68c8c0a5ecc9e8ddef15c3e24`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29388571926 |
| Ubuntu quality | GitHub Actions job `87266834075` | success; started `2026-07-15T04:16:17Z`, completed `2026-07-15T04:17:50Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87266834088` | success; started `2026-07-15T04:16:18Z`, completed `2026-07-15T04:18:22Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-0809 still needs final Checkpoint 8 catalog evidence. Deeper renderer integration can continue in later UI tasks.

## DV-0809 Checkpoint 8 plugin catalog evidence - 2026-07-15

Revision: documentation-only checkpoint ledger update over baseline head `09f2b34b23fb60c19333ac7da649af5d7f2f430d`.

Checkpoint scope:

- P8 statistics/analysis catalog completed: Dataset Profile, Descriptive Statistics, Distribution Summary, Correlation/Covariance, and Dataset Compare.
- P8 visualization/catalog views completed: line, scatter, histogram, box, multidimensional slice navigator, correlation heatmap, missing-data map, and NIfTI orthogonal viewer/inspector.
- All P8 catalog entries keep renderer/application ownership boundaries: plugins return declarative result payloads and metadata; GUI views consume bounded payloads and do not own source handles.
- Sampling is explicit for distribution, plot, and missing-data map paths; result provenance records sampled/full status.
- Large-input boundaries are covered through chunked `InputAccess`, variable-count budgets, point/observation sampling, result materialization budgets, and NIfTI bounded proxy reads.

Checkpoint local evidence:

| Evidence area | Command/source | Observed result |
|---|---|---|
| Latest full local suite | `venv\Scripts\python.exe -m pytest -q` | 482 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Latest target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 100 source files |
| Latest focused P8 heatmap subset | `venv\Scripts\python.exe -m pytest tests\test_builtin_heatmap_plugins.py tests\test_builtin_plot_plugins.py tests\test_builtin_correlation_covariance_plugin.py tests\test_plugin_results.py tests\test_plugin_registry.py tests\test_plugin_compatibility_parameters.py tests\test_plugin_runner.py -q` | 48 passed |
| Latest focused GUI/NIfTI subset | `venv\Scripts\python.exe -m pytest tests\test_gui_base_views.py tests\test_nifti_adapter.py tests\test_gui_shell.py tests\test_gui_i18n_accessibility.py -q` | 39 passed |
| Latest wheel/package smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; inspect wheel with `zipfile`; remove `.tmp-wheel` | required P8 plugin manifests and modules present when checked during DV-0805 and DV-0807 |

Checkpoint dual-platform evidence:

| Check | Command/source | Observed result |
|---|---|---|
| Final pre-checkpoint GitHub Actions run | `gh run view 29388764156 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `09f2b34b23fb60c19333ac7da649af5d7f2f430d`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29388764156 |
| Ubuntu quality | GitHub Actions job `87267404774` | success; started `2026-07-15T04:21:07Z`, completed `2026-07-15T04:22:38Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87267404805` | success; started `2026-07-15T04:21:08Z`, completed `2026-07-15T04:23:17Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Checkpoint status:

- `tasks/todo.md` marks DV-0801 through DV-0809 complete.
- Checkpoint 8 exits with no known Critical or Required review issue recorded in this report.
- Remaining work moves to P9 workspace, comparison, and usability tasks.

## DV-0901 Workspace schema/model/deterministic atomic save-load - 2026-07-15

Revision: implementation commit `2528087adcedc895aec3c7fbe57e7ff7a9ff4cd8`.

Implementation evidence:

- `data_viewer/workspace/manifest.py` adds `WorkspaceManifest`, `WorkspaceSource`, `WorkspaceView`, `WorkspaceService`, and explicit validation/version exceptions for Workspace Format v1.
- `data_viewer/workspace/schema/workspace-v1.schema.json` adds the packaged public JSON Schema resource; `pyproject.toml` includes it as package data.
- Workspace serialization is deterministic UTF-8 JSON with two-space indentation, sorted keys, and a trailing newline.
- Workspace loading enforces byte/depth budgets, rejects forbidden executable/credential/bulk-data keys before restore, preserves unknown JSON-safe fields, and protects newer unsupported schema versions from overwrite.
- Workspace saving uses `AtomicReplacementService`; failed saves leave the previous `.dvw` file unchanged. Runtime source dirty and workspace dirty flags are independent and are not serialized as scientific source state.
- `tests/test_workspace_manifest.py` covers minimal schema load, deterministic unknown-preserving round trip, relative/absolute path resolution, newer-version/security/budget rejection, and atomic save failure behavior.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing workspace tests | `venv\Scripts\python.exe -m pytest tests\test_workspace_manifest.py -q` | failed as expected before implementation: `data_viewer.workspace` module was missing |
| Focused workspace tests | `venv\Scripts\python.exe -m pytest tests\test_workspace_manifest.py -q` | 5 passed |
| Workspace/persistence/config subset | `venv\Scripts\python.exe -m pytest tests\test_workspace_manifest.py tests\test_persistence_transaction.py tests\test_infrastructure_config.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\workspace tests\test_workspace_manifest.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_workspace_manifest.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 103 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 487 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Wheel package-data smoke | `venv\Scripts\python.exe -m pip wheel . -w .tmp-wheel --no-deps --no-build-isolation --no-cache-dir`; then inspect wheel with `zipfile` for `data_viewer/workspace/manifest.py` and `data_viewer/workspace/schema/workspace-v1.schema.json` | wheel built successfully; required workspace files present; temporary `.tmp-wheel` removed |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29389566562 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `2528087adcedc895aec3c7fbe57e7ff7a9ff4cd8`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29389566562 |
| Windows quality | GitHub Actions job `87269791873` | success; started `2026-07-15T04:41:19Z`, completed `2026-07-15T04:43:34Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Ubuntu quality | GitHub Actions job `87269791876` | success; started `2026-07-15T04:41:18Z`, completed `2026-07-15T04:43:17Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-0902 still owns asynchronous restore, relocation, degraded mode, and current-file status classification.

## DV-0902 Asynchronous restore, relocation, and degraded mode - 2026-07-15

Revision: implementation commit `163aad0b930bfea4ceba0739c44b768a53258cd9`.

Implementation evidence:

- `data_viewer/workspace/restore.py` adds `WorkspaceRestoreCoordinator`, explicit source restore states, view-shell restore states, plugin-result freshness states, and a `WorkspaceRestorePlan` degraded-mode model for UI consumption.
- Restore planning resolves persisted source paths without mutating the manifest and classifies available, missing, changed, moved-candidate, ambiguous, unsupported, and failed sources independently.
- Relocation matching is bounded to user-provided replacement roots and uses basename plus persisted fingerprint hints (`size`/`size_bytes`, `mtime_ns`/`modified_time_ns`, and `prefix_sha256`). Ambiguous matches are reported; no source path is changed until `apply_confirmed_relocations(...)` receives an explicit source-ID confirmation.
- View shells are restored before metadata and payload reads. Available sources produce pending payload shells; unavailable sources produce blocked shells while preserving original source/resource identity.
- Persisted plugin results are marked stale when an input source is unavailable or its current fingerprint differs from the stored input fingerprint.
- `plan_restore_async(...)` runs the same restore contract asynchronously and honors cooperative cancellation before and during relocation scanning, including non-ASCII relative paths.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing workspace restore tests | `venv\Scripts\python.exe -m pytest tests\test_workspace_restore.py -q` | failed as expected before implementation: `data_viewer.workspace.restore` module was missing |
| Focused restore tests | `venv\Scripts\python.exe -m pytest tests\test_workspace_restore.py -q` | 4 passed |
| Workspace/persistence regression subset | `venv\Scripts\python.exe -m pytest tests\test_workspace_restore.py tests\test_workspace_manifest.py tests\test_persistence_transaction.py -q` | 26 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\workspace tests\test_workspace_restore.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_workspace_restore.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 104 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 491 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29390259329 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `163aad0b930bfea4ceba0739c44b768a53258cd9`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29390259329 |
| Ubuntu quality | GitHub Actions job `87271930467` | success; started `2026-07-15T04:58:31Z`, completed `2026-07-15T05:00:01Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87271930481` | success; started `2026-07-15T04:58:31Z`, completed `2026-07-15T05:00:24Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Interactive Locate/Locate Folder dialogs and session auto-restore policy remain later P9 tasks. DV-0902 provides the restore/degraded state model those UI surfaces will consume.

## DV-0903 Comparison domain and workspace - 2026-07-15

Revision: implementation commit `b1975e99b74b89b370123bb9cef2f6af63e84a39`.

Implementation evidence:

- `data_viewer/app/compare.py` adds comparison-side identity, explicit alignment policies, difference modes, compatibility decisions, Qt-free view state, workspace serialization, and restore-error reporting.
- Array comparison state validates metadata before payload work and refuses implicit broadcasting for mismatched shapes.
- Table comparison state requires explicit non-duplicated left/right column matches and rejects unknown columns.
- Comparison workspace entries persist left/right source/resource identity, shape, dtype, fingerprint provenance, alignment mode, difference mode, linked-navigation state, compatibility status, and optional result ID.
- Invalid comparison entries degrade independently during workspace restore through `ComparisonRestoreError` and do not abort valid workspace content.
- The existing Dataset Compare plugin remains the numerical metric engine; DV-0903 owns comparison state, alignment contracts, and workspace persistence.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing comparison tests | `venv\Scripts\python.exe -m pytest tests\test_comparison_workspace.py -q` | failed as expected before implementation: `data_viewer.app.compare` module was missing |
| Focused comparison tests | `venv\Scripts\python.exe -m pytest tests\test_comparison_workspace.py -q` | 5 passed |
| Comparison/plugin/workspace subset | `venv\Scripts\python.exe -m pytest tests\test_comparison_workspace.py tests\test_builtin_dataset_compare_plugin.py tests\test_workspace_manifest.py tests\test_workspace_restore.py -q` | 19 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app\compare.py data_viewer\app\__init__.py tests\test_comparison_workspace.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_comparison_workspace.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 105 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 496 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29391043119 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `b1975e99b74b89b370123bb9cef2f6af63e84a39`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29391043119 |
| Ubuntu quality | GitHub Actions job `87274420418` | success; started `2026-07-15T05:16:49Z`, completed `2026-07-15T05:18:33Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87274420387` | success; started `2026-07-15T05:16:50Z`, completed `2026-07-15T05:18:54Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Full interactive comparison widgets and deeper visual diff rendering remain future UI slices. DV-0903 supplies the validated domain/controller/view-state contract and workspace persistence.

## DV-0904 Recent, pinned, favorites, history, and global search - 2026-07-15

Revision: implementation commit `08ed8340335fea7be30304f80aa07223578da5e5`.

Implementation evidence:

- `data_viewer/app/navigation.py` adds Qt-free models and `NavigationService` for recent files, pinned recent files, resource favorites, semantic back/forward history, missing-recent remediation, and grouped global search.
- Recent and pinned file state is serialized as application configuration via `to_app_config()` and is intentionally kept out of `.dvw` workspace manifests.
- Resource favorites use `(source_id, resource_path)` identity; display labels are mutable presentation and do not define identity.
- `NavigationHistory` stores semantic source/resource/view/split targets so Back and Forward restore active split/resource intent instead of widget focus.
- `SearchQuery` supports path text, name text, domain, dtype substring, exact shape, and optional regular-expression matching. Results are grouped by resource domain.
- Search validates regular expressions up front and honors cooperative cancellation with `TASK_CANCELLED`.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing navigation/search tests | `venv\Scripts\python.exe -m pytest tests\test_navigation_search.py -q` | failed as expected before implementation: `data_viewer.app.navigation` module was missing |
| Focused navigation/search tests | `venv\Scripts\python.exe -m pytest tests\test_navigation_search.py -q` | 5 passed |
| Navigation/comparison/workspace subset | `venv\Scripts\python.exe -m pytest tests\test_navigation_search.py tests\test_comparison_workspace.py tests\test_workspace_manifest.py -q` | 15 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app\navigation.py data_viewer\app\__init__.py tests\test_navigation_search.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_navigation_search.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 106 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 501 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29391772848 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `08ed8340335fea7be30304f80aa07223578da5e5`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29391772848 |
| Ubuntu quality | GitHub Actions job `87276624485` | success; started `2026-07-15T05:33:52Z`, completed `2026-07-15T05:35:29Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87276624320` | success; started `2026-07-15T05:33:53Z`, completed `2026-07-15T05:36:02Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Full Qt navigation rail/search/favorites panels remain later UI integration work. DV-0904 supplies the validated application state and search contract.

## DV-0905 Session restore and external file change detection - 2026-07-15

Revision: implementation commit `0a96af5c22a749be26217c640f7d686a7a5be891`.

Implementation evidence:

- `data_viewer/app/session_restore.py` adds Qt-free session restore policy and startup decision models for last-workspace pointers, clean shutdowns, missing manifests, restart, and crash-recovery handling.
- Session restore records only application-level recovery state and returns safe decisions before any previous workspace is opened.
- `ExternalChangeDetector` classifies unchanged, changed, replaced, deleted, and self-save watcher events against source fingerprints.
- Dirty patch state is fail-closed: external changes never trigger a normal reload, and only explicit discard, Save As, or cancel decisions are allowed.
- Self-save events update the trusted baseline fingerprint and suppress false external-conflict reports.
- `docs/WORKSPACE_FORMAT.md` and `docs/SAFE_EDITING.md` document the restore pointer, startup behavior, watcher event decisions, and v1 non-goals.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing session-restore tests | `venv\Scripts\python.exe -m pytest tests\test_session_restore.py -q` | failed as expected before implementation: `data_viewer.app.session_restore` module was missing |
| Focused session-restore tests | `venv\Scripts\python.exe -m pytest tests\test_session_restore.py -q` | 6 passed |
| Session/document/workspace subset | `venv\Scripts\python.exe -m pytest tests\test_session_restore.py tests\test_document_controller.py tests\test_workspace_restore.py tests\test_workspace_manifest.py -q` | 23 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app\session_restore.py data_viewer\app\__init__.py tests\test_session_restore.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_session_restore.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 107 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 507 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29392521329 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `0a96af5c22a749be26217c640f7d686a7a5be891`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29392521329 |
| Ubuntu quality | GitHub Actions job `87278903267` | success; started `2026-07-15T05:50:52Z`, completed `2026-07-15T05:52:29Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87278903301` | success; started `2026-07-15T05:50:57Z`, completed `2026-07-15T05:53:12Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Full Qt startup prompt, native file watcher wiring, and user-visible reload/Save As/cancel dialogs remain later UI integration work. DV-0905 supplies the validated restore and external-change decision contracts those surfaces will consume.

## DV-0906 Background export queue and Diagnostics - 2026-07-15

Revision: implementation commit `305b3139cf19022ee59c55fdaee8479a35ff797c`.

Implementation evidence:

- `data_viewer/app/export_queue.py` adds an application export queue that wraps reviewed `ExportPlan` values in `TaskRecord` lifecycle state, tracks progress, supports queued cancellation, stores export receipt history, and retries failed/cancelled jobs as new attempts.
- Failed queued exports create `ExportProblem` links with task ID, target path, source URI, resource path, structured error code, and safe message for Problems-panel routing.
- `data_viewer/app/diagnostics.py` now includes `PluginInventoryItem`, `DiagnosticsBundle`, and `DiagnosticsBundleService` for user-previewable diagnostics bundles.
- Diagnostics bundles include application/runtime/platform version fields, plugin inventory, recent diagnostic events, optional task records, and configured path redaction before preview/export.
- `ARCHITECTURE.md`, `docs/SAFE_EDITING.md`, and `CHANGELOG.md` document the implemented queue, receipt, retry, Problems, and diagnostics-preview behavior.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing export queue/diagnostics tests | `venv\Scripts\python.exe -m pytest tests\test_export_queue_diagnostics.py -q` | failed as expected before implementation: `DiagnosticsBundleService` and `ExportQueueService` were missing |
| Focused export queue/diagnostics tests | `venv\Scripts\python.exe -m pytest tests\test_export_queue_diagnostics.py -q` | 4 passed |
| Export/diagnostics/task subset | `venv\Scripts\python.exe -m pytest tests\test_export_queue_diagnostics.py tests\test_exporting.py tests\test_error_diagnostics.py tests\test_task_lifecycle.py -q` | 27 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app\export_queue.py data_viewer\app\diagnostics.py data_viewer\app\__init__.py tests\test_export_queue_diagnostics.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_export_queue_diagnostics.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 108 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 511 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29393299377 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `305b3139cf19022ee59c55fdaee8479a35ff797c`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29393299377 |
| Ubuntu quality | GitHub Actions job `87281186180` | success; started `2026-07-15T06:07:27Z`, completed `2026-07-15T06:09:14Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87281186161` | success; started `2026-07-15T06:07:28Z`, completed `2026-07-15T06:09:46Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- Full Qt Tasks/Problems/Diagnostics panels and native background executor wiring remain later UI integration work. DV-0906 supplies the validated app-layer queue, receipt history, Problems link, retry, and diagnostics bundle contracts those surfaces will consume.

## DV-0907 Checkpoint 9 workbench evidence - 2026-07-15

Revision: documentation-only checkpoint ledger update over baseline head `d14e36179d0e2ede2b58c6918c6431e90b1241be`.

Checkpoint scope:

- P9 workspace foundation completed: `.dvw` schema/model/save-load service, source restore planner, relocation/degraded-state decisions, session restore policy, and external change detection.
- P9 comparison/usability foundation completed: comparison workspace state, compatibility contracts, semantic navigation history, recent/pinned/favorite state, global search contracts, background export queue, Problems links, and diagnostics bundle preview/redaction.
- Workspace manifests remain external-reference based and do not embed large source data. Application-local usability state such as recent files, pinned files, and last-workspace restore pointer remains outside `.dvw` manifests.
- Comparison, search, restore, export, and diagnostics logic is Qt-free application state that later UI surfaces can consume without scanning widget internals.
- Dirty edits and external changes remain fail-closed: session restore does not auto-open unsafe state, dirty patches do not auto-overwrite changed sources, and queued exports use reviewed plans plus terminal receipts.

Checkpoint local evidence:

| Evidence area | Command/source | Observed result |
|---|---|---|
| Latest full local suite | `venv\Scripts\python.exe -m pytest -q` | 511 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Latest target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 108 source files |
| Focused P9 workbench matrix | `venv\Scripts\python.exe -m pytest tests\test_workspace_manifest.py tests\test_workspace_restore.py tests\test_comparison_workspace.py tests\test_navigation_search.py tests\test_session_restore.py tests\test_export_queue_diagnostics.py -q` | 29 passed |

Checkpoint dual-platform evidence:

| Check | Command/source | Observed result |
|---|---|---|
| Final pre-checkpoint GitHub Actions run | `gh run view 29393535798 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `d14e36179d0e2ede2b58c6918c6431e90b1241be`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29393535798 |
| Ubuntu quality | GitHub Actions job `87281904343` | success; started `2026-07-15T06:12:35Z`, completed `2026-07-15T06:14:30Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87281904354` | success; started `2026-07-15T06:12:36Z`, completed `2026-07-15T06:15:06Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Checkpoint status:

- `tasks/todo.md` marks DV-0901 through DV-0907 complete.
- Checkpoint 9 exits with no known Critical or Required review issue recorded in this report.
- Remaining work moves to P10 hardening, packaging, smoke validation, and release tasks.

## DV-1001 Performance, memory, and cache budget harness - 2026-07-15

Revision: implementation commit `3331aba4fba1f9fe3b24776850fec75fcc6f90d9` plus CI-stability fix `12929edac5f140674341a2f4db42e25d7531f12d`.

Implementation evidence:

- `data_viewer/performance/__init__.py` adds release-budget metric names, benchmark reports with median/p95/peak traced memory, path-free platform profiles, synthetic dataset generators, optional budget thresholds, and structured budget evaluations.
- `tools/run_performance_baseline.py` emits reproducible JSON Phase 0 baseline reports for all Testing §11 metric categories: cold launch, metadata open, many-child expansion, first table page, table scroll, 2D slice, NIfTI plane proxy, cancellation latency, repeated open/close allocation delta, gzip extraction, and plugin chunk throughput.
- `docs/PERFORMANCE_BUDGETS.md` documents the two-step budget policy: collect Windows/Linux baselines first, then encode numeric thresholds with cited evidence.
- `docs/INDEX.md` routes future performance/hardening work to the budget document.
- Ubuntu CI initially exposed a platform-specific test assumption: empty callbacks may record zero traced peak memory on Linux. Commit `12929edac5f140674341a2f4db42e25d7531f12d` fixed the test to allocate deterministically before asserting peak-memory threshold violations.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing performance-budget tests | `venv\Scripts\python.exe -m pytest tests\test_performance_budgets.py -q` | failed as expected before implementation: `data_viewer.performance` module was missing |
| Focused performance-budget tests | `venv\Scripts\python.exe -m pytest tests\test_performance_budgets.py -q` | 6 passed |
| Baseline script smoke | `venv\Scripts\python.exe tools\run_performance_baseline.py --iterations 2 --warmups 0 --rows 8 --columns 4 --hierarchy-depth 2 --fanout 3` | emitted JSON reports for all 11 release-budget metrics with median/p95/peak memory and Windows platform profile |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\performance tests\test_performance_budgets.py tools\run_performance_baseline.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_performance_budgets.py tools\run_performance_baseline.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 109 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 517 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after fix:

| Check | Command/source | Observed result |
|---|---|---|
| Failed implementation GitHub Actions run | `gh run view 29394576463 --json status,conclusion,headSha,jobs,url` | failed on Ubuntu for head SHA `3331aba4fba1f9fe3b24776850fec75fcc6f90d9`; root cause was a platform-specific zero-peak-memory assumption in `tests/test_performance_budgets.py` |
| Successful GitHub Actions run | `gh run view 29394863661 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `12929edac5f140674341a2f4db42e25d7531f12d`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29394863661 |
| Ubuntu quality | GitHub Actions job `87285952690` | success; started `2026-07-15T06:39:48Z`, completed `2026-07-15T06:41:35Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87285952707` | success; started `2026-07-15T06:39:49Z`, completed `2026-07-15T06:41:45Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-1001 establishes Phase 0 synthetic/runtime probes and threshold plumbing. Later P10/P11 package-smoke and stress tasks must add artifact-level probes against real HDF5, CSV, NIfTI, gzip, workspace, and plugin fixtures before release thresholds are finalized.

## DV-1002 Stress, leak, and adversarial hardening suite - 2026-07-15

Revision: implementation commit `ce91a891bfb0e62043e3d4e8298b11939f5ae655`.

Implementation evidence:

- `tests/test_hardening_stress.py` adds retained stress/security coverage for many queued exports, rapid navigation cancellation, adversarial workspace nesting, and gzip extraction budget cleanup.
- `ExportQueueService` now exposes retained task count for diagnostics/tests and releases successful task records and payload references after terminal receipts are stored, preventing many successful exports from accumulating retained task payloads.
- Rapid navigation search is verified to honor cooperative cancellation without returning partial grouped results.
- Deep malicious workspace manifests fail through structured `WorkspaceValidationError` nesting-budget checks rather than unbounded recursion.
- Gzip decompression budget failures are verified to remove abandoned `.incomplete` cache files.
- `docs/PERFORMANCE_BUDGETS.md` records the current DV-1002 stress coverage and remaining packaged/runtime stress extensions.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing hardening stress tests | `venv\Scripts\python.exe -m pytest tests\test_hardening_stress.py -q` | failed as expected before implementation: `ExportQueueService.retained_task_count` was missing and successful jobs were retained |
| Focused hardening/export regression tests | `venv\Scripts\python.exe -m pytest tests\test_hardening_stress.py tests\test_export_queue_diagnostics.py -q` | 8 passed |
| Hardening/navigation/gzip/workspace subset | `venv\Scripts\python.exe -m pytest tests\test_hardening_stress.py tests\test_export_queue_diagnostics.py tests\test_navigation_search.py tests\test_gzip_adapter.py tests\test_workspace_manifest.py -q` | 25 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\app\export_queue.py tests\test_hardening_stress.py` | passed |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_hardening_stress.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 109 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 521 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29395715609 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `ce91a891bfb0e62043e3d4e8298b11939f5ae655`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29395715609 |
| Ubuntu quality | GitHub Actions job `87288637836` | success; started `2026-07-15T06:56:31Z`, completed `2026-07-15T06:58:05Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87288637859` | success; started `2026-07-15T06:56:31Z`, completed `2026-07-15T06:59:19Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-1002 retained logs are currently the GitHub Actions logs/artifacts plus `TEST_REPORT.md` evidence. Later package-smoke and release-candidate tasks should retain artifact-level stress logs for real packaged open/close loops and representative fixture workflows.

## DV-1003 Data Viewer name and canonical version migration - 2026-07-15

Revision: implementation commit `e9e6d2779782574b4efe3f6ddc7ee676f3b4593b`.

Implementation evidence:

- `WorkspaceManifest.app["version"]` now reads the canonical package `data_viewer.__version__` value instead of a hard-coded release string.
- `tests/test_data_viewer_package.py` verifies workspace app metadata, target package runtime surfaces, and repository-wide old-name references.
- Current target package/bootstrap/workspace surfaces use `Data Viewer`; remaining `HDF5 Viewer`, `HDF5Viewer`, and `hdf5viewer` occurrences are constrained to explicit legacy, historical, migration, or rejected-decision contexts.
- Legacy root scripts, old PyInstaller spec, old GUI entrypoint, and legacy tests retain their historical names only with explicit legacy labeling.
- Git tags were not modified.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Focused package/name/version tests | `venv\Scripts\python.exe -m pytest tests\test_data_viewer_package.py -q` | 7 passed |
| Workspace/UI related subset | `venv\Scripts\python.exe -m pytest tests\test_data_viewer_package.py tests\test_workspace_manifest.py tests\test_gui_i18n_accessibility.py -q` | 20 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\workspace\manifest.py tests\test_data_viewer_package.py build.py build_windows.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 109 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests build.py build_windows.py main.py gui` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 524 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Case-sensitive old-name scan | `rg -n "HDF5 Viewer|HDF5Viewer|hdf5viewer" . -g "!venv/**" -g "!.git/**" -g "!.hypothesis/**" -g "!.pytest_cache/**" -g "!.mypy_cache/**" -g "!.ruff_cache/**" -g "!htmlcov/**" -g "!build/**" -g "!dist/**" -g "!*.pyc" -g "!*.zip" -g "!*.png" -g "!*.svg"` | remaining matches were legacy, historical, migration, or rejected-decision contexts |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29397644108 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `e9e6d2779782574b4efe3f6ddc7ee676f3b4593b`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29397644108 |
| Ubuntu quality | GitHub Actions job `87294666727` | success; started `2026-07-15T07:31:42Z`, completed `2026-07-15T07:33:34Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87294666711` | success; started `2026-07-15T07:31:42Z`, completed `2026-07-15T07:33:51Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-1003 intentionally labels rather than deletes legacy GUI/build entrypoints. DV-1004 through DV-1008 own platform config migration, Data Viewer artifact builds, installed smoke validation, release assembly, and final legacy removal.

## DV-1004 Platform configuration migration - 2026-07-15

Revision: implementation commit `36aa5675fe31cffbbd6d34c8c2d6477808b2bc1a`.

Implementation evidence:

- `AppConfig` now includes versioned UI preferences for theme, sidebar width, secondary panel width, and secondary panel visibility.
- `data_viewer.infrastructure.config_migration` previews and explicitly applies legacy repository `config.json` migration without modifying or deleting the legacy file.
- Legacy migration maps known UI keys, reports unknown keys as warnings, rejects corrupt legacy JSON safely, supports explicit decline, and blocks stale legacy config from overwriting an existing target config.
- Target bootstrap now prepares platform config/cache/log paths through `platformdirs`, loads target config, and creates a legacy migration preview by default without silently writing repository config.
- `docs/CONFIGURATION.md` records target config schema, platform locations, test overrides, and legacy migration rules.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial failing config migration tests | `venv\Scripts\python.exe -m pytest tests\test_infrastructure_config.py -q` | failed as expected before implementation: `UIConfig` and `prepare_runtime_configuration` were missing |
| Config/path/package subset | `venv\Scripts\python.exe -m pytest tests\test_infrastructure_config.py tests\test_infrastructure_paths.py tests\test_data_viewer_package.py -q` | 21 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\infrastructure data_viewer\gui\app.py tests\test_infrastructure_config.py tests\test_infrastructure_paths.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py` | passed; no issues in 110 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 531 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29398823919 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `36aa5675fe31cffbbd6d34c8c2d6477808b2bc1a`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29398823919 |
| Ubuntu quality | GitHub Actions job `87298417557` | success; started `2026-07-15T07:52:49Z`, completed `2026-07-15T07:55:02Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |
| Windows quality | GitHub Actions job `87298417561` | success; started `2026-07-15T07:52:50Z`, completed `2026-07-15T07:55:29Z`; full offscreen regression suite, lint, type check, compile, and package build steps passed |

Known gaps:

- DV-1004 prepares and tests the non-destructive migration machinery. A later UI task should surface the migration preview/decision to users instead of applying migration automatically, and DV-1008 still owns final legacy config write removal from the old GUI path.

## DV-1005 Windows and Linux Data Viewer artifacts - 2026-07-15

Revision: implementation commit `931583060a486c7e2217c43419e145561239e13e`.

Implementation evidence:

- `packaging/DataViewer.spec` builds the target `DataViewer` PyInstaller bundle through `tools/pyinstaller_entry.py`.
- `tools/build_pyinstaller_artifact.py` creates platform-specific archives named `DataViewer-<version>-windows-x86_64.zip` and `DataViewer-<version>-linux-x86_64.tar.gz`, plus `pyinstaller-manifest.json`.
- The CI quality workflow now builds the PyInstaller artifact after locked install, lint, type-check, compile, full regression tests, and wheel/sdist build.
- `.github/scripts/smoke_pyinstaller_artifact.py` runs the packaged executable with `--version` on both platforms before package artifact upload.
- `tests/test_packaging_artifacts.py` guards current product naming, platform-specific artifact naming, executable names, and CI packaging steps.
- `RELEASE.md` documents the package artifact upload names and manifest layout.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial packaging contract tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py -q` | failed as expected before implementation because `tools.build_pyinstaller_artifact` did not exist |
| Packaging/name subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_data_viewer_package.py -q` | 10 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tools .github\scripts tests\test_packaging_artifacts.py tests\test_data_viewer_package.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py .github\scripts\smoke_pyinstaller_artifact.py tools\build_pyinstaller_artifact.py` | passed; no issues in 112 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tools core gui plugins services utils main.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 534 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Local PyInstaller build attempt | `venv\Scripts\python.exe tools\build_pyinstaller_artifact.py --output-dir artifacts\local-package` | blocked by local mixed conda/venv PyInstaller hook pollution: imported `hook-numpy.py` from the historical legacy migration environment `C:\Users\Alvin\anaconda3\envs\hdf5viewer_build`; clean CI builds below are authoritative |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29400222068 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `931583060a486c7e2217c43419e145561239e13e`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29400222068 |
| Ubuntu quality | GitHub Actions job `87302819079` | success; started `2026-07-15T08:16:46Z`, completed `2026-07-15T08:21:12Z`; full offscreen regression suite, wheel/sdist build, `Build Data Viewer PyInstaller artifact`, `Smoke-test Data Viewer executable`, and artifact upload passed |
| Windows quality | GitHub Actions job `87302819069` | success; started `2026-07-15T08:16:45Z`, completed `2026-07-15T08:22:45Z`; full offscreen regression suite, wheel/sdist build, `Build Data Viewer PyInstaller artifact`, `Smoke-test Data Viewer executable`, and artifact upload passed |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29400222068/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29400222068-1` (178330685 bytes), `data-viewer-package-Ubuntu-29400222068-1` (218842324 bytes), plus matching quality evidence artifacts |

Known gaps:

- DV-1005 proves clean CI artifact construction and packaged `--version` launch smoke. DV-1006 owns richer installed-artifact functional workflows for opening representative HDF5/CSV/NIfTI/gzip/workspace data, running plugins, exporting, screenshots/logs, and release-chain blocking.
- DV-1007 owns checksums, SBOM, license notices, security evidence, and path/credential leakage review before public release publication.

## DV-1006 installed-artifact functional smoke and release chain - 2026-07-15

Revision: implementation commit `663b80c743dc024eef7633984539890c2347acec`.

Implementation evidence:

- `data_viewer/installed_smoke.py` implements the hidden installed-artifact workflow used by packaged executables through `data-viewer --ci-smoke`.
- The workflow creates representative HDF5, CSV, gzip-wrapped CSV, NIfTI, and `.dvw` workspace fixtures; opens and reads them through the target source registry; runs the packaged `org.dataviewer.dataset_profile` reference plugin; exports the plugin result through `ExportService`; closes all opened documents; and writes `installed-smoke-report.json` plus `installed-smoke-screenshot.png`.
- `.github/scripts/smoke_pyinstaller_artifact.py` still verifies packaged `--version`, and now optionally invokes the functional smoke against the built executable.
- `.github/workflows/ci.yml` runs `Functional smoke installed Data Viewer artifact` after the PyInstaller build and before package artifact upload for both Windows and Ubuntu.
- `.github/workflows/build.yml` keeps release gating dependent on the reusable quality workflow and adds a dry-run tag input for release-candidate evidence.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial installed-smoke contract tests | `venv\Scripts\python.exe -m pytest tests\test_installed_artifact_smoke.py -q` | failed as expected before implementation because `data_viewer.installed_smoke` did not exist |
| Installed-smoke target tests | `venv\Scripts\python.exe -m pytest tests\test_installed_artifact_smoke.py tests\test_packaging_artifacts.py tests\test_data_viewer_package.py -q` | 13 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer .github\scripts tools tests\test_installed_artifact_smoke.py tests\test_packaging_artifacts.py tests\test_data_viewer_package.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py .github\scripts\smoke_pyinstaller_artifact.py tools\build_pyinstaller_artifact.py` | passed; no issues in 113 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tools core gui plugins services utils main.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 537 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29403460120 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `663b80c743dc024eef7633984539890c2347acec`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29403460120 |
| Ubuntu quality | GitHub Actions job `87313221250` | success; started `2026-07-15T09:09:46Z`, completed `2026-07-15T09:14:15Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, `Functional smoke installed Data Viewer artifact`, and artifact uploads passed |
| Windows quality | GitHub Actions job `87313221143` | success; started `2026-07-15T09:09:46Z`, completed `2026-07-15T09:15:14Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, `Functional smoke installed Data Viewer artifact`, and artifact uploads passed |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29403460120/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29403460120-1` (178350340 bytes), `data-viewer-package-Ubuntu-29403460120-1` (218863210 bytes), plus matching quality evidence artifacts containing installed-smoke reports and screenshots |

Known gaps:

- DV-1006 proves installed-artifact functional smoke and release-chain dependency on the reusable quality workflow. DV-1007 still owns checksums, SBOM, license notices, dependency/security evidence, and path/credential leakage review before public binary release.
- The public release workflow remains intentionally blocked until every v1 release gate is complete and the PyQt distribution licensing decision is resolved.

## DV-1007 release evidence automation pre-license slice - 2026-07-15

Revision: implementation commit `bc5a4d105b40d4878790892dc3d53f567567f073`.

Implementation evidence:

- `.github/scripts/generate_release_evidence.py` generates one SHA-256 checksum file per Data Viewer archive, `sbom.json`, `third-party-licenses.txt`, and `release-security-review.json` from the locked CI Python environment without adding a new dependency.
- `.github/workflows/ci.yml` runs release-evidence generation only after the installed-artifact functional smoke passes, then includes checksums, SBOM, notices, and security review files in the package upload artifact.
- `release-security-review.json` records dependency-consistency enforcement, path/credential leak-scan results, and release-blocker findings with owner/expiry.
- Because `docs/DEPENDENCIES.md` still records the PyQt binary distribution decision as unresolved, generated release evidence intentionally reports `release_status: blocked` and the release workflow remains fail-closed.
- `RELEASE.md` documents the expanded package artifact layout and the PyQt licensing fail-closed behavior.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial release-evidence contract tests | `venv\Scripts\python.exe -m pytest tests\test_release_evidence.py -q` | failed as expected before implementation because `.github/scripts/generate_release_evidence.py` did not exist and CI did not generate evidence |
| Release-evidence target tests | `venv\Scripts\python.exe -m pytest tests\test_release_evidence.py -q` | 3 passed |
| Release/package related tests | `venv\Scripts\python.exe -m pytest tests\test_release_evidence.py tests\test_packaging_artifacts.py tests\test_installed_artifact_smoke.py tests\test_data_viewer_package.py -q` | 16 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer .github\scripts tools tests\test_release_evidence.py tests\test_installed_artifact_smoke.py tests\test_packaging_artifacts.py tests\test_data_viewer_package.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py .github\scripts\generate_release_evidence.py .github\scripts\smoke_pyinstaller_artifact.py tools\build_pyinstaller_artifact.py` | passed; no issues in 114 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tools core gui plugins services utils main.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 540 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29405323517 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `bc5a4d105b40d4878790892dc3d53f567567f073`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29405323517 |
| Ubuntu quality | GitHub Actions job `87319262931` | success; started `2026-07-15T09:39:50Z`, completed `2026-07-15T09:44:27Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| Windows quality | GitHub Actions job `87319262875` | success; started `2026-07-15T09:39:52Z`, completed `2026-07-15T09:46:06Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29405323517/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29405323517-1` (178389099 bytes), `data-viewer-package-Ubuntu-29405323517-1` (218894312 bytes), plus matching quality evidence artifacts containing release-evidence files |

Known gaps:

- DV-1007 remains unchecked until the PyQt distribution-license decision is documented as satisfied and the generated evidence is verified from Windows and Linux CI package outputs for the committed revision.

## DV-1008 target CLI legacy fallback removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- `data_viewer.__main__` no longer exposes the removed `--legacy` argument and no longer honors `DATA_VIEWER_LEGACY=1` as a target-bootstrap override.
- The prior explicit legacy path was broken because it attempted to launch `data_viewer/main.py`, which does not exist in the target package.
- `--version` and `--ci-smoke` remain available target CLI surfaces.
- README and changelog wording now describe legacy names as historical or migration references, not as a supported target CLI fallback.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial target CLI regression tests | `venv\Scripts\python.exe -m pytest tests\test_data_viewer_package.py -q` | failed as expected before implementation: `--legacy` attempted to run missing `data_viewer\main.py`, and `DATA_VIEWER_LEGACY=1` bypassed the target bootstrap |
| Target CLI package tests | `venv\Scripts\python.exe -m pytest tests\test_data_viewer_package.py -q` | 8 passed |
| CLI plus installed-smoke scope | `venv\Scripts\python.exe -m pytest tests\test_data_viewer_package.py tests\test_installed_artifact_smoke.py -q` | 11 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer\__main__.py tests\test_data_viewer_package.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer` | passed; no issues in 110 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tools core gui plugins services utils main.py` | passed |
| Manual target version CLI | `venv\Scripts\python.exe -m data_viewer --version` | printed `Data Viewer 1.0.0.dev0` |
| Manual removed legacy CLI | `venv\Scripts\python.exe -m data_viewer --legacy` | failed argument parsing as expected with `unrecognized arguments: --legacy` |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 541 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Removed fallback scan | `rg -n -g "*.md" -g "*.py" -g "*.yml" -- "--legacy|DATA_VIEWER_LEGACY|legacy fallback|legacy-fallback" README.md README_EN.md docs tasks data_viewer tests .github tools packaging` | only the DV-1008 acceptance text and negative regression tests mention removed fallback surfaces |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29408402126 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `4450ac3a557e5937ece32dfd62dae09649bc88d5`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29408402126 |
| Ubuntu quality | GitHub Actions job `87329357125` | success; started `2026-07-15T10:31:09Z`, completed `2026-07-15T10:35:21Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| Windows quality | GitHub Actions job `87329357104` | success; started `2026-07-15T10:31:09Z`, completed `2026-07-15T10:36:22Z`; full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29408402126/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29408402126-1` (178387903 bytes), `data-viewer-quality-Windows-29408402126-1` (179071936 bytes), `data-viewer-package-Ubuntu-29408402126-1` (218882756 bytes), and `data-viewer-quality-Ubuntu-29408402126-1` (219613411 bytes) |

Known gaps:

- This is a safe DV-1008 slice, not full DV-1008 completion. Legacy `main.py`, `core/`, `gui/`, `plugins/`, `services/`, and legacy regression tests remain as migration references until each eligible capability/removal group is proven separately.
- DV-1008 remains unchecked until the remaining legacy capability/removal groups prove no obsolete runtime, test, or build imports and Windows/Linux CI evidence exists for that full removal revision.

## DV-1008 release compile gate legacy-runtime removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- `.github/workflows/ci.yml` renames the compile step to `Compile Data Viewer target paths`.
- The release-facing compile gate now compiles only `data_viewer`, `.github/scripts`, and `tools`.
- Legacy `main.py`, `core/`, `gui/`, `plugins/`, `services/`, and `utils` are no longer part of the release compile gate. They remain covered by the full regression suite until their individual migration/removal groups are proven.
- `tests/test_packaging_artifacts.py` asserts the CI compile gate excludes legacy runtime paths so the release artifact pipeline cannot silently regain a legacy compile dependency.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial compile-gate regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_ci_compile_gate_excludes_legacy_runtime_paths -q` | failed as expected before implementation because the workflow still used `Compile target and legacy compatibility paths` |
| Packaging contract tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py -q` | 4 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py` | passed |
| Target compile scope | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tools` | passed |
| Release/package related tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_release_evidence.py tests\test_installed_artifact_smoke.py tests\test_data_viewer_package.py -q` | 18 passed |
| Release/package scoped lint | `venv\Scripts\python.exe -m ruff check data_viewer .github\scripts tools tests\test_packaging_artifacts.py tests\test_release_evidence.py tests\test_installed_artifact_smoke.py tests\test_data_viewer_package.py` | passed |
| Target type check | `venv\Scripts\python.exe -m mypy data_viewer .github\scripts\write_quality_manifest.py .github\scripts\generate_release_evidence.py .github\scripts\smoke_pyinstaller_artifact.py tools\build_pyinstaller_artifact.py` | passed; no issues in 114 source files |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 542 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29409740527 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `431d50ff1b80eb7846d4dca9c834c62d4e7e88d2`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29409740527 |
| Ubuntu quality | GitHub Actions job `87333725394` | success; started `2026-07-15T10:54:15Z`, completed `2026-07-15T10:58:45Z`; the renamed `Compile Data Viewer target paths` step passed, followed by full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads |
| Windows quality | GitHub Actions job `87333725400` | success; started `2026-07-15T10:54:14Z`, completed `2026-07-15T10:59:19Z`; the renamed `Compile Data Viewer target paths` step passed, followed by full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29409740527/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29409740527-1` (178388543 bytes), `data-viewer-quality-Windows-29409740527-1` (179072849 bytes), `data-viewer-package-Ubuntu-29409740527-1` (218889936 bytes), and `data-viewer-quality-Ubuntu-29409740527-1` (219620899 bytes) |

Known gaps:

- This is a release-gate cleanup slice, not full DV-1008 completion. Legacy runtime packages and historical regression tests remain until their capability groups satisfy the migration removal criteria.

## DV-1008 legacy PyInstaller/build entrypoint removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed obsolete root legacy release entrypoints: `HDF5Viewer.spec`, `build_windows.py`, and `build_windows.bat`.
- Replaced the root `build.py` legacy HDF5 Viewer packager with a small Data Viewer release-build front end that delegates packaging to `tools/build_pyinstaller_artifact.py`.
- `build.py --help` now advertises Data Viewer release artifact behavior and supports `--clean`, `--test`, `--windows`, `--linux`, and `--output-dir`.
- `tests/test_packaging_artifacts.py` asserts the removed legacy entrypoints stay absent and the root build script no longer references the old HDF5Viewer artifact name, old spec, legacy application entrypoint, or old conda build environment.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy-build-entrypoint regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_pyinstaller_build_entrypoints_are_removed -q` | failed as expected before implementation because `HDF5Viewer.spec`, `build_windows.py`, and `build_windows.bat` still existed |
| Packaging contract tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py -q` | 5 passed |
| Build front-end help smoke | `venv\Scripts\python.exe build.py --help` | printed Data Viewer release artifact usage |
| Release/package related tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_data_viewer_package.py tests\test_release_evidence.py tests\test_installed_artifact_smoke.py -q` | 19 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check build.py tools tests\test_packaging_artifacts.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy build.py tools\build_pyinstaller_artifact.py` | passed; no issues in 2 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q build.py tools data_viewer .github\scripts` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 543 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Dual-platform CI verification after commit:

| Check | Command/source | Observed result |
|---|---|---|
| GitHub Actions run | `gh run view 29411328385 --json status,conclusion,headSha,jobs,url` | completed successfully for head SHA `c3bee374825f0c2da4167311be005fa7ac30c2eb`; run URL: https://github.com/alvinloga/HDF5-Viewer/actions/runs/29411328385 |
| Ubuntu quality | GitHub Actions job `87338855742` | success; started `2026-07-15T11:21:16Z`, completed `2026-07-15T11:25:47Z`; lint/type/compile, full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| Windows quality | GitHub Actions job `87338855730` | success; started `2026-07-15T11:21:18Z`, completed `2026-07-15T11:26:29Z`; lint/type/compile, full offscreen regression suite, wheel/sdist build, PyInstaller artifact build, packaged `--version` smoke, installed functional smoke, `Generate release evidence`, and artifact uploads passed |
| GitHub Actions artifacts | `gh api repos/alvinloga/HDF5-Viewer/actions/runs/29411328385/artifacts --jq '.artifacts[] | [.name,.size_in_bytes,.expired] | @tsv'` | uploaded non-expired artifacts `data-viewer-package-Windows-29411328385-1` (178387969 bytes), `data-viewer-quality-Windows-29411328385-1` (179072405 bytes), `data-viewer-package-Ubuntu-29411328385-1` (218898730 bytes), and `data-viewer-quality-Ubuntu-29411328385-1` (219629886 bytes) |

Known gaps:

- This removes obsolete legacy release entrypoints only. Legacy application runtime modules and historical regression tests remain until their individual migration/removal groups satisfy the full removal criteria.

## DV-1008 PyPA build module shadowing guard slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- `build.py` remains the root `python build.py` Data Viewer PyInstaller release front end.
- When the same file is resolved by `python -m build`, it now removes the repository root from module resolution and delegates to the installed PyPA `build` package instead of parsing Data Viewer release-wrapper arguments.
- If PyPA `build` is absent from the local environment, `python -m build` now reports a clean missing-dev-dependency message rather than a misleading `build.py` argparse error or traceback.
- `tests/test_packaging_artifacts.py` records the regression boundary so the standard wheel/sdist command cannot silently fall back into the Data Viewer PyInstaller wrapper again.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial PyPA build shadowing regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_root_build_wrapper_does_not_shadow_pypa_build_module -q` | failed as expected before implementation because `python -m build --version` entered root `build.py` and rejected `--version` |
| Packaging contract tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py -q` | 6 passed |
| Standard build-module smoke in stale local venv | `venv\Scripts\python.exe -m build --version` | failed cleanly with `PyPA build is not installed; install the project dev dependencies or run \`uv build --no-sources\`.`; this venv lacks the PyPA `build` package |
| Data Viewer build front-end help smoke | `venv\Scripts\python.exe build.py --help` | printed Data Viewer release artifact usage |
| Locked-environment command availability check | `uv run --locked python -m build --version` | not run locally because `uv` is not on this Windows shell PATH; GitHub Actions remains the authoritative locked-environment verification |
| Release/package related tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_data_viewer_package.py tests\test_release_evidence.py tests\test_installed_artifact_smoke.py -q` | 20 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check build.py tools tests\test_packaging_artifacts.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy build.py tools\build_pyinstaller_artifact.py` | passed; no issues in 2 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q build.py tools data_viewer .github\scripts` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 544 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This is a command-resolution guard only. It does not mark DV-1008 complete; remaining legacy runtime modules and historical regression tests still require separate migration/removal evidence.

## DV-1008 legacy packaged-smoke test removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed `tests/test_packaged.py`, the obsolete "packaged build" smoke suite that imported legacy `core`, `plugins`, and `services` modules directly from the source tree instead of exercising Data Viewer release artifacts.
- The current package-smoke responsibility remains with `tests/test_installed_artifact_smoke.py` and `.github/scripts/smoke_pyinstaller_artifact.py`, which run the Data Viewer executable with `--version` and the hidden `--ci-smoke` workflow used by CI package artifacts.
- `tests/test_packaging_artifacts.py` now asserts the obsolete legacy packaged-smoke file stays absent and that the target installed-artifact smoke path does not import legacy runtime modules.
- Parity rationale: the removed legacy test covered source imports, HDF5 reading, slicing, cache, legacy plugins, and CSV export. These release-facing concerns are now covered by target package/version tests, source adapter suites, Plugin API/built-in plugin tests, export tests, and the installed-artifact functional smoke that opens HDF5/CSV/NIfTI/gzip/workspace data, runs `org.dataviewer.dataset_profile`, exports a result, and closes documents.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy packaged-smoke removal regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_packaged_build_smoke_suite_is_removed -q` | failed as expected before implementation because `tests/test_packaged.py` still existed |
| Targeted regression test after removal | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_packaged_build_smoke_suite_is_removed -q` | passed |
| Release/package related tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_installed_artifact_smoke.py tests\test_release_evidence.py tests\test_data_viewer_package.py -q` | 21 passed |
| Target package-smoke legacy import audit | `rg -n "test_packaged\\.py|Legacy HDF5 Viewer - Packaged Build Tests|from (core|gui|plugins|services)" tests\test_packaging_artifacts.py tests\test_installed_artifact_smoke.py .github\scripts\smoke_pyinstaller_artifact.py` | only intentional guard strings remained in `tests/test_packaging_artifacts.py`; target smoke code had no legacy runtime imports |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_installed_artifact_smoke.py .github\scripts\smoke_pyinstaller_artifact.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy .github\scripts\smoke_pyinstaller_artifact.py data_viewer\installed_smoke.py` | passed; no issues in 2 source files |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer .github\scripts tests\test_packaging_artifacts.py tests\test_installed_artifact_smoke.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 539 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete legacy packaged-smoke test group. Other legacy regression suites still import `core`, `gui`, `plugins`, `services`, and `main.py` as migration references until each remaining capability/removal group satisfies the full removal criteria.

## DV-1008 legacy final integration script removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed `tests/test_final.py`, an obsolete legacy "Final Integration Tests" script that performed module-level source imports from legacy `core`, `gui`, `services`, and `plugins`, printed ad-hoc status lines at import time, and duplicated smaller legacy/target coverage without exercising Data Viewer release artifacts.
- Updated `tests/test_test_environment.py` so the GUI module collection lifecycle regression still collects multiple existing legacy GUI-heavy modules rather than referencing the removed script.
- `tests/test_packaging_artifacts.py` now asserts the obsolete final integration script stays absent and that the environment lifecycle test does not reintroduce it.
- Parity rationale: the removed script's core HDF5, slicing/cache, plugin, export, and GUI import smoke coverage remains represented by focused legacy tests (`tests/test_integration.py`, `tests/test_gui_interaction.py`, `tests/test_test_environment.py`) plus target Data Viewer package and installed-artifact smoke tests.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy final-script removal regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_final_integration_smoke_script_is_removed -q` | failed as expected before implementation because `tests/test_final.py` still existed |
| Targeted regression test after removal | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_final_integration_smoke_script_is_removed -q` | passed |
| GUI collection lifecycle regression | `venv\Scripts\python.exe -m pytest tests\test_test_environment.py::test_gui_module_collection_exits_after_importing_multiple_modules -q` | passed |
| Affected legacy/target subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_integration.py tests\test_gui_interaction.py tests\test_data_viewer_package.py tests\test_installed_artifact_smoke.py -q` | 43 passed |
| Removed-script reference audit | `rg -n "test_final\\.py|Final Integration Tests|from (core|gui|plugins|services)" tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_data_viewer_package.py tests\test_installed_artifact_smoke.py` | only intentional guard strings remained for `test_final.py`; target Data Viewer package/smoke tests had no legacy runtime imports |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_test_environment.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_integration.py tests\test_gui_interaction.py` | passed |
| Legacy lint/type debt probe | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_integration.py tests\test_gui_interaction.py`; `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py tests\test_test_environment.py` | not used as a completion gate; failed on pre-existing legacy Ruff/mypy debt outside this removal slice, while the project CI strict lint/type scope remains target-focused |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 537 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete final integration script. Other legacy regression suites still import `core`, `gui`, `plugins`, `services`, and `main.py` as migration references until each remaining capability/removal group satisfies the full removal criteria.

## DV-1008 legacy comprehensive all-features script removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed `tests/test_all_features.py`, an obsolete legacy "Comprehensive Feature Tests" script that created a `QApplication` at module import time, imported legacy `core`, `gui`, `services`, and `plugins` modules directly, and duplicated focused HDF5, slicing, plugin, export, event-bus, async-load, and table-model coverage.
- Updated `tests/test_test_environment.py` so the GUI module collection lifecycle regression still collects multiple existing modules (`tests/test_gui_interaction.py`, `tests/test_phase1.py`, and `tests/test_comprehensive.py`) without referencing the removed script.
- `tests/test_packaging_artifacts.py` now asserts the obsolete comprehensive script stays absent and that the environment lifecycle test does not reintroduce it.
- Parity rationale: the removed script's HDF5, slicing, plugin, export, and event-bus coverage remains represented by `tests/test_integration.py`; GUI/model and broader legacy behavior remain represented by `tests/test_gui_interaction.py`, `tests/test_comprehensive.py`, and `tests/test_test_environment.py`; target release-facing behavior remains covered by package and installed-artifact smoke tests.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy all-features removal regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_all_features_smoke_script_is_removed -q` | failed as expected before implementation because `tests/test_all_features.py` still existed |
| Targeted regression test after removal | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_all_features_smoke_script_is_removed -q` | passed |
| GUI collection lifecycle regression | `venv\Scripts\python.exe -m pytest tests\test_test_environment.py::test_gui_module_collection_exits_after_importing_multiple_modules -q` | passed |
| Affected legacy/target subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_integration.py tests\test_gui_interaction.py tests\test_comprehensive.py tests\test_data_viewer_package.py tests\test_installed_artifact_smoke.py -q` | 110 passed, 1 skipped |
| Removed-script reference audit | `rg -n "test_all_features\\.py|Legacy HDF5 Viewer - Comprehensive Feature Tests|from (core|gui|plugins|services)" tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_data_viewer_package.py tests\test_installed_artifact_smoke.py` | only intentional guard strings remained for `test_all_features.py`; target Data Viewer package/smoke tests had no legacy runtime imports; `tests/test_test_environment.py` retains expected legacy lifecycle imports |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_test_environment.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q data_viewer tests\test_packaging_artifacts.py tests\test_test_environment.py tests\test_integration.py tests\test_gui_interaction.py tests\test_comprehensive.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 531 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete comprehensive all-features script. Other legacy regression suites still import `core`, `gui`, `plugins`, `services`, and `main.py` as migration references until each remaining capability/removal group satisfies the full removal criteria.

## DV-1008 legacy core-test manual runner removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed the obsolete `main()` / `if __name__ == "__main__"` manual runner from `tests/test_core.py`, including the historical "Legacy HDF5 Viewer - Core Module Tests" banner.
- Kept the existing pytest tests for `EventBus`, `SliceParser`, `LRUCache`, `H5Source`, and `DataSourceRegistry` intact.
- Removed now-obvious unused datasource imports from `tests/test_core.py`.
- `tests/test_packaging_artifacts.py` now asserts the manual runner stays absent while preserving the core pytest module.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy core runner regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_core_test_manual_runner_is_removed -q` | failed as expected before implementation because `tests/test_core.py` still contained the legacy banner and manual runner |
| Targeted regression and retained core tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_core_test_manual_runner_is_removed tests\test_core.py -q` | 6 passed |
| Affected legacy subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_core.py tests\test_integration.py tests\test_edge_cases.py -q` | 32 passed, 3 existing NumPy NaN/Inf warnings |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_core.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q tests\test_packaging_artifacts.py tests\test_core.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 532 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete manual runner from the retained core pytest module. Other legacy regression suites still have manual script runners and legacy imports until each group is cleaned or removed with parity evidence.

## DV-1008 legacy integration-test manual runner removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed the obsolete `main()` / `if __name__ == "__main__"` manual runner from `tests/test_integration.py`, including the historical "Legacy HDF5 Viewer - Integration Tests" banner.
- Kept the pytest tests for HDF5 file operations, slicing, cache, plugins, export, and event bus intact.
- Removed unused imports exposed by the runner cleanup from `tests/test_integration.py`.
- `tests/test_packaging_artifacts.py` now asserts the manual runner stays absent while preserving the integration pytest module.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy integration runner regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_integration_test_manual_runner_is_removed -q` | failed as expected before implementation because `tests/test_integration.py` still contained the legacy banner and manual runner |
| Targeted regression and retained integration tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_integration_test_manual_runner_is_removed tests\test_integration.py -q` | 7 passed |
| Affected legacy subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_integration.py tests\test_core.py tests\test_test_environment.py -q` | 31 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_integration.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q tests\test_packaging_artifacts.py tests\test_integration.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 533 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Removed-runner reference audit | `rg -n "Legacy HDF5 Viewer - Integration Tests|def main\\(|__main__" tests\test_integration.py tests\test_packaging_artifacts.py` | only intentional guard strings remained in `tests/test_packaging_artifacts.py` |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete manual runner from the retained integration pytest module. Other legacy regression suites still have manual script runners and legacy imports until each group is cleaned or removed with parity evidence.

## DV-1008 legacy edge-case manual runner removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed the obsolete `main()` / `if __name__ == "__main__"` manual runner from `tests/test_edge_cases.py`, including the historical "Legacy HDF5 Viewer - Edge Case Tests" banner.
- Kept the pytest tests for HDF5 edge files, NaN/Inf statistics, large dataset reads, slicer/export/cache/event-bus edge cases, and `DataTableModel` edge cases intact.
- Removed unused imports and no-op timing variables exposed by the runner cleanup from `tests/test_edge_cases.py`; normalized legacy `assert result == True` checks to direct truth assertions without changing expected behavior.
- `tests/test_packaging_artifacts.py` now asserts the manual runner stays absent while preserving the edge-case pytest module.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy edge-case runner regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_edge_case_test_manual_runner_is_removed -q` | failed as expected before implementation because `tests/test_edge_cases.py` still contained the legacy banner and manual runner |
| Targeted regression and retained edge-case tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_edge_case_test_manual_runner_is_removed tests\test_edge_cases.py -q` | 12 passed, 3 existing NumPy NaN/Inf warnings |
| Affected legacy subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_edge_cases.py tests\test_core.py tests\test_integration.py -q` | 34 passed, 3 existing NumPy NaN/Inf warnings |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_edge_cases.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q tests\test_packaging_artifacts.py tests\test_edge_cases.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 534 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Removed-runner reference audit | `rg -n "Legacy HDF5 Viewer - Edge Case Tests|def main\\(|__main__" tests\test_edge_cases.py tests\test_packaging_artifacts.py` | only intentional guard strings remained in `tests/test_packaging_artifacts.py` |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete manual runner from the retained edge-case pytest module. Other legacy regression suites still have manual script runners and legacy imports until each group is cleaned or removed with parity evidence.

## DV-1008 legacy Phase 1 manual runner removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed the obsolete `main()` / `if __name__ == "__main__"` manual runner from `tests/test_phase1.py`, including the historical "Legacy HDF5 Viewer - Phase 1 Tests" banner.
- Kept the pytest tests for `TabManager`, `ExplorerPanel`, `SliceInput`, `DataTable`, and `StatusBar` intact.
- Removed unused imports and normalized import ordering exposed by the runner cleanup from `tests/test_phase1.py`.
- `tests/test_packaging_artifacts.py` now asserts the manual runner stays absent while preserving the Phase 1 pytest module.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy Phase 1 runner regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_phase1_test_manual_runner_is_removed -q` | failed as expected before implementation because `tests/test_phase1.py` still contained the legacy banner and manual runner |
| Targeted regression and retained Phase 1 tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_phase1_test_manual_runner_is_removed tests\test_phase1.py -q` | 6 passed |
| Affected GUI lifecycle subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_phase1.py tests\test_test_environment.py -q` | 27 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_phase1.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q tests\test_packaging_artifacts.py tests\test_phase1.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 535 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Removed-runner reference audit | `rg -n "Legacy HDF5 Viewer - Phase 1 Tests|def main\\(|__main__" tests\test_phase1.py tests\test_packaging_artifacts.py` | only intentional guard strings remained in `tests/test_packaging_artifacts.py` |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete manual runner from the retained Phase 1 pytest module. Other legacy regression suites still have manual script runners and legacy imports until each group is cleaned or removed with parity evidence.

## DV-1008 legacy GUI-interaction manual runner removal slice - 2026-07-15

Revision: implementation and evidence are recorded together in the commit containing this section.

Implementation evidence:

- Removed the obsolete `main()` / `if __name__ == "__main__"` manual runner from `tests/test_gui_interaction.py`, including the historical "Legacy HDF5 Viewer - GUI Interaction Tests" banner.
- Kept the pytest tests for legacy main window creation, tab manager, explorer, slice input, data table, status bar, bottom panel, activity bar, and search panel intact.
- Removed unused imports and normalized one legacy truth assertion exposed by the runner cleanup from `tests/test_gui_interaction.py`.
- `tests/test_packaging_artifacts.py` now asserts the manual runner stays absent while preserving the GUI-interaction pytest module.

Local Windows verification in the repository `venv`:

| Check | Command | Observed result |
|---|---|---|
| Initial legacy GUI-interaction runner regression test | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_gui_interaction_test_manual_runner_is_removed -q` | failed as expected before implementation because `tests/test_gui_interaction.py` still contained the legacy banner and manual runner |
| Targeted regression and retained GUI-interaction tests | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py::test_legacy_gui_interaction_test_manual_runner_is_removed tests\test_gui_interaction.py -q` | 10 passed |
| Affected GUI subset | `venv\Scripts\python.exe -m pytest tests\test_packaging_artifacts.py tests\test_gui_interaction.py tests\test_test_environment.py tests\test_gui_theme.py tests\test_gui_shell.py -q` | 57 passed |
| Scoped lint | `venv\Scripts\python.exe -m ruff check tests\test_packaging_artifacts.py tests\test_gui_interaction.py` | passed |
| Scoped type check | `venv\Scripts\python.exe -m mypy tests\test_packaging_artifacts.py` | passed; no issues in 1 source file |
| Scoped compile | `venv\Scripts\python.exe -m compileall -q tests\test_packaging_artifacts.py tests\test_gui_interaction.py` | passed |
| Full local suite | `venv\Scripts\python.exe -m pytest -q` | 536 passed, 1 skipped, 3 existing NumPy NaN/Inf warnings |
| Removed-runner reference audit | `rg -n "Legacy HDF5 Viewer - GUI Interaction Tests|def main\\(|__main__" tests\test_gui_interaction.py tests\test_packaging_artifacts.py` | only intentional guard strings remained in `tests/test_packaging_artifacts.py` |
| Diff whitespace check | `git diff --check` | passed; Git emitted only expected LF-to-CRLF working-copy warnings on Windows |

Known gaps:

- This removes only the obsolete manual runner from the retained GUI-interaction pytest module. `tests/test_stress.py` still has a manual script runner until it is cleaned with parity evidence.
