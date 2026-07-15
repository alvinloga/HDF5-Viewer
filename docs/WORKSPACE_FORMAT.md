# Data Viewer Workspace Format v1

## 1. Purpose

A workspace is a versioned JSON manifest with extension `.dvw`. It references scientific files; it does not embed their bulk data. It restores navigation, view, comparison, plugin-result provenance, and layout state while remaining inspectable and recoverable.

## 2. Safety and privacy

- A workspace never contains credentials, file contents, arbitrary Python objects, executable code, or plugin instances.
- Opening a workspace does not run plugins automatically.
- Paths may reveal sensitive directory names; the UI warns before sharing a workspace.
- Unknown fields are preserved during a read-modify-write cycle when feasible.
- The parser enforces byte, depth, collection, and string-length budgets.
- The manifest is validated against `workspace-v1.schema.json` before use.

## 3. Top-level schema

```json
{
  "$schema": "https://dataviewer.local/schemas/workspace-v1.schema.json",
  "schema_version": 1,
  "app": {
    "name": "Data Viewer",
    "version": "1.0.0"
  },
  "workspace_id": "018f73cf-d5aa-7bd0-8b80-1fd928f9c714",
  "title": "Experiment comparison",
  "created_at": "2026-07-11T08:00:00Z",
  "updated_at": "2026-07-11T09:30:00Z",
  "path_base": "workspace_directory",
  "sources": [],
  "views": [],
  "comparisons": [],
  "plugin_results": [],
  "layout": {},
  "preferences": {},
  "extensions": {}
}
```

All timestamps use UTC RFC 3339 with `Z`. IDs use UUIDv7 where available and are opaque to consumers.

## 4. Source reference

```json
{
  "source_id": "src-01J2R3N4E5",
  "display_name": "run_04.h5",
  "path": "data/run_04.h5",
  "path_kind": "relative",
  "format_id": "hdf5",
  "fingerprint": {
    "size": 8493210,
    "mtime_ns": 1783756800000000000,
    "prefix_sha256": "hex-value"
  },
  "open_options": {},
  "status_hint": "available"
}
```

Rules:

- Prefer a relative path when the source lies under or near the workspace directory.
- `path_kind` is `relative` or `absolute`; environment-variable interpolation is forbidden.
- The fingerprint is an identity hint, not proof of authenticity.
- `open_options` contains only adapter-defined JSON values such as confirmed CSV dialect/encoding.
- Credentials and file handles are forbidden.

## 5. View state

```json
{
  "view_id": "view-01J2R3P0C1",
  "source_id": "src-01J2R3N4E5",
  "resource_path": "/results/field",
  "resource_domain": "array",
  "view_type": "table",
  "selection": {
    "kind": "hyperslab",
    "start": [0, 0, 20],
    "stop": [1, 128, 21],
    "step": [1, 1, 1]
  },
  "cursor": [0, 12, 20],
  "scroll": {"row": 0, "column": 0},
  "display": {
    "numeric_precision": 6,
    "value_mode": "raw",
    "colormap": "viridis"
  },
  "split_group": "split-left",
  "pinned": false
}
```

`resource_path` and selection syntax follow `docs/DATASOURCE_API.md`. Adapter-specific display fields live below `display.extensions.<format_id>` and must not be required to open the resource.

## 6. Comparison state

```json
{
  "comparison_id": "cmp-01J2R3Q7A9",
  "left": {
    "source_id": "src-left",
    "resource_path": "/results/field",
    "resource_domain": "array",
    "display_name": "baseline",
    "shape": [128, 128],
    "dtype": "float64",
    "columns": [],
    "fingerprint": {"size": 8493210}
  },
  "right": {
    "source_id": "src-right",
    "resource_path": "/results/field",
    "resource_domain": "array",
    "display_name": "candidate",
    "shape": [128, 128],
    "dtype": "float64",
    "columns": [],
    "fingerprint": {"size": 8493288}
  },
  "alignment": {
    "mode": "by_index"
  },
  "difference_mode": "absolute",
  "linked_navigation": true,
  "compatibility": {
    "shape_compatible": true,
    "column_compatible": false,
    "reason": "exact shape"
  },
  "result_id": "result-01J2R3S2M4",
  "provenance": {
    "left_source_id": "src-left",
    "left_resource_path": "/results/field",
    "left_fingerprint": {"size": 8493210},
    "right_source_id": "src-right",
    "right_resource_path": "/results/field",
    "right_fingerprint": {"size": 8493288},
    "alignment_mode": "by_index",
    "difference_mode": "absolute"
  }
}
```

