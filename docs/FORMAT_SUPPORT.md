# Format Support Contract

## 1. Purpose

This document is the normative v1 format matrix for Data Viewer. An adapter is not complete until its behavior, limits, security controls, gzip behavior, and conformance tests match this contract.

## 2. Global rules

1. Extension matching is case-insensitive and only proposes an adapter; `probe()` must validate content.
2. Compound extensions are parsed longest-first: `.nii.gz` before `.gz`, then the inner suffix.
3. Probing reads at most 1 MiB unless the format requires a documented bounded exception.
4. Opening a source must not recursively enumerate all resources or load an entire large payload.
5. Unsupported features fail with a structured `SourceError`; they never silently coerce data.
6. Values shown in a view retain their original coordinates, dtype, missing-value semantics, and provenance.
7. Object deserialization, macros, formulas-as-code, YAML constructors, and external links are never executed.
8. Every adapter supplies tiny, malformed, edge-case, representative, and gzip-wrapped fixtures.

## 3. v1 matrix

| Family | Extensions | Domain | v1 access | Primary library | Required semantics |
|---|---|---|---|---|---|
| HDF5 | `.h5`, `.hdf5`, `.hdf`, `.h5py` | hierarchical array | safe edit | h5py | groups, datasets, attributes, links, chunks, compression |
| NumPy array | `.npy` | array | safe edit | NumPy | dtype/shape/order preserved; object arrays rejected by default |
| NumPy archive | `.npz` | hierarchical array | safe edit by archive rebuild | NumPy/zipfile | member names, arrays, compression mode, archive integrity |
| Delimited table | `.csv`, `.tsv` | table | safe edit | pandas/Python csv | explicit encoding, delimiter, quote, header and type decisions |
| Text | `.txt` | text or table | safe edit | Python codecs/csv | preview first; user confirms parse mode before table interpretation |
| MATLAB | `.mat` | hierarchical array | read-only; export/Save As | SciPy and h5py | v4/v5/v7.2 via SciPy; v7.3 via HDF5; variables remain distinct |
| NIfTI | `.nii`, `.nii.gz` | volume | read-only; export/Save As | NiBabel | header, affine, orientation, scaling, voxel/world coordinates |
| Excel | `.xlsx` | workbook | read-only; export/Save As | openpyxl | workbook/sheets/cells; no macros, external links, or formula execution |
| JSON | `.json` | structured | read-only; export/Save As | stdlib json | duplicate-key warning policy; depth/size budgets; scalar root allowed |
| YAML | `.yaml`, `.yml` | structured | read-only; export/Save As | PyYAML | `safe_load` only; aliases/depth/size budgets; scalar root allowed |
| Outer gzip | any extension above plus `.gz` | wrapper | read-only wrapper | stdlib gzip | bounded decompression; streaming or managed extraction by inner adapter |

NetCDF and Zarr are explicitly unregistered in v1. Their dependencies, menu entries, tests, and README claims must be removed during migration.

## 4. Adapter requirements

### 4.1 HDF5

- Validate the HDF5 signature and open with the least permissive mode needed.
- List only direct children; cycles through links must not recurse indefinitely.
- Mark soft/external links and broken links explicitly. Do not follow external links without an explicit future policy.
- Expose dataset shape, dtype, chunks, compression, fill value, storage size, and attributes.
- Preserve compound, variable-length, string, boolean, complex, scalar, and zero-length datasets.
- Read selections directly from the dataset. Never read the full dataset merely to slice afterward.
- Attribute and dataset edits use patches. Structural replacement uses a temporary sibling and verified swap when in-place mutation is unsafe.
- Opening a gzip-wrapped HDF5 file first extracts to managed temporary storage because random access is required.

### 4.2 NPY

- Load with `allow_pickle=False` in every path, including probe and preview.
- Memory-map uncompressed, compatible arrays where possible.
- Reject object arrays with a clear security error; do not add an unsafe override in v1.
- Preserve dtype byte order, structured fields, Fortran/C order, shape, and scalar/zero-length cases.
- Save by writing a complete temporary `.npy`, reopening it with `allow_pickle=False`, verifying header/shape/dtype, then replacing the destination atomically.

### 4.3 NPZ

- Treat the archive as a synthetic hierarchy with one array resource per member.
- Reject encrypted entries, path traversal names, duplicate normalized names, extreme compression ratios, and entries exceeding configured budgets.
- Load every array with `allow_pickle=False`.
- Editing always rebuilds the archive into a temporary file; never patch ZIP members in place.
- Preserve unaffected members byte-for-byte only when safe and practical; otherwise preserve their decoded array semantics and report that the archive was rebuilt.

### 4.4 CSV and TSV

- Opening begins with a bounded import preview and an explicit `DelimitedTextOptions` value.
- Options include encoding, delimiter, quote character, escape behavior, header row, skipped rows, comment prefix, decimal separator, thousands separator, missing tokens, and per-column dtype overrides.
- Defaults: UTF-8 with BOM detection; comma for CSV; tab for TSV. Failed decoding opens an options dialog, not silent replacement characters.
- Type inference is preview-only until the user confirms it. The confirmed schema becomes source provenance and workspace state.
- Paginated/chunked reads are required. Row identity is the original zero-based data-row offset plus header offset.
- Safe save rewrites the complete table to a temporary file using the confirmed dialect and encoding, then validates row/column counts before replacement.

### 4.5 TXT

