# Dependency and Environment Policy

## 1. Principles

- Python 3.12 is the initial baseline; Phase 0 records the exact supported range after wheel/package validation on Windows and Linux.
- Runtime and development dependencies are separated and locked reproducibly.
- Direct dependencies have a named purpose and owner; transient packages are not imported directly.
- Adding or upgrading a dependency requires license, security, platform-wheel, maintenance, size, startup, and packaging review.
- NetCDF and Zarr dependencies are excluded from v1.
- Scientific format libraries stay behind DataSource adapters; plugins and GUI do not receive their objects.

## 2. Proposed direct runtime dependencies

| Dependency | Purpose | Boundary/security rule |
|---|---|---|
| PyQt6 | native desktop UI | GUI layer only; distribution license review is mandatory |
| NumPy | canonical array payloads and NPY/NPZ | `allow_pickle=False` everywhere |
| h5py | HDF5 | session-owned handles; direct bounded selections |
| pandas | chunked delimited-text parsing | adapters only; DataSource API does not expose DataFrames |
| SciPy | legacy MAT and numerical plugin algorithms | MAT loads reject unsafe/object execution paths |
| NiBabel | NIfTI | preserve affine/header/orientation; proxy reads |
| openpyxl | XLSX inspection | read-only; no macro/formula/external-link execution |
| PyYAML | YAML | `safe_load`/restricted loader only |
| Matplotlib | initial plot renderer/export | figures owned/disposed by result renderer; theme tokens applied |
| jsonschema | plugin/workspace manifest validation | bounded JSON before validation |
| platformdirs | platform configuration/cache/log locations | no hand-built home-directory paths |
| PyInstaller | packaged Windows/Linux application | build dependency, pinned in packaging group |

Relevant upstream behavior must be checked against official documentation when implementing adapters: [h5py](https://docs.h5py.org/en/stable/index.html), [NumPy I/O](https://numpy.org/doc/stable/user/how-to-io.html), [SciPy MATLAB I/O](https://docs.scipy.org/doc/scipy/reference/io.html), [NiBabel](https://nipy.org/nibabel/gettingstarted.html), [openpyxl workbook loading](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html), [PyYAML safe loading](https://pyyaml.org/wiki/PyYAMLDocumentation), and [pandas I/O](https://pandas.pydata.org/docs/reference/io.html).

## 3. Development dependencies

| Dependency | Purpose |
|---|---|
| pytest | test runner |
| pytest-qt | Qt signals/events/widgets |
| pytest-cov/coverage | measured coverage evidence |
| hypothesis | property tests for selections/edit round trips |
| ruff | formatting/import/lint gate |
| mypy | public/core type checking |
| psutil | test/benchmark process-memory evidence only |
| build | standard project build metadata validation |

Avoid multiple tools for the same job unless a concrete gap is documented.

## 4. Packaging groups

Target `pyproject.toml` groups:

```toml
[project]
dependencies = [
  "PyQt6",
  "numpy",
  "h5py",
  "pandas",
  "scipy",
  "nibabel",
  "openpyxl",
  "PyYAML",
  "matplotlib",
  "jsonschema",
  "platformdirs",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt", "pytest-cov", "hypothesis", "ruff", "mypy", "build"]
packaging = ["pyinstaller"]
```

The exact version ranges and lock files are produced in Phase 0 after clean installations and import smoke tests. This document intentionally does not invent unverified pins.

## 5. Lock and upgrade process

1. Declare compatible direct ranges in `pyproject.toml`.
2. Generate reproducible Windows and Linux lock/constraint files with hashes using the selected lock tool.
3. Install in fresh Python environments on both platforms.
4. Run import, collection, unit, adapter, GUI, and package smoke suites.
5. Record dependency tree, licenses, artifact sizes, and known advisories.
6. Commit declaration and lock changes together.
7. For an upgrade, document behavioral/ABI changes and regenerate all locks; do not hand-edit transient pins.

CI installs from the lock/constraints, not unconstrained latest releases.

## 6. Licensing

The repository currently declares MIT, while PyQt6 is offered under GPL/commercial licensing. Before public binary distribution, the project owner must choose and document a compatible distribution model or licensed alternative. This is a release blocker, not merely a README footnote. See [Riverbank's PyQt licensing overview](https://riverbankcomputing.com/software/pyqt/intro).

Every new dependency adds SPDX license information to the release bill of materials. Unknown, incompatible, or non-redistributable licenses block inclusion.

## 7. Security baseline

- No NumPy/MAT path enables pickle or arbitrary Python object loading.
- YAML uses safe loading and anti-expansion budgets.
- JSON/YAML/archives/decompression have size, count, depth, and ratio limits.
- XLSX formulas/macros/external links are not executed.
- HDF5 external links are not followed by default.
- Dependencies are scanned in CI and reviewed; suppressions require owner, reason, scope, and expiry.
- Data Viewer has no network dependency at runtime in v1.

## 8. Platform validation

For every direct dependency verify:

- CPython 3.12 wheel availability for Windows x86-64 and Linux x86-64;
- import under clean virtual environments;
- Qt platform plugin availability in packaged artifacts;
- native library discovery without user-installed compilers;
- Unicode/long-path behavior;
- compatibility with NumPy ABI constraints;
- PyInstaller hook/hidden import behavior;
- license files included in distributions.

Linux's supported distribution baseline is finalized during packaging tests and documented in release notes.

## 9. Optional capabilities

If a plugin needs a heavy optional dependency, its manifest declares it and the registry reports availability. V1 release plugins required for acceptance must be included in the standard artifact; users must not install packages into a packaged application manually.

## 10. Prohibited dependency patterns

- unpinned VCS URLs or arbitrary downloaded executables;
- runtime `pip install`;
- importing optional libraries at application startup when not needed;
- dependence on NetCDF/Zarr for shared domain code;
- exposing library-specific mutable objects across public contracts;
- vendoring large third-party code without provenance/license;
- silent fallback to unsafe deserialization when a library raises.
