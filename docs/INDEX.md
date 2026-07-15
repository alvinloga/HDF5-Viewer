# Data Viewer Documentation Index

## Source of truth

| Priority | Document | Defines |
|---:|---|---|
| 1 | `docs/decisions/*.md` | Accepted irreversible decisions |
| 2 | `docs/PRODUCT_SPEC.md` | Product requirements and success criteria |
| 3 | `docs/DATASOURCE_API.md` | Data adapter public contract |
| 3 | `docs/PLUGIN_API.md` | Plugin public contract |
| 3 | `docs/WORKSPACE_FORMAT.md` | Workspace schema contract |
| 4 | `ARCHITECTURE.md` | Module boundaries and runtime flow |
| 5 | behavior specs under `docs/` | Format, editing, UI, testing, dependencies, performance budgets |
| 5 | `docs/CONFIGURATION.md` | Platform config schema, locations, and legacy migration rules |
| 5 | `docs/FORMAT_INVENTORY.md` | Current format inventory and checkpoint evidence |
| 6 | `tasks/plan.md` | Implementation ordering and checkpoints |
| 7 | `tasks/todo.md` | Executable work items |

## Required reading by task

| Task type | Required documents |
|---|---|
| Data source | PRODUCT_SPEC, ARCHITECTURE, FORMAT_SUPPORT, DATASOURCE_API, ADR-002, ADR-007 |
| Editing/export | PRODUCT_SPEC, SAFE_EDITING, DATASOURCE_API, ADR-004 |
| Background work | ARCHITECTURE, TESTING, ADR-003 |
| Plugin | PLUGIN_API, FORMAT_SUPPORT, TESTING, ADR-005 |
| Workspace | WORKSPACE_FORMAT, SAFE_EDITING, ADR-006 |
| Configuration | CONFIGURATION, MIGRATION, TESTING |
| UI | UI_UX_SPEC, ARCHITECTURE, ADR-009 |
| Performance/hardening | TESTING, PERFORMANCE_BUDGETS, ARCHITECTURE |
| Packaging/CI | TESTING, DEPENDENCIES, ADR-008 |

## Historical documents

- `RELEASE.md` describes legacy release history only.
- `TEST_REPORT.md` is a current evidence ledger, not a marketing report.
- `TODO.md` redirects to `tasks/todo.md`.
