# Release History and Data Viewer v1 Gate

## Historical releases

The repository contains legacy HDF5 Viewer tags `v0.2.1`, `v0.3.0`, and `v0.3.1`. Their artifacts, names, claims, and internal version values are historical. Do not rewrite tags or present their feature lists as current Data Viewer behavior.

## Data Viewer v1 status

Data Viewer v1 is specified but not implemented. The active implementation sequence is `tasks/plan.md`; completion evidence belongs in `TEST_REPORT.md`.

## Release blockers

- every task marked as a v1 gate in `tasks/todo.md` is complete;
- target package, application, window, About, diagnostics, workspace, artifact, and desktop names are consistently Data Viewer;
- one canonical semantic version feeds every surface;
- PySide6/MIT distribution licensing is resolved by ADR-010 and documented;
- locked reproducible dependencies install on Windows and Linux;
- both CI matrices and packaged application smoke tests pass;
- format/gzip, safe editing, plugin, workspace, performance, UI/accessibility, localization, and diagnostics acceptance pass;
- release notes match implemented behavior and list known limitations;
- SBOM/license notices and SHA-256 checksums accompany artifacts;
- upgrade/config migration and rollback/recovery paths are tested.

## Artifact targets

- `DataViewer-<version>-windows-x86_64.zip` or an approved signed installer;
- `DataViewer-<version>-linux-x86_64.tar.gz` or an approved package/AppImage;
- SHA-256 checksums;
- SBOM and third-party license notices;
- release notes and `TEST_REPORT.md` evidence reference.

The supported Linux distribution baseline and Windows minimum version are finalized from clean packaging evidence, not assumed from build-runner success.

## CI package artifact layout

The quality workflow builds the current PyInstaller package from `packaging/DataViewer.spec` after the locked test, lint, type-check, compile, and wheel/sdist gates. The package upload names are:

- `data-viewer-package-windows-<run_id>-<run_attempt>`
- `data-viewer-package-ubuntu-<run_id>-<run_attempt>`

Each package upload contains the platform archive, `pyinstaller-manifest.json`, SHA-256 checksum files, `sbom.json`, `third-party-licenses.txt`, and `release-security-review.json`. The manifest records the Data Viewer version, platform tag, archive path, bundle directory, and packaged executable path used by the CI smoke steps using upload-safe relative paths, not build-runner absolute paths. The CI smoke first runs the packaged executable with `--version`, then runs the hidden installed-artifact functional workflow with `--ci-smoke`. That workflow opens representative HDF5, CSV, NIfTI, gzip-wrapped CSV, and workspace fixtures; runs the packaged Dataset Profile reference plugin; exports the plugin result; closes opened documents; and writes `installed-smoke-report.json` plus `installed-smoke-screenshot.png` into the quality evidence artifact.

Release evidence is generated only after the packaged functional smoke succeeds. The evidence generator records one checksum per platform archive, a dependency SBOM from the locked Python environment, third-party license notices, dependency-consistency status, and a path/credential leak scan across uploaded manifest/evidence attachments. The former PyQt6 distribution-license blocker is resolved by the PySide6/MIT decision in ADR-010; `release-security-review.json` still blocks publication for evidence leaks or unresolved dependency/security findings.

## Release sequence

1. Freeze scope and dependency locks.
2. Run the full PR gate on Windows and Linux.
3. Build artifacts in clean CI jobs.
4. Install/extract and run packaged smoke workflows on both platforms.
5. Run manual visual/accessibility and high-DPI matrix.
6. Review license/SBOM/security scan and known limitations.
7. Generate checksums and release notes from the canonical version.
8. Publish only when every required job is green; retain artifacts/logs.
9. Perform post-release download/launch/hash smoke and document rollback instructions.

The manual Windows/Linux acceptance procedure and sign-off template are defined in `docs/RELEASE_ACCEPTANCE.md`. DV-1101 and DV-1102 cannot be marked complete from CI evidence alone.

## Hotfix rule

A hotfix may narrow only unaffected expensive manual suites when the owner documents evidence, risk, and follow-up. It may never skip both-platform launch, changed-behavior tests, data-integrity tests, security/license checks, or artifact verification.
