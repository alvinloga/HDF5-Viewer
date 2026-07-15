# Changelog

All notable Data Viewer changes are recorded here.

## Unreleased

### Added

- Added the installable `data_viewer` package skeleton with one canonical development version and a migration-safe command-line entry point.
- Added deterministic, generated HDF5, NPY, and CSV fixture factories with recorded creation parameters for reusable scientific-data tests.
- Added Windows/Ubuntu quality evidence artifacts with JUnit reports, CI manifests, and sdist/wheel outputs before any release job.
- Added immutable Data Viewer domain values for resource identity, domains, capabilities, metadata, fingerprints, and hierarchy nodes.
- Added normalized selection, table-page, payload, scope, sampling, and read-result domain values with coordinate provenance.
- Added structured error taxonomy, safe user messages, diagnostic snapshots, and path redaction values.
- Added cooperative task lifecycle primitives with cancellation tokens, thread-safe progress, snapshots, and injectable callback dispatching.
- Added DataSource API v1 source adapter/session protocols, bounded source registry probe arbitration, managed session lifecycle checks, and a reusable fake adapter conformance harness.
- Added the HDF5 probe/session foundation in `data_viewer/sources/hdf5` (`HDF5Adapter`, `HDF5SourceSession`) and `tests/test_hdf5_adapter.py` covering signature validation, wrong-extension and malformed input, locked/missing sources, Unicode paths, shared contract conformance, and open/close stability.
- Added lazy HDF5 hierarchy listing metadata support in DV-0202: paginated direct-child listing (no full recursive traversal), explicit dataset layout metadata (`chunks`, `compression`, `compression_opts`, `fill_value`), soft-link target status detection (including broken/cyclic links), and metadata-enriched link summaries for soft/external links.
- Added direct bounded HDF5 selection reads in `data_viewer/sources/hdf5/session.py` (DV-0203): reads now materialize through a normalized selection key with added coverage for scalar, empty, 1D/2D/high-dimensional, compound, string, complex, and boolean arrays and dtypes.
- Added a new target Qt bootstrap for Data Viewer with minimal shell/command composition:
  - `data_viewer/gui/app.py` introduces `run_data_viewer` bootstrap entry.
  - `data_viewer/gui/commands.py` implements asynchronous open + cancellation command handling.
  - `data_viewer/gui/shell.py` provides regioned shell scaffolding and lifecycle-safe open/close handling.
  - `data_viewer/__main__.py` dispatches to target bootstrap by default with `--version` support.