Restoration validates compatibility again. A stored alignment never bypasses current safety checks.

The DV-0903 implementation provides the non-GUI comparison state surface in `data_viewer.app.compare`:

- `ComparisonSide` records left/right source identity, resource path/domain, display name, shape, dtype, table columns, and fingerprint provenance.
- `ComparisonAlignment` requires an explicit mode: `by_index`, `by_axis`, or `by_column`.
- `by_index` and `by_axis` require exact same shape; no implicit broadcasting is permitted. `by_axis` additionally requires a same-rank axis permutation.
- `by_column` requires explicit non-duplicated `left↔right` column matches; unknown columns fail validation.
- `ComparisonController.create_comparison(...)` validates compatibility before payload comparison and exposes a Qt-free `ComparisonViewState` containing visible left/right identity, alignment label, difference label, and linked-navigation state.
- `ComparisonController.save_to_workspace(...)` stores one comparison entry and marks only the workspace dirty. `restore_from_workspace(...)` restores valid comparison entries and records invalid ones as structured restore errors instead of aborting workspace load.

## 7. Plugin result provenance

```json
{
  "result_id": "result-01J2R3S2M4",
  "plugin_id": "org.dataviewer.descriptive_statistics",
  "plugin_version": "1.0.0",
  "api_version": 1,
  "input": {
    "source_id": "src-01J2R3N4E5",
    "resource_path": "/results/field",
    "selection": {"kind": "all"},
    "source_fingerprint": {"size": 8493210, "mtime_ns": 1783756800000000000}
  },
  "parameters": {"axis": 0, "nan_policy": "omit"},
  "result_kind": "table",
  "materialization": "recompute_required",
  "created_at": "2026-07-11T09:20:00Z",
  "status": "stale"
}
```

V1 stores parameters and provenance but does not embed arbitrary binary results. Small JSON-safe scalar/table summaries may be embedded under a size budget and must still be marked stale if input fingerprints change.

## 8. Layout and preferences

Layout stores semantic positions, not raw Qt object serialization:

```json
{
  "layout": {
    "active_view_id": "view-01J2R3P0C1",
    "left_panel": {"visible": true, "width": 280, "section": "structure"},
    "inspector": {"visible": true, "width": 320, "section": "statistics"},
    "bottom_panel": {"visible": true, "height": 220, "section": "tasks"},
    "splits": [{"id": "split-left", "orientation": "horizontal", "weight": 1.0}]
  }
}
```

Workspace preferences may contain view-specific precision, theme override, and navigation options. Machine-global preferences, cache paths, recent files, pinned files, resource favorites, semantic navigation history, global-search filters, and secrets stay in application configuration.

The DV-0904 implementation provides the non-GUI navigation/search state surface in `data_viewer.app.navigation`:

- `NavigationService` stores recent files, pinned recent files, and resource favorites in application configuration, not in `.dvw` workspaces.
- Recent-file entries record resolved paths, pinned state, and missing-file state. Missing recent items expose remediation actions such as Locate and Remove.
- `ResourceFavorite` uses `(source_id, resource_path)` identity and treats display labels as mutable presentation only.
- `NavigationHistory` records semantic source/resource/view/split targets for Back and Forward rather than arbitrary widget focus.
- `SearchQuery` supports path text, name text, domain, dtype substring, exact shape, and optional regular-expression matching.
- Search is grouped by resource domain and honors cooperative cancellation; invalid regular expressions fail with a structured `SearchQueryError` before returning partial results.

