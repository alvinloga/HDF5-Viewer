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
  - `data_viewer/__main__.py` dispatches to target bootstrap by default with `--legacy` fallback and `--version` support.
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

### Fixed

- Stabilized the legacy GUI regression suite on Windows and Linux by isolating process state, scoping themes to each main window, and closing data-load panels cooperatively before their shared HDF5 sessions close.
- Removed one structurally proven duplicate legacy event-bus test while retaining its canonical regression coverage.
- Removed first-release NetCDF/Zarr product paths (DV-0411): legacy startup no longer imports/registers external NetCDF/Zarr sources, folder explorer defaults no longer advertise `.zarr`, optional dependency claims were removed, and the obsolete external source modules were deleted.
- Normalized lock-file evidence across Windows and Linux checkouts and verified release jobs stop when quality tests fail.

### Documentation

- Renamed the target product to Data Viewer.
- Defined the first-release multi-format scope.
- Defined Windows and Linux as simultaneous release gates.
- Added target architecture, product specification, public API contracts, workspace schema, UI specification, safe-editing protocol, testing policy, dependency policy, ADRs, and agent rules.
- Reclassified the existing source as the legacy migration baseline.
- Recorded Checkpoint 3 persistence evidence for HDF5 safe edits, generic transactions, export provenance, and edit/export UI flows on Windows and Ubuntu CI.
- Recorded Checkpoint 4 uncompressed format evidence for all v1 first-release adapters on Windows and Ubuntu CI.

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
