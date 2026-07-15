# Safe Editing and Persistence Specification

## 1. Scope

Data Viewer v1 safely edits HDF5, NPY, NPZ, CSV, TSV, and TXT. MAT, NIfTI, XLSX, JSON, YAML, and every generic gzip wrapper are read-only and support compatible Save As/export paths.

Editing is patch-based: a view never mutates the source merely because a cell widget changed. Save is a transaction with explicit validation, conflict detection, recovery behavior, and provenance.

## 2. Guarantees

For a successful save:

1. only the reviewed patch set changes;
2. dtype, shape, coordinates, source identity, and format semantics are preserved unless a confirmed structural operation says otherwise;
3. the destination is either the old valid file or the new verified file after interruption;
4. the application can explain what changed, where it was written, and whether it used replacement or in-place mutation;
5. a stale external source is never overwritten without a user decision.

For a failed or cancelled save, the original file remains usable and dirty state remains recoverable in memory.

## 3. Edit model

```python
@dataclass(frozen=True)
class CellPatch:
    resource_id: ResourceId
    coordinate: tuple[int, ...]
    old_value_fingerprint: str
    new_value: ScalarValue

@dataclass(frozen=True)
class TextPatch:
    resource_id: ResourceId
    start_offset: int
    end_offset: int
    old_text_fingerprint: str
    replacement: str

@dataclass(frozen=True)
class AttributePatch:
    resource_id: ResourceId
    name: str
    old_value_fingerprint: str | None
    new_value: ScalarValue | ArrayValue | None

@dataclass(frozen=True)
class ChangeSet:
    source_fingerprint: SourceFingerprint
    patches: tuple[CellPatch | TextPatch | AttributePatch, ...]
    created_at_utc: str
```

The implementation may add structural patch types only with tests and an ADR amendment. Patches are immutable, ordered, undoable, and scoped to one source revision.

## 4. Value validation

- Parse through the target dtype, not Python's most convenient type.
- Integer edits detect overflow and unsigned negatives.
- Floating edits explicitly support finite values, `NaN`, and infinities according to source dtype and UI policy.
- Complex values use an unambiguous parser and preview.
- Fixed-width strings reject or explicitly confirm truncation; implicit truncation is forbidden.
- Encodings use strict errors by default.
- Structured dtypes edit named fields without replacing unrelated fields.
- Dates/times preserve timezone/unit metadata when the format provides it.
- Missing values remain distinct from empty strings, zeros, and blank cells.

Validation happens before a patch enters the change set and again immediately before persistence.

## 5. Dirty, undo, and close behavior

Each document exposes `CLEAN`, `DIRTY`, `SAVING`, `SAVE_FAILED`, and `CONFLICTED` states.

- Undo/redo changes patches, not the source.
- Reverting all patches returns to `CLEAN` without a disk write.
- Closing a dirty document offers Save, Discard, or Cancel.
- Closing the application aggregates dirty documents in one review dialog.
- Background save disables conflicting edits but leaves navigation and cancellation available when safe.
- Autosave never overwrites scientific source files. Workspace recovery may serialize patch metadata into the application recovery area only after a future privacy review.

## 6. Conflict detection

The open-source fingerprint contains canonical path, size, modification time, format identity, and a bounded content fingerprint. Before commit:

1. stat and fingerprint the destination again;
2. if unchanged, proceed;
3. if changed, enter `CONFLICTED`;
4. offer Reload and discard local patches, Save As a new file, or Cancel;
5. v1 does not automatically merge external and local changes.

Network shares and coarse timestamp filesystems require a stronger content fingerprint before overwrite.

The DV-0905 implementation provides the non-GUI external-change decision surface in `data_viewer.app.session_restore`:

- `ExternalChangeDetector` classifies watcher/fingerprint refresh outcomes as unchanged, changed, replaced, deleted, or self-save.
- Dirty local patches never auto-overwrite changed source files. Dirty external changes default to Cancel and offer Reload and discard local patches, Save As, or Cancel.
- Deleted sources offer Save As, Close Reference, or Cancel.
- Replaced or changed clean sources offer Reload, Save As, or Cancel.
- Fingerprints recorded through `record_self_save(...)` suppress watcher echo false conflicts and update the clean baseline instead.