- Initially open as bounded plain text with encoding detection limited to BOM plus strict UTF-8; alternative encodings require user selection.
- Offer table parsing only after a preview demonstrates a stable delimiter/column count or the user configures it.
- Preserve line-ending choice and final-newline state when editing as text.
- Never infer whitespace-delimited scientific notation in a way that discards the original textual representation without confirmation.

### 4.6 MAT

- Detect HDF5-backed v7.3 separately from earlier MAT versions.
- Map MATLAB variables to stable resource nodes. Internal metadata keys remain hidden by default but inspectable.
- Cells, structs, char arrays, sparse matrices, complex values, logical arrays, and nested values must have explicit representations or a structured unsupported-value state.
- v7.3 reference graphs require cycle detection and bounded traversal.
- v1 does not overwrite MAT. Export may target NPY/NPZ, CSV/TSV, HDF5, JSON, or another compatible format after a scope/semantics preview.

### 4.7 NIfTI

- `.nii.gz` is a native NIfTI form, not a generic gzip suffix in UI labeling.
- Preserve and display header fields, raw shape/dtype, slope/intercept scaling, affine, axis codes, voxel sizes, units, and dimensional intent when present.
- Views provide axial, coronal, and sagittal planes with linked crosshairs, voxel coordinates, world coordinates, window/level, and time/volume selection for 4D data.
- Do not silently canonicalize or resample the source. Any derived orientation is labeled and retains a transform back to source indices.
- Use proxy/memory-mapped access when supported; do not call full-volume materialization for an ordinary slice.
- v1 is read-only. Exported arrays must state whether values are raw stored voxels or scaled values and must include affine/header sidecar options.

### 4.8 XLSX

- Open in read-only/data-only mode appropriate to safe inspection; formulas are displayed as formulas and/or cached values, never executed.
- Disable retention/following of external links. Reject encrypted workbooks with a specific error.
- Expose workbook, worksheet, dimensions, merged cells, tables, defined names, and cell types without building every cell widget.
- Preserve cell coordinates and distinguish blank cells from missing rows.
- Macros are outside scope because `.xlsm` is not a supported extension.
- v1 does not overwrite XLSX. Table ranges may be exported to CSV/TSV/NPY/JSON.

### 4.9 JSON

- Parse UTF-8/UTF-8-BOM only unless a future ADR expands encoding support.
- Enforce configurable file-size, nesting-depth, collection-length, and string-length budgets.
- Detect duplicate object keys and surface a warning with the chosen last-value interpretation; preserve no false claim that duplicates were losslessly represented.
- Stable resource paths use JSON Pointer escaping.
- Large documents that exceed the v1 parser budget fail with remediation guidance rather than exhausting memory.

### 4.10 YAML/YML

- Use `yaml.safe_load` or an equivalently restricted loader only.
- Reject application-specific tags and Python object constructors.
- Enforce byte, depth, alias expansion, collection, and scalar-length budgets before producing a UI tree.
- Map keys that are not strings to a display-safe representation while retaining type metadata.
- Report YAML merge-key and alias semantics in metadata so the displayed resolved structure is not mistaken for the original spelling.

## 5. Gzip wrapper

### 5.1 Detection

`foo.ext.gz` first validates gzip framing and then probes the decompressed prefix as `foo.ext`. A filename-only match is insufficient. `.nii.gz` is routed directly to the NIfTI adapter, which may use NiBabel's indexed behavior.

### 5.2 Resource strategy

- Stream-capable inner formats (`csv`, `tsv`, `txt`, `json`, `yaml`) receive a bounded decompression stream.
- Random-access inner formats (`h5`, `hdf5`, `hdf`, `h5py`, `npy`, `npz`, `mat`, `xlsx`) extract to a managed cache file.
- The task checks compressed size, declared/uncompressed progress, compression ratio, free disk, configured extraction budget, and cancellation.
- Temporary data is stored under the application cache directory, never beside the source unless explicitly exporting.
- Cache keys include canonical path, size, mtime, and a content prefix hash. Stale entries are invalidated.
- Cancellation, crash recovery, and normal close remove incomplete extraction files. A startup janitor removes expired complete entries.

### 5.3 Output policy

Generic gzip sources are read-only in v1. Users may Save As to an uncompressed editable target or export to another format. `.npz.gz` and `.xlsx.gz` can be opened but are labeled inefficient nested compression and are not proposed as output formats.

## 6. Budgets and configuration

Defaults are conservative and configurable after Phase 0 measurements:

| Budget | Required default behavior |
|---|---|
| Probe bytes | at most 1 MiB |
| Initial table preview | at most 10,000 rows and 16 MiB decoded |
| View payload | bounded by task memory budget; never whole-file by implication |
| JSON/YAML nesting | reject beyond configured depth |
| Archive entries | reject beyond configured count |
| Decompression | preflight free disk and abort before configured maximum |

Exact numeric production defaults belong in versioned configuration and benchmark evidence, not duplicated constants across adapters.

## 7. Conformance checklist

Every adapter must prove:

- positive and negative probe behavior;
- stable resource identity and paginated direct-child listing;
- metadata without uncontrolled payload loading;
- correct scalar, empty, 1D, 2D, high-dimensional, unusual dtype, and malformed behavior;
- cancellation and close during an active read;
- structured, actionable errors without traceback leakage in the main UI;
- gzip behavior for every registered extension;
- Windows and Linux path/unicode fixtures;
- no unsafe deserialization or embedded code execution;
- documented Save, Save As, and export capabilities.
