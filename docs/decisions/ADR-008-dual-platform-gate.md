# ADR-008: Windows and Linux Are Equal Release Gates

- Status: Accepted
- Date: 2026-07-11

## Context

The application uses Qt and several native scientific libraries. A source-level test suite does not prove that packaged binaries launch, locate Qt plugins, handle paths, or behave correctly on both requested platforms.

## Decision

V1 releases only when the same functional acceptance matrix and packaged smoke suite pass on Windows x86-64 and supported Linux x86-64. CI builds, tests, packages, installs/launches, opens representative files/workspaces, and records checksums on both.

Platform-specific behavior is allowed only behind an explicit adapter and documented acceptance difference; core scientific semantics remain equal.

## Alternatives

- Windows-first release with Linux best effort: rejected by the explicit product requirement.
- Build artifacts without running them: rejected because native dependency and Qt plugin failures occur only after packaging.
- Use one platform's tests as proxy: rejected due to filesystem, locking, font, display, and packaging differences.

## Consequences

- Release cadence is constrained by the slower/failing platform.
- Platform fixtures cover Unicode paths, permissions/locks, high DPI, and temporary/atomic behavior.
- CI and artifact size increase.
- Supported Linux baseline must be named in release documentation.

## Related documents

`docs/TESTING.md`, `docs/DEPENDENCIES.md`.
