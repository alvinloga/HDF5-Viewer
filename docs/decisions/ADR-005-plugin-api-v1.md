# ADR-005: Stable Built-in Plugin API v1

- Status: Accepted
- Date: 2026-07-11

## Context

Statistics and visualization must grow incrementally. Existing plugin code coupled to GUI widgets or raw handles would make each new format and UI refactor multiply maintenance cost. Loading arbitrary third-party Python also introduces an unsolved trust boundary.

## Decision

Define Plugin API `api_version=1` around validated manifests, capability compatibility, JSON-schema parameters, budgeted `InputAccess`, cooperative tasks, typed/declarative results, and complete provenance. Plugins do not import GUI/adapters or receive library handles.

V1 discovers only trusted built-ins packaged with the application. The contract is shaped to permit later process isolation but does not claim a third-party marketplace or sandbox.

## Alternatives

- Let plugins create arbitrary Qt widgets: rejected because it breaks design, lifecycle, accessibility, and isolation.
- Pass full arrays to every plugin: rejected due to uncontrolled memory.
- Use Python entry points for arbitrary installed packages in v1: rejected because permission, compatibility, signing, and isolation are unspecified.
- Hard-code every analysis into the inspector: rejected because incremental ownership and testing become poor.

## Consequences

- Each plugin is independently manifest-driven and conformance-tested.
- Plots are declarative and rendered by the application.
- Disabled compatibility reasons are visible.
- Future breaking API changes coexist under a new version with migration guidance.

## Related documents

`docs/PLUGIN_API.md`, `docs/TESTING.md`.
