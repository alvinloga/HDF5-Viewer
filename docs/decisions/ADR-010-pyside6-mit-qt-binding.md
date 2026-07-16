# ADR-010: Use PySide6 to Preserve MIT Distribution

- Status: Accepted
- Date: 2026-07-16

## Context

Data Viewer is intended to remain an MIT-licensed open-source desktop scientific workbench. The previous Qt binding, PyQt6, supports GPLv3 or a commercial Riverbank license. Keeping PyQt6 while distributing public binaries would either require changing the project to a GPL-compatible distribution model or obtaining a commercial license.

The project owner chose to keep the project MIT-licensed and migrate the Qt binding instead.

## Decision

Use **PySide6 / Qt for Python** as the v1 Qt binding and keep the Data Viewer project license as **MIT**.

Release evidence treats the Qt binding decision as satisfied only when:

- `pyproject.toml` declares `PySide6` as the direct Qt runtime dependency;
- `pyproject.toml` keeps `license = "MIT"`;
- dependency policy documents PySide6 LGPL-compatible distribution obligations;
- CI imports PySide6 on Windows and Linux;
- release artifacts include SBOM, license notices, checksums, and security review evidence.

## Alternatives

### Keep PyQt6 and publish Data Viewer as GPLv3

- Pros: Smallest technical migration.
- Cons: Changes the project licensing model and downstream obligations.
- Rejected because the owner explicitly selected MIT distribution.

### Keep PyQt6 and buy a commercial license

- Pros: Small technical change and allows non-GPL distribution.
- Cons: Requires a paid external license and future license management.
- Rejected for v1 because the project can use PySide6 instead.

### Defer public binary release

- Pros: Avoids an immediate migration.
- Cons: Leaves the release gate blocked and prevents completing the requested Windows/Linux release.
- Rejected because v1 requires distributable artifacts.

## Consequences

- All direct `PyQt6` imports must migrate to `PySide6`.
- The universal lock and CI direct-import smoke must be regenerated for PySide6.
- Any PyQt-specific signal/slot/type APIs must be reviewed before use; v1 code should prefer binding-neutral Qt APIs where possible.
- Release evidence must continue to include third-party notices and artifact checksums, and LGPL obligations remain a release checklist item.

## Related documents

`docs/DEPENDENCIES.md`, `docs/TESTING.md`, `RELEASE.md`, `tasks/todo.md`.
