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
- Added DocumentController ownership and request-generation tracking (`data_viewer/app/documents.py` and `data_viewer/app/active_context.py`), including close/wait lifecycle cleanup and non-GUI dirty/active-task state hooks.
- Added platform path resolution and bounded temporary cache primitives (`data_viewer/infrastructure/paths.py`, `cache.py`), with atomic read/write configuration handling and log redaction support for diagnostics in `data_viewer/infrastructure/config.py` and `data_viewer/infrastructure/logging.py`.

### Fixed

- Stabilized the legacy GUI regression suite on Windows and Linux by isolating process state, scoping themes to each main window, and closing data-load panels cooperatively before their shared HDF5 sessions close.
- Removed one structurally proven duplicate legacy event-bus test while retaining its canonical regression coverage.
- Normalized lock-file evidence across Windows and Linux checkouts and verified release jobs stop when quality tests fail.

### Documentation

- Renamed the target product to Data Viewer.
- Defined the first-release multi-format scope.
- Defined Windows and Linux as simultaneous release gates.
- Added target architecture, product specification, public API contracts, workspace schema, UI specification, safe-editing protocol, testing policy, dependency policy, ADRs, and agent rules.
- Reclassified the existing source as the legacy migration baseline.

### Known legacy limitations

- Editing and export do not preserve correct data semantics for all shapes.
- Split focus and source ownership are ambiguous.
- Existing NetCDF/Zarr registration does not match the target scope.

## Legacy HDF5 Viewer v0.3.1

- Theme initialization and toggle crash fixes.
- Automated Windows and Linux build workflow added.

## Legacy HDF5 Viewer v0.2.1

- Embedded edit controls in file panels.
- Added secondary panel behavior and plugin tracking.
- This release's historical test claims are retained only as history and are not a current verification baseline.
