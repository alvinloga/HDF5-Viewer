# ADR-006: Versioned External-Reference Workspace

- Status: Accepted
- Date: 2026-07-11

## Context

Users need to restore files, views, comparisons, layouts, and plugin parameters. Embedding scientific payloads would make workspaces huge and duplicate data; serializing Python/Qt objects would be unsafe and brittle.

## Decision

Use a bounded, schema-validated UTF-8 JSON `.dvw` manifest with integer major `schema_version`. It references source files by relative/absolute paths plus identity hints and stores semantic state/provenance, not library objects or bulk data.

Loading supports partial/degraded restoration, explicit relocation, stale-result detection, and newer-version read-only protection. Saving is deterministic and atomic. Workspace dirty state is independent from source-document dirty state.

## Alternatives

- Pickle application state: rejected as unsafe and version-fragile.
- Embed all source data: rejected due to size, duplication, and unclear authority.
- Store only absolute paths: rejected for portability.
- Silently search and relink moved files: rejected due to ambiguous scientific identity.

## Consequences

- A JSON Schema and migration golden tests are required.
- Shared workspaces may reveal paths, so sharing receives a privacy warning.
- Missing sources do not prevent available sources from restoring.
- Large plugin results are recomputed or stored separately, with provenance retained.

## Related documents

`docs/WORKSPACE_FORMAT.md`, `docs/SAFE_EDITING.md`.
