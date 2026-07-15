# Data Viewer

[中文](README.md) | [English](README_EN.md)

Data Viewer is a cross-platform desktop scientific data workbench for researchers, data engineers, and algorithm developers. Its target workflow covers viewing, analysis, comparison, safe editing, export, and reproducible workspaces.

## Project status

This repository is preparing for an architectural migration.

- `core/`, `gui/`, `plugins/`, and `services/` are the legacy HDF5 Viewer implementation; the root legacy `main.py` entrypoint and empty compatibility `utils/` package were removed in DV-1008.
- The legacy application is migration input. It does not implement the complete Data Viewer specification.
- The target contract lives in `docs/`, `ARCHITECTURE.md`, and `tasks/`.
- Future changes must migrate behavior incrementally and preserve a testable application after every task.

Known baseline limitations:

- the GUI suite does not currently collect in the active development environment;
- the historical claim that 121 tests pass is not accepted as current evidence;
- editing, export, split focus, async loading, and optional-source handling contain confirmed defects;
- the old `HDF5 Viewer` name is retained only in historical or migration-reference contexts; current target package, entrypoint, and UI surfaces use `Data Viewer`.

## Product definition

```text
Open -> Browse -> Slice -> View -> Analyze/Visualize
     -> Compare -> Safely Edit -> Export -> Save Workspace
```

Principles:

- read-only by default;
- full processing for small data, chunking for medium data, explicit sampling for very large data;
- reproducible analysis provenance for every result;
- no implicit spatial resampling, unsafe deserialization, or untrusted plugin execution;
- both Windows and Linux must pass release acceptance.

## First-release formats

| Format | Domain | Read | Edit | Contract |
|---|---|---:|---:|---|
| HDF5 | Hierarchical arrays | Yes | Yes | Slice patch writes |
| NPY | Array | Yes | Yes | Atomic replacement or Save As |
| NPZ | Multi-array archive | Yes | Yes | Full archive rebuild; pickle disabled |
| CSV | Table | Yes | Yes | Import settings confirmed before load |
| TSV | Table | Yes | Yes | Shared delimited adapter |
| TXT | Text/Table | Yes | Yes | Falls back to text when table inference is unreliable |
| MAT | Hierarchical arrays | Yes | No | Traditional and HDF5-based MAT; export only |
| NIfTI | Medical volume | Yes | No | Affine, orientation, header, and world coordinates preserved |
| XLSX | Workbook | Yes | No | No macro or external-link execution |
| JSON | Structured data | Yes | No | Tree and record-set views |
| YAML/YML | Structured data | Yes | No | Safe loading only |
| `.gz` wrapper for every format | Compression wrapper | Yes | No | Save As; binary formats use managed temporary extraction |

NetCDF and Zarr are explicitly outside the first-release scope. See [Format Support](docs/FORMAT_SUPPORT.md) for the complete matrix.

## Target capabilities

- lazy hierarchy browsing and virtualized tables;
- specialized scalar, array, table, structured, and volume views;
- advanced search, favorites, recent files, navigation history;
- statistics, distribution, correlation, comparison, and visual plugins;
- NIfTI orthogonal views with linked cursor and voxel/world coordinates;
- versioned workspaces that preserve tabs, splits, slices, comparisons, and plugin parameters;
- patch-based editing with undo, conflict detection, atomic save, and Save As;
- a stable, versioned plugin API for incremental development.

## Documentation map

| Document | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Mandatory rules for future agents |
| [Product Spec](docs/PRODUCT_SPEC.md) | Requirements, boundaries, success criteria |
| [Architecture](ARCHITECTURE.md) | Target modules, flows, and state machines |
| [Format Support](docs/FORMAT_SUPPORT.md) | Format and gzip behavior |
| [DataSource API](docs/DATASOURCE_API.md) | Adapter contract |
| [Plugin API](docs/PLUGIN_API.md) | Plugin API v1 |
| [Workspace Format](docs/WORKSPACE_FORMAT.md) | `.dvw` manifest schema |
| [Safe Editing](docs/SAFE_EDITING.md) | Patch and save protocol |
| [UI/UX Spec](docs/UI_UX_SPEC.md) | Information architecture, design system, states, accessibility |
| [Testing](docs/TESTING.md) | Test levels, CI, performance budgets |
| [Dependencies](docs/DEPENDENCIES.md) | Runtime, development, and license policy |
| [Configuration](docs/CONFIGURATION.md) | Platform config, schema, and legacy config migration |
| [Migration](docs/MIGRATION.md) | Incremental legacy migration and removal criteria |
| [ADRs](docs/decisions/README.md) | Accepted architecture decisions |
| [Documentation Index](docs/INDEX.md) | Authority order and task-specific reading map |
| [Plan](tasks/plan.md) | Dependency graph and checkpoints |
| [Todo](tasks/todo.md) | Executable tasks and verification |

## Legacy application quick start

These commands are for auditing the current implementation only.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m data_viewer
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
QT_QPA_PLATFORM=xcb python -m data_viewer
```

The target commands are maintained in `docs/PRODUCT_SPEC.md`.

## Current verification baseline

The initial read-only audit has been superseded by the current locked Windows/Linux baseline:

- `uv sync --locked --all-extras` passes in an independent CPython 3.12 environment and in Windows/Ubuntu CI;
- all v1 direct dependencies, including PyQt6, import successfully on both platforms;
- full collection reports 189 tests and execution reports 188 passed, 1 skipped;
- CI now verifies locked installation, lint/type, compilation, collection, offscreen GUI regression, JUnit/manifest evidence upload, and sdist/wheel builds;
- the release gate has been verified to stop when quality tests fail;
- release remains gated on unimplemented v1 functionality, artifact smoke, SBOM, and licensing decisions;
- static counts and the historical “121 tests / 100%” claim are still not current evidence.

See [TEST_REPORT.md](TEST_REPORT.md). Future agents must replace this baseline only with reproducible CI evidence.

## Contributing

Read [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md). Implement one task from `tasks/todo.md` at a time, write the regression test first, keep each change reviewable, and verify both platforms where behavior differs.

## License

Repository source is currently MIT licensed. PyQt6 is distributed under GPLv3 or a commercial license. A dependency-license review is required before distributing Data Viewer binaries.
