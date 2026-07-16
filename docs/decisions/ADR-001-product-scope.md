# ADR-001: Data Viewer Product Scope

- Status: Accepted
- Date: 2026-07-11

## Context

The repository is an HDF5-focused viewer, while the intended product is a general scientific workbench for viewing, analysis, comparison, and safe editing. The name, release formats, edit boundary, and platform commitment must be fixed before architecture work.

## Decision

Rename the target product to **Data Viewer**. V1 is a local-first PySide6 desktop application with equal Windows and Linux acceptance.

V1 supports HDF5, NPY, NPZ, CSV, TSV, TXT, MAT, NIfTI, XLSX, JSON, YAML/YML, plus each format's outer `.gz` form. HDF5/NPY/NPZ/CSV/TSV/TXT support safe editing. MAT/NIfTI/XLSX/JSON/YAML and generic gzip wrappers are read-only with Save As/export. NetCDF and Zarr are excluded.

## Alternatives

- Keep the HDF5 Viewer name: rejected because it misstates the multi-format product.
- Ship every format as editable: rejected because safe faithful writers and validation exceed v1 risk tolerance.
- Keep NetCDF/Zarr: rejected by current product prioritization.
- Validate only Windows: rejected because Linux is an explicit user requirement.

## Consequences

- The legacy app is migration input and documentation must distinguish current from target.
- Format support requires real adapter conformance, not filename recognition.
- Name/version/artifact migration is a tracked release task.
- Both platform matrices may delay release; one-platform success cannot waive the other.

## Related documents

`docs/PRODUCT_SPEC.md`, `docs/FORMAT_SUPPORT.md`, `docs/MIGRATION.md`.