- Added vertical shell behaviors for the target Data Viewer (DV-0205): lazy tree expansion/load-more behavior, dataset activation path/shape/dtype/slice status synchronization, and object-name wiring for status labels used by automation and tests.
- Added DocumentController ownership and request-generation tracking (`data_viewer/app/documents.py` and `data_viewer/app/active_context.py`), including close/wait lifecycle cleanup and non-GUI dirty/active-task state hooks.
- Added platform path resolution and bounded temporary cache primitives (`data_viewer/infrastructure/paths.py`, `cache.py`), with atomic read/write configuration handling and log redaction support for diagnostics in `data_viewer/infrastructure/config.py` and `data_viewer/infrastructure/logging.py`.
- Added immutable safe-editing patch primitives in `data_viewer/editing/patches.py` (`Patch`, `CellPatch`, `TextPatch`, `AttributePatch`, `ChangeSet`), typed edit-value validation in `data_viewer/editing/validation.py` (integer/float/complex/boolean/string/structured support with nonfinite and truncation guards), and `EditHistory` immutable undo/redo state in `data_viewer/editing/history.py`.
- Added edit-session persistence state flow and save/conflict review model in `data_viewer/editing/session.py` and `data_viewer/editing/review.py`; integrated dirty/save/close/conflict transitions into `DocumentController` with close-policy semantics and structured save summary generation (`data_viewer/app/documents.py`) to support safe-edit workflows (DV-0302).
- Added verified atomic replacement persistence service foundation for safe overwrite paths in `data_viewer/persistence/transaction.py`, startup recovery marker lifecycle in `data_viewer/persistence/recovery.py`, and coverage for fault injection, cancellation, disk preflight, and orphan cleanup (`tests/test_persistence_recovery.py`, `tests/test_persistence_transaction.py`) (DV-0303).
- Added HDF5 safe persistence strategies (DV-0304): reviewed cell patches can use verified in-place writes with a same-directory recovery backup, while attributes and unsafe cells use verified atomic replacement with source-fingerprint conflict checks and post-write coordinate verification.
- Added export planning, execution, and receipt primitives (DV-0305) covering explicit full/slice/selection/filtered/result/rendered scopes, raw/display/scaled value modes, overwrite/cancel/failure receipts, CSV formula-cell escaping, and JSON receipt round trips.
- Added edit review, save/conflict, and export UI wiring (DV-0306): the shell now exposes textual dirty/read-only/conflict states, review/save/export command controls, real HDF5 patch save execution through `DocumentController`, conflict-safe disabled save behavior, and receipt-backed active-payload export.
- Added the NPY adapter and verified replacement writer (DV-0401): `.npy` sources now probe/open through DataSource API v1, load with `allow_pickle=False`, reject object arrays, preserve scalar/empty/structured/order/byte-order metadata, support bounded selection reads, and save reviewed cell patches through atomic replacement validation.
- Added the NPZ adapter and archive-rebuild writer (DV-0402): `.npz` sources now expose synthetic member hierarchies, reject unsafe archive members and object arrays, enforce ZIP size/compression safety budgets, support bounded member selection reads, and save reviewed cell patches by rebuilding and validating the archive.
- Added the CSV/TSV delimited adapter foundation (DV-0403): `.csv` and `.tsv` sources now use bounded strict-UTF-8/BOM previews, explicit dialect/options/schema provenance, paged table reads with stable row identity, and shell table rendering; verified source overwrite remains owned by DV-0404.
- Added the CSV/TSV verified writer (DV-0404): reviewed table cell patches now rewrite the full delimited file through the atomic replacement service, preserve confirmed encoding/dialect and line-ending/final-newline state, validate row/column counts and patched values before replacement, and reject stale source fingerprints.
- Added the TXT text/table dual-mode adapter and writer (DV-0405): `.txt` opens as strict UTF-8/BOM text by default with bounded text previews and atomic `TextPatch` replacement, while explicitly configured table mode reuses confirmed delimited parsing/writing without silent whitespace inference.
- Added the read-only JSON structured adapter (DV-0406): `.json` sources now parse strict UTF-8/BOM input, expose JSON Pointer resource paths, support scalar roots, detect duplicate object keys with warnings, enforce size/depth/collection/string budgets, and render structured previews in the target shell.
- Added the read-only restricted YAML adapter (DV-0407): `.yaml` and `.yml` sources now parse strict UTF-8/BOM input with `yaml.safe_load`, reject unsafe/custom tags, expose JSON Pointer resource paths, surface alias/merge semantics and typed nonstring key metadata, enforce size/depth/collection/string/alias budgets, and render structured previews in the target shell.
- Added the read-only MATLAB MAT adapter (DV-0408): `.mat` sources now dispatch legacy MAT files through SciPy and HDF5-backed v7.3 files through h5py, expose a unified stable variable tree, hide internal metadata nodes by default, represent arrays/text/sparse/cell/struct/nested resources explicitly, bound traversal, and register in the target shell.
- Added the read-only safe XLSX adapter (DV-0409): `.xlsx` workbooks now open with external links disabled, expose workbook/sheet/cell/table/defined-name/merged-range metadata, distinguish formulas from cached values without execution, preserve blank cells inside used ranges, support bounded worksheet page reads, reject encrypted/malformed inputs, and register in the target shell.
- Added the read-only NIfTI adapter and coordinate model (DV-0410): `.nii` and native `.nii.gz` volumes now expose spatial metadata, proxy-backed bounded slices, scaling/intent/header provenance, exact voxel↔world affine mapping, and register in the target shell without canonicalization or resampling.
- Added generic gzip wrapper detection and stream-capable inner adapter support (DV-0501) for `.csv.gz`, `.tsv.gz`, `.txt.gz`, `.json.gz`, `.yaml.gz`, and `.yml.gz`, while preserving native `.nii.gz` routing and leaving random-access gzip extraction to DV-0502.
- Added managed random-access gzip extraction cache (DV-0502) with canonical fingerprint cache keys, budget/ratio/free-disk preflight, cancellation cleanup, expired/incomplete startup cleanup, and random-access NPY gzip fixture coverage.
- Added full v1 gzip registry integration (DV-0503): every v1 gzip wrapper opens through the default target registry, generic gzip metadata is read-only, `.npz.gz`/`.xlsx.gz` report inefficient nested-compression warnings, native `.nii.gz` remains a NIfTI source, and nested-compression targets are not inferred as export formats.
- Added the semantic Qt theme foundation (DV-0601): centralized light/dark color roles, compact 4 px metrics, platform typography roles, bundled monochrome SVG icon definitions, generated application stylesheet, and palette/icon scan tests.
- Added the application command registry and expanded ActiveContext (DV-0602): stable command IDs, labels, shortcuts, semantic actions, enabled/disabled reasons, and explicit split/view/resource/selection/task/dirty state without widget coupling.
- Added the first production shell structure slice (DV-0603): command bar bindings, authoritative structure tree contract, workspace tabs, explicit active split label, inspector tabs, Tasks/Output/Problems bottom panel, expanded status fields, and 1024×768 minimum usability guard.
- Added standard Qt state component contracts (DV-0604): initial/loading/empty/ready/partial/error/disabled/dirty/read-only/conflicted/stale view models, keyboard-reachable actions, safe error details, and non-color-only labels.
- Added base workspace view contracts and widgets (DV-0605): virtual table, bounded array projection, paged text preview, and image projection views with explicit scope, coordinates, shape, slice, cursor, and plugin result-channel metadata.
- Added safe dialog primitives (DV-0606): inline path validation, modal save summaries, safe-default destructive confirmations, and preview-first nonmodal import options.
- Added the first DV-0607 accessibility/localization baseline slice: centralized English/Simplified Chinese UI string resources, shell/dialog/state locale wiring, accessible-name audit helpers, deterministic command-row focus order, and compact high-DPI metric scaling helpers.
- Extended the DV-0607 baseline with localized base-view chrome and a plot accessibility summary contract for future visualization plugins.
- Completed the DV-0607 automated baseline with a simulated 200% offscreen shell screenshot/layout check.
- Added the Plugin API v1 manifest and built-in registry foundation (DV-0701): public plugin result/context types, strict manifest validation, deterministic built-in registry ordering, structured diagnostics, duplicate-ID handling, and lazy entry-point imports.
- Added the Plugin API v1 compatibility and parameter-form foundation (DV-0702): single-input domain/shape/dtype/access/budget/dependency decisions with exact disabled reasons, immutable parameter defaults/validation, and keyboard-accessible standard Qt controls without plugin-created dialogs.
- Added the Plugin API v1 runner/input-access foundation (DV-0703): document-backed bounded reads and first-axis chunks, task snapshots, cooperative cancellation without partial results, stale-result rejection, and safe plugin exception mapping.
- Added the Plugin API v1 typed-result foundation (DV-0704): summary/table/array/image/plot/collection validators, declarative PlotSpec/PlotMark payloads, provenance export records, and bounded in-memory array result materialization.
- Added the Plugin API v1 conformance/reference slice (DV-0705): reusable test-side plugin conformance checks plus a packaged `org.dataviewer.dataset_profile` reference plugin demonstrating manifest discovery, compatibility, immutable parameters, chunked execution, cancellation/progress, numerical goldens, edge-input handling, result/provenance validation, and forbidden-import scanning.
- Added the first P8 statistics plugins (DV-0801): Dataset Profile now reports storage estimates and numeric/complex-magnitude semantics, and `org.dataviewer.descriptive_statistics` provides axis-aware count, missing/nonfinite counts, mean, sample standard deviation, configurable quantiles, and extrema as provenance-complete table results.
- Added the Distribution Summary built-in plugin (DV-0802): histogram rows, IQR/MAD robust spread, skewness/kurtosis only when valid, nonfinite accounting, and explicit deterministic sampling metadata.
- Added the Correlation/Covariance built-in plugin (DV-0803): labeled symmetric matrix output, listwise/pairwise missing-data alignment, contiguous variable-axis selection, constant-variable warnings, and variable-count budget refusal.
- Added the Dataset Compare built-in plugin (DV-0804): exact-shape compatibility checks, no-broadcast refusal, equality counts, finite/nonfinite accounting, absolute and left-relative error metrics, and explicit zero-denominator handling.
- Added the first declarative visualization plugins (DV-0805): line, scatter, histogram, and box plot built-ins now emit renderer-owned `PlotSpec` results with finite-value filtering, deterministic sampling metadata, accessible summaries, export provenance, and JSON-safe data-table metadata.
- Added the multidimensional slice navigator workspace view (DV-0806): image projections now have explicit high-dimensional axis/index navigation state, raw/display mode labeling, linked-slice status, bounded-read provenance, preserved aspect/zoom/interpolation metadata, and cursor-to-source coordinate reporting.
- Added heatmap visualization plugins (DV-0807): Correlation Heatmap and Missing Data Map built-ins now emit renderer-owned heatmap `PlotSpec` results with labeled axes, explicit value ranges/legends, data-table alternatives, missing-data semantics, and deterministic observation sampling for large missing maps.
- Added the NIfTI orthogonal viewer foundation (DV-0808): bounded `VolumePayload` results can now render axial/coronal/sagittal orientation labels, linked crosshair voxel/world/value metadata, 4D volume index state, window/level labels, affine/header inspection, and explicit no-resampling status.
- Added the Workspace Format v1 foundation (DV-0901): `.dvw` manifests now have a packaged schema, typed model, deterministic UTF-8 serialization, bounded unsafe-input validation, unknown-field preservation, relative/absolute source path resolution, and atomic save/load service semantics independent from source dirty state.
- Added the Workspace restore planner (DV-0902): `.dvw` sources are now classified as available, moved candidate, missing, changed, ambiguous, unsupported, or failed; view shells restore before bounded metadata/payload reads; persisted plugin results are marked current/stale from source fingerprints; relocation updates require explicit confirmation and mark only the workspace dirty.
- Added comparison workspace state (DV-0903): comparison sides now persist left/right resource identity, fingerprints, explicit index/axis/column alignment, difference mode, linked-navigation state, compatibility labels, and provenance; invalid comparison workspace entries degrade independently instead of aborting workspace restore.
- Added navigation/search application state (DV-0904): recent and pinned files, resource favorites, semantic back/forward history, missing-recent remediation, and grouped global search now have Qt-free service models that remain outside `.dvw` workspace manifests.
- Added session restore and external-change decision models (DV-0905): startup restore now records only a safe last-workspace pointer and clean-shutdown flag, while external file changes classify changed/replaced/deleted/self-save outcomes and prevent dirty patches from auto-overwriting source files.
- Added background export queue and diagnostics bundle contracts (DV-0906): reviewed exports now have queued task state, progress, cancellation, retry, receipt history, Problems links to task/source/resource, and user-previewable diagnostics bundles with configured path redaction and plugin inventory.
- Added the Phase 0 performance budget harness (DV-1001): reproducible benchmark reports now record median, p95, peak traced memory, path-free platform profiles, synthetic release-budget probes, and structured threshold evaluations.
- Added the first hardening stress suite (DV-1002): export queues now release successful task payload records, and tests cover many-task retention, rapid-search cancellation, adversarial workspace depth, and gzip incomplete-cache cleanup.
- Completed the current Data Viewer name/version migration slice (DV-1003): workspace app metadata now reads the canonical package version and target runtime scans guard against non-historical HDF5 Viewer naming.
- Added the platform configuration migration slice (DV-1004): target config now has versioned UI preferences, legacy repository config preview/migration is explicit and non-destructive, and bootstrap prepares platform config/cache/log paths.
- Added the initial Data Viewer PyInstaller packaging slice (DV-1005): Windows and Linux CI now build `DataViewer-<version>-<platform>` archives from a locked environment, run a packaged `--version` smoke test, upload package artifacts, and lint/type-check the packaging scripts.
- Added the installed-artifact functional smoke slice (DV-1006): packaged Data Viewer executables now run a hidden CI workflow that opens representative HDF5, CSV, NIfTI, gzip, and workspace data, runs the Dataset Profile reference plugin, exports a plugin result, closes documents, captures an offscreen screenshot, and uploads smoke evidence before package artifacts are accepted.
- Added the DV-1007 release-evidence automation slice: CI now generates SHA-256 checksums, `sbom.json`, `third-party-licenses.txt`, and `release-security-review.json` for each package artifact after installed functional smoke, while continuing to block public release until the PyQt distribution-license decision is satisfied.

