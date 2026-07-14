# Data Viewer Verification Ledger

## Purpose

This file records commands actually run against specific repository states. It must not predict future results. Update it after meaningful baseline, checkpoint, and release verification.

## Legacy baseline â€?2026-07-11

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

## Documentation architecture pass â€?2026-07-11

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

## DV-0001 package skeleton â€?2026-07-11

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

## DV-0003 pytest collection and isolation pre-acceptance â€?2026-07-11

Revision: `35d0a73` (`test: stabilize Qt collection and config isolation`).

| Check | Command | Observed result |
|---|---|---|
| Qt/config regression tests | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py -q` | 3 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 133 tests collected in 1.09 seconds; command exited 0 |
| Repository config integrity | SHA-256 before/after GUI config test | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |
| Full execution diagnostic | `venv\Scripts\python.exe -m pytest -q` | 132 passed, 1 skipped, 11 teardown errors |

The full-execution errors are Windows `PermissionError` failures while deleting temporary HDF5 files that remain open after GUI/tab operations. They are assigned to DV-0004 (close/ownership regression coverage), not suppressed. Test order randomization is not configured in the repository, so the required order/seed rerun is not applicable yet.

The successful local environment is a project virtual environment derived from the existing `hdf5viewer_build` Conda environment. It is sufficient for collection diagnosis but is not the clean lock-validation environment required by DV-0002. DV-0003 remains unchecked until the same collection gate passes from the locked environment.

## Legacy resource-cleanup follow-up â€?2026-07-11

Revision: working tree following `158c55d` (`docs: record pytest isolation pre-acceptance`). This follow-up is baseline test isolation only; it does not change the target Data Viewer source-session architecture.

| Check | Command | Observed result |
|---|---|---|
| Focused Windows handle regressions | `venv\Scripts\python.exe -m pytest tests/test_test_environment.py::test_registry_cleanup_releases_open_hdf5_sources tests/test_comprehensive.py::TestTabOperations::test_open_file tests/test_comprehensive.py::TestFileOperations::test_open_hdf5_file tests/test_comprehensive.py::TestDataNavigation::test_node_double_click -q` | 4 passed |
| Full collection | `venv\Scripts\python.exe -m pytest --collect-only -q` | 134 tests collected in 1.32 seconds; command exited 0 |
| Full execution | `venv\Scripts\python.exe -m pytest -q` | 133 passed, 1 skipped, 3 existing NaN/Inf `RuntimeWarning`s; command exited 0 |
| Test parsing | `venv\Scripts\python.exe -m compileall -q tests` | passed |
| Repository config integrity | SHA-256 after the full run | unchanged: `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` |

The fix explicitly closes the legacy registry entry before each affected xUnit teardown deletes its temporary HDF5 fixture, while an autouse fixture resets cached data sources and the event bus between tests. This closes the prior Windows temporary-file-handle failure without weakening product assertions. Ruff is not present in this diagnostic virtual environment, so lint/type checks remain blocked on DV-0002's clean, locked dev environment.

## DV-0002 Windows locked-environment evidence â€?2026-07-11

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

## DV-0002 and DV-0003 completion evidence â€?2026-07-11

Revision: `ab9ea7e` (`test: stabilize locale and timezone isolation`); lock SHA-256: `F44C592658057904746D776129076715CDE998FB699A797E256F432FA2C07734`.

The historical Windows-only entry above is superseded by [GitHub Actions run 29151025813](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29151025813), which passed the same locked gate on both platforms.

| Platform | CPython | Locked CI result |
|---|---:|---|
| Windows Server 2025 | 3.12.10 | `uv lock --check`, locked sync, direct imports, target lint/type, compile, 139-test collection, 138 passed / 1 skipped, and sdist/wheel build all passed |
| Ubuntu latest | 3.12.13 | the same locked install, import, static, collection, full offscreen GUI, and package-build gate passed |

The test fixture now fixes `TZ=UTC` and locale `C`, config writes are redirected to `tmp_path`, Qt is offscreen, and data-source/event-bus singletons reset per test. Static test definitions and collected tests are both 139; runtime execution is 138 passed and 1 intentionally skipped. `config.json` remains SHA-256 `D5A91F78570EE3F73920596A0FC1729546B5F09BABFA6EE01AB5CD451C64C305` after the local full run.

DV-0002 and DV-0003 are complete. The public binary release remains blocked by the unresolved PyQt6 GPL/commercial distribution decision and all later v1 acceptance tasks. DV-0005 remains open because artifact-report upload, release dependency enforcement, and its deliberate-failure verification are not complete.

## DV-0004 legacy-test consolidation and deterministic fixtures â€?2026-07-11

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

No report may use â€?00%â€?unless it names the measured denominator and includes the artifact. A passing build is not a passing application.


