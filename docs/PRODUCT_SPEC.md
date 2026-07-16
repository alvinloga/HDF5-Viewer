# Product Specification: Data Viewer v1

## 1. Objective

Build a cross-platform desktop scientific data workbench that lets technical users inspect, analyze, visualize, compare, safely edit, and export common scientific file formats without loading uncontrolled amounts of data or losing provenance.

### Target users

- researchers inspecting experiment outputs;
- data engineers validating files and conversions;
- algorithm developers debugging arrays and tables;
- neuroimaging researchers viewing NIfTI MRI volumes;
- reviewers comparing results across files, versions, or pipelines.

### Primary user stories

1. Open a large supported file and browse its structure without a frozen UI.
2. Select a resource and inspect metadata before reading the payload.
3. View a bounded slice with explicit original coordinates.
4. Run a compatible analysis or visualization with reproducible parameters.
5. Compare two resources and understand incompatibilities before computation.
6. Edit supported formats using patches, review changes, and save safely.
7. Export full data, current slice, selection, result, or visualization with explicit scope.
8. Save a workspace and restore it even if some referenced files moved.

## 2. Confirmed scope

### Product

- Name: Data Viewer.
- Platforms: Windows and Linux are equal release gates.
- Mode: desktop application using PySide6.
- Connectivity: offline by default; no telemetry or automatic upload.
- Plugin trust: built-in plugins only in v1.

### Formats

First release:

- HDF5;
- NPY and NPZ;
- CSV, TSV, TXT;
- MAT;
- NIfTI `.nii` and `.nii.gz`;
- XLSX;
- JSON;
- YAML/YML;
- outer `.gz` wrapper for every listed format.

Not in v1:

- NetCDF and Zarr;
- DICOM;
- Parquet and Arrow IPC;
- DICOM networking or PACS;
- arbitrary raw binary import;
- pickle, joblib, or arbitrary Python object deserialization.

## 3. Functional requirements

### FR-001 Open and identify

- Use extension as a candidate hint, then validate format content.
- Recognize compound extensions such as `.nii.gz` and `.h5.gz`.
- Produce a structured error for unsupported, malformed, encrypted, or truncated input.
- Never execute embedded or serialized code while probing.

### FR-002 Browse

- Hierarchical sources load direct children on demand.
- Flat sources expose a synthetic root and stable resource nodes.
- Metadata remains available without loading the full payload when the format permits.
- Search supports path/name, domain, dtype, ndim, shape filters, and regex.

### FR-003 View

- Scalar, 1D, 2D, high-dimensional, table, text, structured, workbook, and volume resources use dedicated views.
- The UI always displays source path, node path, shape, dtype/domain, active slice, and data-scope mode.
- High-dimensional arrays use axis/index controls instead of implicit flattening.
- Tables use virtualized rows and columns.

### FR-004 Data scale

- Small operations may use full data.
- Medium operations use chunks or pages.
- Large operations require a declared sample or user-approved full operation.
- Estimated bytes and operation mode are visible before expensive work.
- Default memory cache budget: 512 MiB, configurable.
- Default temporary extraction budget: min(20 GiB, 25% of free space), configurable.

Threshold values are policy defaults, not hard-coded format rules. The budget service makes the final decision from dtype, shape, compression, free memory, and free disk.

### FR-005 Analyze and visualize

- Only compatible plugins are enabled.
- Every execution records plugin ID/version, resource ID, slice, parameters, scope, sample method, seed, start/end time, and outcome.
- Long-running plugins support progress and cooperative cancellation.
- Full visualization widgets render in workspace tabs.

Required statistics:

- dataset profile;
- descriptive statistics;
- distribution and outlier summary;
- correlation/covariance;
- dataset comparison metrics.

Required visualizations:

- line, scatter, histogram, box plot;
- image viewer;
- high-dimensional slice navigator;
- correlation heatmap;
- missing-data map;
- NIfTI orthogonal viewer.

### FR-006 Compare

- Compare metadata before payload.
- Arrays require explicit shape compatibility or a selected broadcast policy.
- Tables require explicit column matching.
- NIfTI comparison checks shape, voxel size, orientation, and affine.
- No implicit resampling, registration, or spatial reorientation.
- Results state exact metric definitions and invalid/missing-value policy.

### FR-007 Safe editing

- Read-only is the initial state.
- HDF5, NPY, NPZ, CSV, TSV, and TXT support v1 editing.
- MAT, NIfTI, XLSX, JSON, YAML, and gzip-wrapped inputs are read-only in v1.
- Edits are typed patches against original coordinates/keys.
- Undo, redo, discard, review, Save, and Save As are supported where applicable.
- A source fingerprint conflict blocks save until the user reloads or saves a copy.
- Failed saves cannot damage the original.

### FR-008 Export

- Scope options: full resource, current slice, current selection, plugin result, visualization.
- Export destination and overwrite behavior are explicit.
- Background export supports progress and cancellation.
- CSV export protects against spreadsheet formula injection by default.
- Exported arrays preserve shape and dtype when the target format can represent them.

### FR-009 Workspace

- File extension: `.dvw`.
- Workspace schema version: 1.
- Saves external references, tabs, split tree, active view, slices, favorites, comparisons, plugin runs, and optional result-cache references.
- Does not embed large source data.
- Missing references do not prevent the rest of the workspace from opening.
- Relocation supports exact path, relative path, filename+size, and optional fingerprint matching.