### Fixed

- Stabilized the legacy GUI regression suite on Windows and Linux by isolating process state, scoping themes to each main window, and closing data-load panels cooperatively before their shared HDF5 sessions close.
- Removed one structurally proven duplicate legacy event-bus test while retaining its canonical regression coverage.
- Removed first-release NetCDF/Zarr product paths (DV-0411): legacy startup no longer imports/registers external NetCDF/Zarr sources, folder explorer defaults no longer advertise `.zarr`, optional dependency claims were removed, and the obsolete external source modules were deleted.
- Removed the broken explicit legacy CLI fallback from the target `data_viewer` entrypoint (DV-1008 slice): `--legacy` now fails argument parsing and `DATA_VIEWER_LEGACY=1` no longer overrides the default Data Viewer bootstrap.
- Removed legacy runtime paths from the release compile gate (DV-1008 slice): CI now compiles the target Data Viewer package, CI scripts, and packaging tools as the release-facing compile scope while legacy tests remain as migration-reference regressions.
- Removed obsolete legacy PyInstaller/build entrypoints (DV-1008 slice): root `build.py` is now a Data Viewer release-build front end, and the old `HDF5Viewer.spec`, `build_windows.py`, and `build_windows.bat` launchers were deleted.
- Fixed the root `build.py` wrapper so `python -m build` no longer falls into the Data Viewer PyInstaller front end; when PyPA `build` is installed it delegates to the standard wheel/sdist builder, and otherwise reports a clean missing-dev-dependency message.
- Removed the obsolete legacy `tests/test_packaged.py` source-import smoke suite; packaged validation is now owned by the Data Viewer installed-artifact smoke workflow and guarded against legacy runtime imports.
- Removed the obsolete legacy `tests/test_final.py` source-import final integration script; remaining legacy environment checks now collect still-existing focused GUI modules instead of the removed script.
- Removed the obsolete legacy `tests/test_all_features.py` comprehensive source-import smoke script; HDF5, slicing, plugin, export, event-bus, and GUI/model coverage remains in focused retained suites.
- Removed the obsolete manual script runner from `tests/test_core.py`; the retained core coverage now runs only through pytest collection.
- Removed the obsolete legacy `tests/test_integration.py` source-import suite; source, HDF5, plugin, registry, and export coverage is now guarded by target Data Viewer suites.
- Removed the obsolete manual script runner from `tests/test_edge_cases.py`; retained edge-case coverage now runs only through pytest collection.
- Removed the obsolete manual script runner from `tests/test_phase1.py`; retained legacy Phase 1 GUI smoke coverage now runs only through pytest collection.
- Removed the obsolete manual script runner from `tests/test_gui_interaction.py`; retained legacy GUI interaction coverage now runs only through pytest collection.
- Removed the obsolete manual script runner from `tests/test_stress.py`; retained stress coverage now runs only through pytest collection and replaced legacy always-true timing checks with shape assertions.
- Removed the root legacy `main.py` bootstrap; current launch documentation now points to `python -m data_viewer`.
- Removed the legacy GUI dependency from first-release format-scope tests so those checks now target the Data Viewer registry and entrypoint only.
- Removed the obsolete legacy `tests/test_phase1.py` GUI smoke suite; retained target GUI shell/base/state coverage remains in the active suite.
- Removed the obsolete legacy `tests/test_core.py` unit suite; retained target source registry, HDF5 adapter, cache, task, and selection coverage remains in the active suite.
- Normalized lock-file evidence across Windows and Linux checkouts and verified release jobs stop when quality tests fail.

