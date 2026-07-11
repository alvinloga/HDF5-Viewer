# Changelog

All notable Data Viewer changes are recorded here.

## Unreleased

### Added

- Added the installable `data_viewer` package skeleton with one canonical development version and a migration-safe command-line entry point.
- Added deterministic, generated HDF5, NPY, and CSV fixture factories with recorded creation parameters for reusable scientific-data tests.

### Fixed

- Stabilized the legacy GUI regression suite on Windows and Linux by isolating process state, scoping themes to each main window, and closing data-load panels cooperatively before their shared HDF5 sessions close.
- Removed one structurally proven duplicate legacy event-bus test while retaining its canonical regression coverage.

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