### FR-010 Diagnostics

- Problems panel shows structured errors with copyable details.
- Tasks panel shows background work, progress, cancellation, duration, and outcome.
- Diagnostics export includes app/runtime/library versions, platform, plugin inventory, redacted paths, and recent structured logs.
- No diagnostic data uploads automatically.

## 4. Non-functional requirements

### Performance

- Initial shell visible within 2 seconds on the reference CI desktop after warm OS startup.
- Opening a file and showing root metadata within 2 seconds when the format header is local and under 10 MiB.
- Expanding a hierarchy node with 1,000 direct children within 1 second after I/O completion.
- UI event loop must not perform payload reads expected to exceed 50 ms.
- Table view must not materialize more than the configured page/cache budget.
- Cancellation acknowledgement target: 250 ms for cooperative Python operations; native calls may finish the current bounded chunk.

### Reliability

- No `QThread.terminate()`.
- No source closes while an I/O lease is active.
- Stale task results are ignored by generation ID.
- Atomic save leaves either the old complete file or the new complete file.
- Temporary extraction is cleaned on success, cancellation, failure, and next-start recovery.

### Security

- `allow_pickle=False` for NumPy formats.
- YAML safe loading only.
- XLSX macros/external links are not executed.
- Workspace and plugin manifests are schema-validated.
- Built-in plugins are imported from packaged modules only.
- No shell command is constructed from file content.

### Accessibility

- All primary workflows are keyboard accessible.
- Visible focus is present in both themes.
- Information is not conveyed by color alone.
- Body text and controls meet WCAG AA contrast targets where applicable to desktop UI.

### Cross-platform

- All release-blocking tests run on Windows and Linux for the same commit.
- Paths, atomic replacement, temporary files, fonts, shortcuts, and packaging have platform-specific contract tests.
- No feature is documented as released if it only works on one platform.

## 5. Technology policy

Target runtime:

- Python 3.11 and 3.12 source compatibility;
- Python 3.12 release builds;
- PySide6 for desktop UI;
- NumPy as the shared numeric interchange type;
- format libraries isolated behind adapters;
- Matplotlib for v1 plots and MRI slice rendering;
- PyInstaller for Windows and Linux packaging.

Exact dependency pins are produced and verified during Phase 0. See `docs/DEPENDENCIES.md`.

## 6. Commands

### Current target commands

```bash
python -m pip install -r requirements-dev.txt
python -m data_viewer
python -m pytest -q
python -m ruff check .
python -m mypy data_viewer
python -m coverage run -m pytest
python -m coverage report --fail-under=85
python build.py --clean --test --windows
python build.py --clean --test --linux
```

## 7. Target project structure

```text
data_viewer/
  __main__.py
  app/
  domain/
  sources/
  tasks/
  plugins/
  workspace/
  services/
  ui/
tests/
  unit/
  contract/
  integration/
  gui/
  performance/
  fixtures/
docs/
  decisions/
tasks/
```

Detailed ownership is defined in `ARCHITECTURE.md`.

## 8. Testing strategy

- Unit tests for pure domain logic and parsers.
- Contract tests shared by all source adapters and plugins.
- Integration tests for source/task/edit/export/workspace boundaries.
- Offscreen GUI tests for focus, commands, state, and result routing.
- Performance tests for hierarchy, tables, chunking, gzip extraction, MRI slicing.
- Packaged smoke tests on Windows and Linux.
- Coverage gate: 85% overall after Phase 0; 95% for domain, workspace schema, edit protocol, and public API contracts.

See `docs/TESTING.md`.

## 9. Boundaries

### Always

- validate untrusted input at adapters;
- preserve data identity and provenance;
- use cooperative cancellation;
- add regression tests for defects;
- update docs with public behavior;
- keep Windows and Linux parity.

### Ask first

- add or remove runtime dependencies;
- change supported format/edit matrix;
- change public API or workspace schema;
- change product name, license, telemetry, or network behavior;
- alter CI release gates;
- enable external plugins.

### Never

- deserialize pickle/object arrays from untrusted input;
- call unsafe YAML loaders;
- execute spreadsheet macros or formulas;
- silently flatten/reorient/resample data;
- force-kill I/O threads;
- write directly to the original during a multi-step save;
- claim tests passed without reproducible evidence;
- implement NetCDF/Zarr in v1.

## 10. Success criteria

Data Viewer v1 is complete only when:

1. every v1 format and its gzip wrapper passes the format contract suite;
2. all required views, plugins, comparison, export, workspace, and editing flows meet their functional requirements;
3. Windows and Linux CI matrices are green for the same commit;
4. both packaged artifacts pass launch, open, analyze, edit-supported, workspace, and export smoke tests;
5. security tests prove pickle/YAML/XLSX/plugin boundaries;
6. performance budgets pass on recorded reference hardware;
7. docs match actual implementation and no target feature is falsely marked complete;
8. no Critical or Required code-review finding remains.

## 11. Open product decisions

The following defaults are specified but require final human acceptance before their implementation task begins:

- exact editing matrix for JSON/YAML/XLSX after v1;
- whether NIfTI label overlays enter v1.1 or a later release;
- external plugin SDK distribution mechanism after API v1 stabilizes;
- post-v1 Qt binding alternatives only if MIT distribution requirements change.
