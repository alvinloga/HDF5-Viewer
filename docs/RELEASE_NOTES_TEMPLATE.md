# Data Viewer v1 GitHub Release Notes Template

Use this template only after DV-1101, DV-1102, and DV-1103 are complete. It is a release-publication aid for DV-1104, not release evidence by itself.

Replace every `TODO` before publishing. Do not publish a draft that still contains `pending-manual`, `pending-after-upload`, missing evidence links, or unchecked integrity/security blockers.

## Release title

Data Viewer vTODO

## Release status

- Version/tag: `vTODO`
- Commit: `TODO`
- GitHub Actions run: `TODO`
- Windows acceptance: `TODO link to signed DV-1101 evidence`
- Linux acceptance: `TODO link to signed DV-1102 evidence`
- Traceability/truth audit: `TODO link to DV-1103 evidence`

## Assets

Attach all assets from the same accepted commit.

| Asset | Required? | SHA-256 | Evidence |
|---|---:|---|---|
| `DataViewer-<version>-windows-x86_64.zip` | yes | TODO | TODO |
| `DataViewer-<version>-linux-x86_64.tar.gz` | yes | TODO | TODO |
| Windows checksum file | yes | TODO | TODO |
| Linux checksum file | yes | TODO | TODO |
| `sbom.json` for each platform artifact | yes | TODO | TODO |
| `third-party-licenses.txt` for each platform artifact | yes | TODO | TODO |
| `release-security-review.json` for each platform artifact | yes | TODO | TODO |

## What is included

- Scientific data workbench named Data Viewer.
- Windows x86-64 and supported Linux x86-64 packaged artifacts.
- v1 format support: HDF5, NPY, NPZ, CSV, TSV, TXT, MAT, NIfTI, XLSX, JSON, YAML/YML, and their documented `.gz` wrappers.
- Safe editing for HDF5, NPY, NPZ, CSV, TSV, and TXT under the v1 editing contract.
- Read-only plus export/Save As paths for MAT, NIfTI, XLSX, JSON, YAML, and gzip-wrapped inputs.
- Built-in statistics, visualization, comparison, export, diagnostics, and workspace flows covered by the release evidence.

## Known limitations

- TODO: list every accepted limitation from DV-1103.
- JSON/YAML/XLSX/MAT/NIfTI source editing is not in v1.
- Third-party plugin installation, signing, sandboxing, and marketplace distribution are not in v1.
- NetCDF, Zarr, DICOM, Parquet/Arrow, FITS, SQLite, EEG/MEG, and macOS packaging are post-v1 scope.

## Installation

### Windows

1. Download `DataViewer-<version>-windows-x86_64.zip`.
2. Verify SHA-256 against the attached checksum.
3. Extract to a user-writable directory.
4. Run `DataViewer.exe`.

### Linux

1. Download `DataViewer-<version>-linux-x86_64.tar.gz`.
2. Verify SHA-256 against the attached checksum.
3. Extract to a user-writable directory.
4. Run `DataViewer/DataViewer` on the supported distribution/display stack recorded in the release evidence.

## Security and licensing

- Data Viewer source code is distributed under MIT.
- PySide6 / Qt for Python distribution obligations are covered by the attached third-party license notices and SBOM.
- `release-security-review.json` for each platform must report ready status, passed leak scan, and no unresolved blocking findings.
- Data Viewer is offline by default and does not upload diagnostics automatically.

## Evidence links

| Evidence | Link |
|---|---|
| TEST_REPORT section for this release | TODO |
| DV-1101 Windows signed checklist | TODO |
| DV-1102 Linux signed checklist | TODO |
| DV-1103 traceability/truth audit | TODO |
| GitHub Actions quality/package run | TODO |
| Post-release download/hash/launch smoke | TODO after publication |

## Rollback instructions

If release publication must be rolled back:

1. Mark the GitHub Release as draft or delete the release assets if an integrity/security issue is confirmed.
2. Leave the immutable git tag intact unless the tag itself points to the wrong commit and the project owner explicitly approves correcting it.
3. Publish a follow-up issue documenting the reason, affected assets, impact, and next action.
4. Keep the previous accepted release available unless it contains the same integrity/security issue.

## Post-release smoke

After publishing:

1. Download the Windows and Linux assets from the public GitHub Release, not from CI artifacts.
2. Verify each SHA-256 checksum.
3. Run `Data Viewer --version` from each extracted package.
4. Open and close a representative fixture/workspace on each platform.
5. Record command output, hashes, release URL, and any issue links in `TEST_REPORT.md`.
