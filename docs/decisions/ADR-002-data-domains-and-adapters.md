# ADR-002: Explicit Data Domains and DataSource Adapters

- Status: Accepted
- Date: 2026-07-11

## Context

Scientific formats have materially different models: arrays, hierarchies, tables, text, workbooks, structured documents, and spatial volumes. Treating them all as HDF5-like trees leaks library handles and produces incorrect viewing/editing semantics.

## Decision

Represent resources using explicit domains and capabilities. Stateless adapter factories open source-owned sessions through DataSource API v1. Metadata and bounded payload reads are separate. Public boundaries use immutable domain values/NumPy payloads and never expose pandas, h5py, NiBabel, SciPy, or openpyxl objects.

Stable `ResourceId` includes source identity and canonical resource path. Selections are normalized and preserve original coordinates. Direct-child listing is paginated.

## Alternatives

- One universal tree/dataset interface: rejected because it hides workbook, table, volume, and text semantics.
- Expose format library objects: rejected because it couples UI/plugins to handle lifetime, threading, and library versions.
- Convert all files to HDF5 on open: rejected because it is slow, lossy, storage-heavy, and changes provenance.

## Consequences

- UI and plugins dispatch on domain/capabilities, not extensions.
- Every adapter must pass one reusable conformance suite plus format tests.
- New formats can be added without changing views that already support their domain.
- Some format-specific metadata remains in namespaced immutable fields.

## Related documents

`ARCHITECTURE.md`, `docs/DATASOURCE_API.md`, `docs/FORMAT_SUPPORT.md`.
