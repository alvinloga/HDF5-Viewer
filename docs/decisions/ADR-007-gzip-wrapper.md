# ADR-007: Universal Outer Gzip Support

- Status: Accepted
- Date: 2026-07-11

## Context

V1 must open gzip-wrapped versions of every supported format. Some inner formats stream naturally; others require random access. Treating all wrappers identically either breaks libraries or creates uncontrolled disk/memory use.

## Decision

Implement gzip as a composable source wrapper. Stream-capable text formats receive bounded decompression streams. Random-access formats extract into a managed application cache after free-disk, size/ratio, and budget checks. `.nii.gz` is handled as native NIfTI behavior. All generic gzip wrappers are read-only in v1.

Compound suffix recognition is longest-first and content-validated. Cancellation and startup cleanup remove incomplete/expired cache entries.

## Alternatives

- Decompress every file fully into memory: rejected due to scale.
- Require users to decompress manually: rejected by confirmed format scope.
- Pretend gzip streams provide random access: rejected because HDF5/ZIP/XLSX and similar readers require seeking.
- Write gzip-wrapped edits directly: rejected because transaction and nested compression semantics are not mature enough for v1.

## Consequences

- Random-access wrappers require temporary disk and clear progress.
- `.npz.gz`/`.xlsx.gz` are readable but discouraged as output.
- Compression bombs and corrupted streams have dedicated tests/errors.
- Cache identity and cleanup become application services.

## Related documents

`docs/FORMAT_SUPPORT.md`, `ARCHITECTURE.md`.
