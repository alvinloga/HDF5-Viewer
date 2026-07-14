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
- runtime/build naming and version sources disagree (`HDF5Viewer`, About version, and git tags);
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

The successful local environment is a project virtual environment derived from the existing `hdf5viewer_build` Conda environment. It is sufficient for collection diagnosis but is not the clean lock-validation environment required by DV-0002. DV-0003 remains unchecked until the same collection gate passes from the locked environment.

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
