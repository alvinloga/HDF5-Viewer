# Data Viewer Format Inventory

This inventory records the current first-release uncompressed format matrix.
It is evidence for DV-0412, not a replacement for the normative behavior rules
in `docs/FORMAT_SUPPORT.md`.

## Checkpoint 4 status

- Checkpoint: DV-0412 uncompressed format evidence.
- Commit: `98fb32babd8bdcfab8d1ee3a147244453dca42a2`.
- CI run: [29364690093](https://github.com/alvinloga/HDF5-Viewer/actions/runs/29364690093).
- Scope: uncompressed HDF5, NPY, NPZ, CSV, TSV, TXT, MAT, NIfTI, XLSX, JSON, YAML/YML.
- Excluded from v1: NetCDF and Zarr.
- Not included in this checkpoint: outer `.gz` composition; it starts at DV-0501.

## Format matrix

| Format | Extensions | Adapter status | v1 write boundary | Representative evidence |
|---|---|---|---|---|
| HDF5 | `.h5`, `.hdf5`, `.hdf`, `.h5py` | `data_viewer.sources.hdf5.HDF5Adapter` | safe edit | hierarchy, metadata, bounded reads, link handling, and HDF5 safe persistence tests |
| NumPy NPY | `.npy` | `data_viewer.sources.numpy.NPYAdapter` | safe edit | no-pickle loading, object-array rejection, scalar/empty/structured/order/byte-order, bounded reads, verified replacement writer |
| NumPy NPZ | `.npz` | `data_viewer.sources.npz.NPZAdapter` | safe edit | member hierarchy, unsafe-member rejection, ZIP budgets, bounded reads, archive-rebuild writer |
| CSV | `.csv` | `data_viewer.sources.delimited.DelimitedTextAdapter` | safe edit | strict UTF-8/BOM preview, dialect/schema provenance, paged table reads, verified full-file writer |
| TSV | `.tsv` | `data_viewer.sources.delimited.DelimitedTextAdapter` | safe edit | same delimited conformance as CSV with tab dialect coverage |
| TXT | `.txt` | `data_viewer.sources.text.TXTAdapter` | safe edit | strict text mode, bounded previews, text patch replacement, explicit table-mode reuse |
| MATLAB MAT | `.mat` | `data_viewer.sources.mat.MATAdapter` | read-only plus export/Save As | legacy SciPy and HDF5-backed v7.3 dispatch, variable tree, sparse/cell/struct/nested handling |
| NIfTI | `.nii`, `.nii.gz` | `data_viewer.sources.nifti.NIFTIAdapter` | read-only plus export/Save As | native NIfTI gzip, proxy slices, affine/axis/voxel/unit/intent/scaling metadata, voxel/world mapping |
| XLSX | `.xlsx` | `data_viewer.sources.xlsx.XLSXAdapter` | read-only plus export/Save As | external links disabled, formula text/cached distinction, sheets/cells/tables/names/merges, encrypted/malformed errors |
| JSON | `.json` | `data_viewer.sources.json.JSONAdapter` | read-only plus export/Save As | strict UTF-8/BOM parsing, JSON Pointer resources, duplicate-key warning, size/depth/string budgets |
| YAML | `.yaml`, `.yml` | `data_viewer.sources.yaml.YAMLAdapter` | read-only plus export/Save As | `yaml.safe_load`, unsafe tag rejection, aliases/merge metadata, nonstring key metadata, budgets |

## Evidence summary

Local Windows evidence on the repository `venv`:

- `venv\Scripts\python.exe -m pytest -q`: 364 passed, 1 skipped.
- `venv\Scripts\python.exe -m ruff check data_viewer main.py core\registry.py gui\sidebar\folder_explorer.py tests\test_format_scope.py tests\test_nifti_adapter.py tests\test_gui_shell.py`: passed.
- `venv\Scripts\python.exe -m mypy data_viewer`: passed.
- `venv\Scripts\python.exe -m compileall -q main.py core gui data_viewer tests`: passed.

GitHub Actions run 29364690093 at commit
`98fb32babd8bdcfab8d1ee3a147244453dca42a2`:

| Platform job | Python | Result | Test report | Build artifacts |
|---|---|---|---|---|
| Windows quality | CPython 3.12.10 | success | 365 total, 0 failures, 0 errors, 1 skipped | `data_viewer-1.0.0.dev0.tar.gz`, `data_viewer-1.0.0.dev0-py3-none-any.whl` |
| Ubuntu quality | CPython 3.12.13 | success | 365 total, 0 failures, 0 errors, 1 skipped | `data_viewer-1.0.0.dev0.tar.gz`, `data_viewer-1.0.0.dev0-py3-none-any.whl` |

Downloaded evidence artifacts were inspected locally under
`.tmp/ci-29364690093` and are not part of the tracked source tree.
