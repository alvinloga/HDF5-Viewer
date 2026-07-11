# ADR-003: Cooperative Tasks and Source Ownership

- Status: Accepted
- Date: 2026-07-11

## Context

Large reads, decompression, exports, plugins, and workspace restoration can block the GUI or outlive source handles. Forced thread termination can corrupt state and allow stale results to overwrite newer navigation.

## Decision

All expensive operations use an application Task abstraction with queued, running, cancelling, succeeded, failed, and cancelled states. Cancellation is cooperative. Results carry request versions and are discarded if stale.

`DocumentController` owns source sessions. Views borrow stable IDs and request data through controllers; they never own handles. Closing waits for or cancels related tasks before session close. GUI updates occur only on the GUI thread.

## Alternatives

- Perform reads synchronously: rejected due to responsiveness requirements.
- Call `QThread.terminate()`: rejected because termination can leave locks/files/native libraries inconsistent.
- Give each tab its own file handle: rejected because ownership, caching, and close behavior become nondeterministic.
- Use async Python everywhere: rejected as a mandated implementation; Qt-compatible executors/tasks can satisfy the contract more directly.

## Consequences

- Adapters and plugins need cancellation checkpoints and progress reporting.
- UI exposes Tasks/Problems/Output states.
- Tests cover close-during-read, cancellation latency, and stale-result rejection.
- Libraries with noninterruptible calls are isolated behind bounded phases and cancellation takes effect at the next safe point.

## Related documents

`ARCHITECTURE.md`, `docs/DATASOURCE_API.md`, `docs/TESTING.md`.