## 7. Transaction protocol

### 7.1 Atomic replacement strategy

NPY, NPZ, CSV, TSV, and TXT use complete-file replacement:

1. validate the change set and destination permissions;
2. reserve free disk for source-equivalent output plus safety margin;
3. create a uniquely named temporary file in the destination directory when possible;
4. write unchanged data plus patches without modifying the original;
5. flush Python/library buffers and `fsync` the temporary file;
6. reopen with the normal adapter and validate format, shape/schema, patch values, and representative unchanged values;
7. preserve documented permissions where supported;
8. replace destination using the platform's atomic replace primitive;
9. `fsync` the parent directory where supported;
10. reopen and record the new fingerprint; only then clear dirty state.

If same-directory temporary creation is impossible, Save is disabled and Save As is offered. A cross-filesystem copy is not described as atomic.

### 7.2 HDF5 strategy

Small value changes may be applied in place only when all are true:

- the dataset shape/dtype/layout is unchanged;
- each patch can be written as a direct selection;
- a backup/recovery strategy is active;
- the source fingerprint is unchanged;
- post-write verification can read every changed coordinate.

Attributes or structural changes that cannot satisfy those rules use a verified complete-file copy/replacement. The UI states the selected strategy before commit. If in-place verification fails, the document enters `SAVE_FAILED`, preserves the change log, and prominently warns that the source requires integrity inspection.

## 8. Save summary

Before writing, show:

- source and destination paths;
- format and write strategy;
- resources affected;
- number and kinds of patches;
- structural/schema changes, if any;
- expected output size and free-disk check;
- overwrite and backup behavior;
- warnings such as lossy conversion, dtype coercion, precision loss, or metadata omission.

Destructive structural changes require an additional explicit confirmation. Ordinary reviewed cell edits use one confirmation.

## 9. Save As and export

Save As preserves source semantics within the same format when that writer is supported. Export converts a selected scope and must show a conversion plan.

Export scopes are explicit values:

- entire resource;
- current normalized slice;
- current selection;
- filtered table rows;
- plugin result;
- rendered visualization.

An export receipt records source fingerprint, resource path, normalized selection, display-vs-raw value mode, parameters, target format/path, warnings, timestamp, application version, and success/failure.

Background exports use the same reviewed `ExportPlan` and terminal `ExportReceipt` values as direct exports. The application export queue adds task lifecycle state, progress, cancellation, retry, and receipt history without changing export semantics. A failed queued export is surfaced as a Problems entry linked to the task ID, target path, source URI, and resource path so the UI can route the user back to the affected source.

Diagnostics bundles may include export task records and recent export errors, but they are generated through the diagnostics redaction service and are previewed by the user before any file is written or shared.

## 10. Backups and recovery

- The default replacement protocol retains the original until the verified new file is ready.
- Optional persistent backups use a sibling `.bak` policy configured by the user; they are not silently created forever.
- Temporary filenames do not expose more source information than the destination already does.
- Startup recovery scans only Data Viewer transaction markers, never arbitrary temporary files.
- A recovery candidate is never auto-promoted. The user sees source, temporary output, verification status, timestamps, and safe actions.

## 11. Test requirements

Tests cover every editable format for:

- single and multiple patches;
- undo/redo and discard;
- dtype limits, strings, missing values, structured values, scalar/empty/high-dimensional data;
- unrelated-data preservation;
- external modification conflict;
- permission failure and insufficient disk;
- cancellation before commit;
- simulated exception at every transaction step;
- reopen verification;
- Windows locked-file behavior and Linux permission behavior;
- non-ASCII paths and long paths within platform support.

Property tests should generate small arrays/tables and prove that applying then reopening yields exactly the intended values and unchanged remainder.
