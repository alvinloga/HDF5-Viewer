# ADR-004: Patch Editing and Verified Persistence

- Status: Accepted
- Date: 2026-07-11

## Context

Editing scientific files risks dtype coercion, coordinate mistakes, partial writes, loss of metadata, external-change overwrite, and silent corruption. Widget state is not a safe persistence model.

## Decision

Edits are immutable patches against a source fingerprint. Users review a change set before Save. Complete-file formats write a temporary sibling, flush, reopen/validate, atomically replace, and reopen. HDF5 may use direct in-place selections only under strict layout, fingerprint, backup/recovery, and post-write verification constraints; otherwise it uses verified replacement.

External changes enter a conflict state. V1 offers Reload, Save As, or Cancel and performs no automatic merge. Read-only formats never enable source overwrite.

## Alternatives

- Write on every cell edit: rejected because it prevents review/undo and magnifies failure risk.
- Always edit HDF5 in place: rejected for structural/verification/recovery risks.
- Always keep a full in-memory copy: rejected due to data scale.
- Auto-merge external changes: rejected because scientific conflict semantics are format/resource-specific.

## Consequences

- Disk-space preflight and fault injection are release requirements.
- Dirty state, undo/redo, conflicts, recovery, Save As, and export receipts are first-class features.
- Complete rewrites may be slower but provide clearer safety.
- Atomicity is stated only where the filesystem/platform primitive actually guarantees it.

## Related documents

`docs/SAFE_EDITING.md`, `docs/TESTING.md`.