### Documentation

- Renamed the target product to Data Viewer.
- Defined the first-release multi-format scope.
- Defined Windows and Linux as simultaneous release gates.
- Added target architecture, product specification, public API contracts, workspace schema, UI specification, safe-editing protocol, testing policy, dependency policy, ADRs, and agent rules.
- Reclassified the existing source as the legacy migration baseline.
- Recorded Checkpoint 3 persistence evidence for HDF5 safe edits, generic transactions, export provenance, and edit/export UI flows on Windows and Ubuntu CI.
- Recorded Checkpoint 4 uncompressed format evidence for all v1 first-release adapters on Windows and Ubuntu CI.
- Recorded Checkpoint 5 gzip evidence for stream wrappers, managed random-access extraction, full gzip registry integration, read-only/nested-compression UX metadata, and Windows/Ubuntu CI.
- Recorded Checkpoint 6 UI evidence for semantic themes, command context, shell layout, standard states, base views, safe dialogs, localization/accessibility, high-DPI baseline, and Windows/Ubuntu CI.
- Recorded Checkpoint 7 plugin-platform evidence for manifest validation, compatibility/parameters, runner/input access, typed results/provenance, the reference Dataset Profile plugin, reusable conformance checks, and Windows/Ubuntu CI.
- Recorded Checkpoint 9 workbench evidence for workspace persistence/restore, comparison state, navigation/search usability, session/external-change safety, background export/diagnostics contracts, and Windows/Ubuntu CI.

### Known legacy limitations

- Editing and export do not preserve correct data semantics for all shapes.
- Split focus and source ownership are ambiguous.

## Legacy HDF5 Viewer v0.3.1

- Theme initialization and toggle crash fixes.
- Automated Windows and Linux build workflow added.

## Legacy HDF5 Viewer v0.2.1

- Embedded edit controls in file panels.
- Added secondary panel behavior and plugin tracking.
- This release's historical test claims are retained only as history and are not a current verification baseline.