## 9. Load algorithm

1. Read with strict UTF-8 and bounded size.
2. Parse JSON without object hooks.
3. Validate schema and `schema_version` before resolving any path.
4. Normalize workspace path, then resolve relative source paths without changing the manifest.
5. Classify each source as available, moved candidate, missing, changed, unsupported, or failed.
6. Open available sources asynchronously; never block loading all views on one failure.
7. Restore view shells, then resource metadata, then bounded visible payloads.
8. Mark results stale when fingerprints or plugin versions differ.
9. Enter degraded mode if any source/view cannot restore; keep usable content available.

Startup session restore is application state, not embedded workspace state:

- `SessionRestoreService` records only the last workspace pointer and clean-shutdown flag in application configuration/recovery state.
- Startup decisions are safe values: ask, restore, skip, or missing. They do not open a workspace by themselves.
- Ask mode offers Restore, Skip, and Forget. Missing pointers offer Locate and Forget.
- Clean shutdown suppresses automatic restore; crash/restart recovery keeps the pointer until the user or policy decides.

## 10. Missing and moved files

Relocation searches are explicit and bounded:

- first check the stored absolute/relative path;
- optionally check a user-selected replacement root using the stored basename, relative suffix, size, and prefix hash;
- present candidates; never silently choose an ambiguous match;
- update the manifest only after user confirmation and Save Workspace;
- allow Skip, Locate, Locate Folder, Remove Reference, and Cancel.

Degraded mode retains source references, view definitions, and plugin provenance so a later relink can fully restore them.

The DV-0902 implementation provides the non-GUI restore planning surface in `data_viewer.workspace.restore`:

- `WorkspaceRestoreCoordinator.plan_restore(...)` resolves each persisted source path without mutating the manifest, classifies source state, prepares view shells, and marks plugin results current or stale.
- Source states are explicit: `available`, `moved_candidate`, `missing`, `changed`, `ambiguous`, `unsupported`, and `failed`.
- Relocation matching is bounded to user-provided replacement roots and uses basename plus persisted fingerprint hints such as `size`, `mtime_ns`, and `prefix_sha256`. A single match is reported as a candidate; multiple matches are ambiguous.
- `apply_confirmed_relocations(...)` changes only user-confirmed source IDs, stores deterministic relative paths from the workspace directory where possible, and marks the workspace dirty for a later Save Workspace operation.
- View shells are restored before metadata and payload reads. Available sources produce pending payload shells; unavailable or changed sources produce blocked shells that keep the original source/resource identity visible.
- `plan_restore_async(...)` runs the same planning contract asynchronously and honors cooperative cancellation before and during relocation scanning.

## 11. Persistence

Workspace saving uses the atomic replacement protocol from `docs/SAFE_EDITING.md`:

- deterministic UTF-8 JSON with two-space indentation and trailing newline;
- stable ordering for human review;
- temporary sibling, flush, schema revalidation, atomic replace;
- no automatic source-file saves;
- dirty source documents and dirty workspace state are independent.

## 12. Versioning and migration

- `schema_version` is an integer major version.
- Readers support the current version and explicitly implemented older migrations.
- Writers emit only the current version.
- A migration is a pure transformation with golden input/output tests and an ADR when semantics change.
- A newer unsupported major version opens in read-only diagnostic mode and is never overwritten.
- Additive optional fields remain within version 1; changing meaning or removing a field requires version 2.

## 13. Required schema and tests

Implementation must add `data_viewer/workspace/schema/workspace-v1.schema.json` and tests for:

- minimal and complete valid manifests;
- every invalid required type/value;
- unknown-field preservation;
- UTF-8 and non-ASCII paths on Windows/Linux;
- relative, absolute, moved, missing, and ambiguous sources;
- changed fingerprint and stale plugin result;
- partial failures/degraded mode;
- deterministic round trip;
- interrupted save and newer-version protection;
- malicious paths, oversized JSON, deep nesting, and unexpected object-like input.
