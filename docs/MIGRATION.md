# Legacy HDF5 Viewer to Data Viewer Migration

## 1. Strategy

The migration is incremental and vertical. The existing application remains a behavioral reference, not the target architecture. New target code lives under `data_viewer/`; compatibility bridges may call legacy code temporarily but new public contracts must not depend on legacy GUI types.

Each phase must leave the repository runnable and its completed scope tested. Do not perform a repository-wide rename/refactor before Phase 0 evidence and core contracts are in place.

## 2. Legacy inventory

Current source areas:

| Legacy area | Role | Migration disposition |
|---|---|---|
| `main.py` | historical entry point and legacy app bootstrap | removed in DV-1008; target launch is `python -m data_viewer` |
| `core/` | HDF5-centric loading/models/cache | extract behavior; replace through DataSource/domain contracts |
| `gui/` | shell, tabs, trees, views | retain useful interaction patterns; rebuild against controllers/state |
| `plugins/` | built-in analyses/plots coupled to current app | port one by one to Plugin API v1 |
| `services/` | legacy export/search services | removed in DV-1008 after target export queue/exporting/navigation coverage |
| `utils/` | empty compatibility package by DV-1008 review | removed in DV-1008; no target code depends on it |
| `config.json` | repository-local settings | migrate to versioned platform config |
| `HDF5Viewer.spec`, build scripts | packaging | replace names/paths and add smoke tests |

No legacy module is deleted merely because a target directory exists. Deletion follows parity tests and import/reference search.

## 3. Strangler sequence

### Stage A — trustworthy baseline

- lock environment and make test collection reliable;
- isolate test config/user directories;
- record current behavioral and packaging evidence;
- introduce `pyproject.toml`, quality commands, and CI test jobs.

### Stage B — target skeleton and contracts

- create `data_viewer.domain`, `sources.api`, application task/error/config primitives;
- add adapter and plugin conformance harnesses;
- add new bootstrap behind a developer feature flag if necessary.

### Stage C — HDF5 vertical slice

- open/probe/list metadata/read bounded payload through the new adapter;
- display through a target controller and one table/array view;
- implement active context, cancellation, close ownership, and structured errors;
- compare the vertical slice with legacy HDF5 fixtures.

### Stage D — safe editing and export

- patch model and review UI;
- HDF5/NPY/NPZ/text transaction paths;
- explicit scope export receipts;
- fault injection before enabling overwrite by default.

### Stage E — remaining adapters

- add each adapter independently through conformance gates;
- add generic gzip last so it composes with already-correct inner adapters;
- remove NetCDF/Zarr registration and stale claims.

### Stage F — shell/design system/workspace

- migrate shell and semantic tokens without breaking the target vertical slice;
- restore view/workspace state through versioned JSON;
- add compare workspace and relocation/degraded behavior.

### Stage G — plugins

- ship registry/runner/parameter/result infrastructure;
- port statistics and visualization plugins one at a time;
- remove direct plugin access to GUI widgets/source handles.

### Stage H — name, packaging, release

- change product/window/package/artifact names to Data Viewer in one audited task;
- migrate config location and version source;
- build and smoke Windows/Linux artifacts;
- remove legacy packages only after reference and parity checks;
- update evidence documents and release notes.

## 4. Compatibility bridges

A bridge must:

- live in an explicitly named `legacy_compat` module;
- adapt legacy values into target immutable types;
- have tests for assumptions and error mapping;
- carry a removal task ID from `tasks/todo.md`;
- never be imported by target public API modules;
- never expand the legacy API surface.

## 5. Name migration checklist

Search case-insensitively for `HDF5 Viewer`, `HDF5Viewer`, artifact names, application organization, config paths, window titles, About text, icons, spec files, CI artifact names, test snapshots, documentation, and MIME/desktop entries. The migration is complete only when remaining occurrences are explicitly historical.

Version has one canonical source in package metadata. Runtime, About, diagnostics, artifacts, manifests, and release notes read the same value. Existing git tags remain unchanged historical records.

## 6. Configuration migration

- New configuration uses `QStandardPaths`/platformdirs and a versioned schema.
- On first target launch, detect legacy `config.json`, validate known keys, show the migration decision, and write target config atomically.
- Never mutate or delete the legacy file automatically.
- Unknown/invalid legacy values produce warnings and safe defaults.
- Tests redirect all locations to temporary directories.

## 7. Removal criteria

Legacy code for a capability can be removed only when:

- target acceptance tests cover successful, empty, malformed, cancellation, and close flows;
- representative legacy fixtures behave equivalently or deliberate differences are documented;
- no runtime/test/build imports reference it (`rg` plus import smoke);
- target documentation and diagnostics exist;
- both platform CI jobs pass;
- a rollback is possible through version control without data migration loss.

## 8. Rollback policy

Before the target becomes default, a feature flag may select the legacy flow in development builds. Once target persistence writes a new format, rollback must still read the previous stable workspace/config version or leave the file untouched. Source scientific files never require an irreversible migration merely to open them.

## 9. Anti-patterns

- big-bang move/rename followed by weeks of broken imports;
- wrapping every legacy object and calling it architecture completion;
- duplicating domain types in GUI/plugins;
- deleting tests because they expose timing or ownership problems;
- using feature flags without owner/removal criteria;
- claiming format support after extension recognition only;
- changing on-disk semantics without fixtures and an ADR.
