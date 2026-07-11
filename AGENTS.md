# Data Viewer Agent Contract

This file is mandatory context for every agent working in this repository.

## 1. Read order

Before changing code, read in this order:

1. `README.md`
2. `docs/PRODUCT_SPEC.md`
3. `ARCHITECTURE.md`
4. the relevant API or behavior document under `docs/`
5. relevant ADRs under `docs/decisions/`
6. `tasks/plan.md`
7. the selected task in `tasks/todo.md`
8. existing source and tests touched by that task

If documents conflict, use this precedence:

```text
Accepted ADR
  > PRODUCT_SPEC
  > public API documents
  > ARCHITECTURE
  > FORMAT/UI/TESTING behavior specs
  > tasks/plan.md
  > tasks/todo.md
  > README
  > legacy source behavior
```

Do not silently resolve a conflict. Update the lower-precedence document in the same change.

## 2. Current-state warning

The repository still contains the legacy HDF5 Viewer implementation. Target Data Viewer modules described in the architecture do not all exist yet.

Never claim a target feature is implemented because it appears in a specification. A feature is implemented only when:

- its task is checked in `tasks/todo.md`;
- required tests pass;
- Windows and Linux behavior is verified where applicable;
- documentation describes actual behavior;
- no known Critical or Required review issue remains.

## 3. Task discipline

- Work on one task ID from `tasks/todo.md` at a time.
- If a task touches more than five product files, split it before implementation.
- Write the failing test first for behavior changes.
- Keep the application runnable after each task.
- Do not mix structural refactoring with unrelated feature work.
- Do not add a new dependency without updating `docs/DEPENDENCIES.md` and obtaining human approval.
- Do not change an accepted public contract without a new ADR and migration note.

## 4. Non-negotiable correctness rules

### Data identity

- A resource is identified by canonical file URI plus node path.
- Normalize paths before registry lookup.
- Never use display labels as identifiers.
- Never infer the active resource by scanning private GUI fields.

### Original data vs presentation

- Raw source data, normalized domain data, and presentation projection are distinct objects.
- Row numbers are table headers, never injected data columns.
- High-dimensional arrays are never flattened for editing or NPY export.
- Every result records whether it used full data, a chunk, a slice, or a sample.

### Threading and lifecycle

- Never call `QThread.terminate()`.
- Cancellation is cooperative through a token and request generation.
- A stale task result must not update current UI state.
- A source cannot close while a task still owns an I/O lease.
- h5py handles are owned by the I/O layer, not arbitrary widgets.
- GUI updates occur only on the GUI thread.

### Editing

- Read-only is the default.
- Changes are recorded as typed patches against original coordinates.
- Saving verifies source fingerprint and target compatibility.
- File replacement is atomic where the platform and filesystem allow it.
- A failed save leaves the original file unchanged.
- gzip-wrapped files are read-only in v1.
- MAT, NIfTI, XLSX, JSON, and YAML are read-only in v1.

### Untrusted data

- Use `allow_pickle=False` for NPY/NPZ.
- Use safe YAML loading only.
- Do not execute Excel macros, external links, formulas, or embedded objects.
- Do not import or execute plugins discovered from arbitrary files in v1.
- Validate workspace manifests, plugin manifests, config, and format headers at boundaries.
- Error details may include technical context but must not expose unrelated file contents.

## 5. Public interface rules

- DataSource API version is `1`.
- Plugin API version is `1`.
- Workspace schema version is `1`.
- Add optional fields instead of changing or removing existing fields.
- Use discriminated result types and structured error codes.
- Public methods must document inputs, outputs, errors, cancellation, and ownership.
- GUI classes are not valid public data/plugin contracts.
- Plugins receive `PluginContext`; they do not access MainWindow or widget internals.

## 6. Format rules

The v1 format list is fixed in `docs/FORMAT_SUPPORT.md`.

- HDF5, NPY, NPZ, CSV, TSV, TXT: safe editing.
- MAT, NIfTI, XLSX, JSON, YAML: read-only plus export/Save As.
- Every listed format accepts an outer `.gz` wrapper.
- Text-like gzip formats may stream.
- Random-access binary gzip formats extract to a budgeted managed temporary file.
- Double-compressed `.npz.gz` and `.xlsx.gz` are readable but not recommended output formats.

Do not add NetCDF or Zarr to v1.

## 7. UI rules

- Use semantic theme tokens only.
- Use one bundled icon family; no emoji or Unicode pictograms as production icons.
- Preserve keyboard navigation and visible focus.
- Every async surface has loading, empty, error, cancelled, and success states.
- Dirty and read-only states require text/icon semantics, not color alone.
- Full plots render in the workspace, not inside the narrow Inspector.
- UI motion communicates feedback or state; no decorative perpetual motion.

## 8. Testing requirements

Follow `docs/TESTING.md`.

Minimum per task:

- targeted unit or contract test;
- regression test for every fixed bug;
- integration test when crossing module boundaries;
- offscreen GUI test for user-visible interaction;
- Windows and Linux CI for platform-sensitive behavior;
- no test may modify tracked repository configuration.

Never weaken an assertion, add `or True`, accept `elapsed >= 0`, or skip a failing test to make CI green.

## 9. Documentation requirements

Update documentation in the same change when any of these change:

- public API;
- supported format behavior;
- workspace schema;
- user-visible command or shortcut;
- dependency or license;
- architecture decision;
- task status.

Do not hand-write a success claim in `TEST_REPORT.md`. Test status must include the exact command, platform, commit, and result.

## 10. Completion checklist

Before marking a task complete:

- [ ] acceptance criteria are satisfied;
- [ ] targeted tests pass;
- [ ] full suite passes or unrelated failures are documented and approved;
- [ ] lint and type checks pass once Phase 0 enables them;
- [ ] no tracked config was modified by tests;
- [ ] docs and ADRs are current;
- [ ] `tasks/todo.md` is updated;
- [ ] `CHANGELOG.md` is updated for user-visible behavior;
- [ ] source tree contains no obsolete duplicate introduced by the task;
- [ ] Windows and Linux evidence exists when required.
