# Data Viewer v1 Release Acceptance Runbook

This document is the auditable manual acceptance runbook for DV-1101, DV-1102, DV-1103, and DV-1104.

It does not itself prove release readiness. A platform is accepted only when a completed copy of the relevant checklist records the tested artifact, artifact checksum, operating system/display stack, screenshots, logs, issue links, reviewer signature, and no unresolved integrity or security blocker.

## 1. Scope and release boundary

Release acceptance covers the packaged Data Viewer v1 artifacts produced from the same commit for:

- Windows x86-64;
- supported Linux x86-64.

The platform checklists must use package artifacts that already passed CI package smoke, installed-artifact functional smoke, release-evidence generation, SBOM/license generation, checksum generation, and path/credential leak scanning.

Do not use source-tree execution as a substitute for packaged manual acceptance. Source-tree checks may support diagnosis, but DV-1101 and DV-1102 require packaged artifacts.

## 2. Required evidence packet

Each platform evidence packet must contain:

| Evidence | Required content |
|---|---|
| Environment record | OS version/build, CPU architecture, display server or DPI/scaling mode, GPU/display notes where relevant, reviewer name, date/time, timezone |
| Artifact identity | Git commit, workflow run, job ID, artifact name, artifact ID, artifact digest, archive SHA-256, executable version output |
| Test data identity | Fixture/source names, generated fixture parameters or checked-in fixture provenance, workspace manifest used |
| Manual checklist | Completed platform checklist with every item marked `pass`, `fail`, `blocked`, or `not applicable with reason` |
| Visual evidence | Screenshots for the UI matrix states and scaling/theme combinations defined below |
| Runtime logs | Packaged application logs, installed-smoke report when reused, diagnostics bundle if any error path is exercised |
| Issue links | Link or local reference for every failure, blocker, accepted limitation, or documented platform difference |
| Sign-off | Reviewer signature and statement that no unresolved integrity/security blocker remains |

Recommended evidence directory names:

```text
release-evidence/
  v1/
    windows/
      DV-1101-checklist.md
      screenshots/
      logs/
      artifacts/
    linux/
      DV-1102-checklist.md
      screenshots/
      logs/
      artifacts/
```

Do not commit large binary screenshots or release archives unless the release manager explicitly chooses a repository-hosted evidence strategy. `TEST_REPORT.md` may point to GitHub Actions artifacts, release assets, or external evidence storage.

## 3. Preflight for both platforms

Before running a platform checklist:

1. Confirm `tasks/todo.md` marks DV-1009 complete.
2. Confirm the candidate commit has green Windows and Ubuntu quality/package jobs.
3. Download the package artifact for the target platform.
4. Verify the GitHub artifact digest and the archive SHA-256 checksum file inside the artifact.
5. Extract/install into a clean temporary directory with no development checkout on `PYTHONPATH`.
6. Run the packaged executable with `--version` and record the exact output.
7. Confirm the artifact contains:
   - the packaged application archive;
   - `pyinstaller-manifest.json`;
   - SHA-256 checksum files;
   - `sbom.json`;
   - `third-party-licenses.txt`;
   - `release-security-review.json`.
8. Review `release-security-review.json`; any leak/security/dependency failure blocks acceptance.

The helper below can prepare the machine-checkable part of the evidence packet from a downloaded package artifact. It does not complete manual acceptance and leaves functional/visual rows as `pending-manual`.

```bash
python tools/prepare_release_acceptance_packet.py \
  --platform Windows \
  --artifact-dir .artifacts/release-acceptance/<run-id>/windows/package \
  --output-dir .artifacts/release-acceptance/<run-id>/windows/evidence \
  --candidate-commit <commit> \
  --run-id <run-id> \
  --job-id <job-id> \
  --artifact-name <artifact-name> \
  --artifact-id <artifact-id> \
  --artifact-digest sha256:<github-artifact-digest> \
  --version-output "Data Viewer <version>"
```

The generated `DV-1101-checklist.md` or `DV-1102-checklist.md` is a starting point for the human reviewer, not a signature.

The CI quality workflow also runs this helper before uploading package artifacts. CI-generated packets live under `artifacts/<platform>/package/acceptance/` inside the package upload and are also uploaded as a small `data-viewer-acceptance-<platform>-<run>-<attempt>` artifact so reviewers can retrieve the checklist and summary without first downloading the full packaged application archive. Those packets are intentionally pre-upload packets: GitHub artifact ID and artifact digest fields are `pending-after-upload` until the release reviewer fills them from the uploaded package artifact metadata.

## 4. Functional acceptance matrix

Run this matrix on Windows for DV-1101 and on Linux for DV-1102. Use representative small fixtures for normal flows and generated stress fixtures where the item calls for large/responsive behavior.

| ID | Area | Required checks | Status | Evidence |
|---|---|---|---|---|
| FMT-HDF5 | HDF5 and `.h5/.hdf5/.hdf/.h5py.gz` | open, browse hierarchy lazily, inspect metadata, read scalar/1D/2D/high-dimensional slices, safe edit supported uncompressed data, review/save/reopen unchanged coordinates, gzip wrapper read-only plus Save As/export alternative |  |  |
| FMT-NPY | NPY and `.npy.gz` | open with `allow_pickle=False`, inspect dtype/shape/order, edit supported uncompressed array, save/reopen verification, object array rejection, gzip wrapper read-only |  |  |
| FMT-NPZ | NPZ and `.npz.gz` | browse member hierarchy, reject unsafe archive members, edit supported uncompressed member by archive rebuild, save/reopen verification, nested gzip warning/read-only behavior |  |  |
| FMT-CSV | CSV and `.csv.gz` | preview import options, paged table view, edit/save/reopen uncompressed table, formula-injection-safe export, gzip wrapper read-only/export alternative |  |  |
| FMT-TSV | TSV and `.tsv.gz` | same delimited behavior as CSV with tab dialect, edit/save/reopen uncompressed table, gzip wrapper read-only/export alternative |  |  |
| FMT-TXT | TXT and `.txt.gz` | text preview, line endings/final newline visibility, text edit/save/reopen uncompressed file, explicit table parse path, gzip wrapper read-only/export alternative |  |  |
| FMT-MAT | MAT and `.mat.gz` | read-only variable tree, legacy and HDF5-backed MAT where fixtures exist, struct/cell/sparse/complex representation or unsupported-value state, export/Save As alternative, overwrite blocked |  |  |
| FMT-NIFTI | NIfTI `.nii/.nii.gz` and generic `.nii.gz` routing | read-only volume open, header/affine/orientation display, axial/coronal/sagittal plane navigation, voxel/world coordinates, 4D index where applicable, export/Save As alternative, no implicit resampling |  |  |
| FMT-XLSX | XLSX and `.xlsx.gz` | read-only workbook/sheet/cell/table/defined-name inspection, formulas not executed, external links/macros not followed, export alternative, overwrite blocked |  |  |
| FMT-JSON | JSON and `.json.gz` | strict UTF-8/BOM parse, structured tree, scalar root, duplicate-key warning, budget/depth error path, export alternative, overwrite blocked |  |  |
| FMT-YAML | YAML/YML and `.yaml.gz/.yml.gz` | safe loader only, structured tree, alias/merge metadata, unsafe tag rejection, budget/depth error path, export alternative, overwrite blocked |  |  |
| EDIT | Safe editing | read-only default, explicit edit entry, dirty marker, undo/redo/discard, review summary, fingerprint conflict block, failed-save recovery, Save As path |  |  |
| EXPORT | Export | full resource, current slice/page, selection, plugin result, visualization export where available, overwrite confirmation, cancellation, receipt/provenance |  |  |
| PLUGIN | Built-in plugins | Dataset Profile, descriptive statistics, distribution summary, correlation/covariance, dataset comparison, line/scatter/histogram/box plot, correlation heatmap, missing-data map, NIfTI viewer; provenance and sampled/full scope visible |  |  |
| COMPARE | Compare | metadata compatibility check, array shape mismatch refusal, table column alignment, NIfTI shape/voxel/orientation/affine checks, linked navigation toggle, explicit difference metrics |  |  |
| WORKSPACE | Workspace | save `.dvw`, restore files/views/slices/favorites/comparisons/plugin parameters, moved/missing/changed source degraded modes, newer-version protection |  |  |
| TASKS | Errors/cancel/recovery | long operation progress, cooperative cancellation, Problems entry, retry/details, diagnostics bundle preview/export, temp gzip cleanup/recovery |  |  |
| SECURITY | Untrusted data boundaries | NumPy pickle/object rejection, YAML unsafe tag rejection, XLSX macro/external-link safety, plugin forbidden import surface, no arbitrary external plugin loading |  |  |
| PACKAGE | Packaged smoke | launch from extracted package, `--version`, open representative HDF5/CSV/NIfTI/gzip/workspace fixtures, run Dataset Profile, export result, close cleanly |  |  |

## 5. Visual, accessibility, localization, and DPI matrix

Every platform must capture and review the applicable visual matrix from `docs/UI_UX_SPEC.md`.

Visual evidence must come from the packaged application running on the platform's native interactive display stack. Offscreen/headless screenshots may support CI smoke diagnostics, but they do not satisfy the manual visual, accessibility, localization, or DPI evidence requirement for DV-1101 or DV-1102. If an offscreen screenshot differs from native rendering, record the native screenshot as authoritative and link the offscreen artifact only as diagnostic context.

For each visual evidence packet, record the display stack and rendering context:

- Windows: Qt platform plugin, monitor scaling, display adapter or remote-session note, and the default UI font observed by the packaged application.
- Linux: distribution/version, desktop environment or window manager, display server (`x11`/`xcb` or Wayland), scaling setting, and the default UI font observed by the packaged application.

### Windows DV-1101 visual matrix

| Scaling | Window size | Themes | Required states |
|---|---|---|---|
| 100% | 1024x768 minimum, 1440x900 typical, 2560x1440 large | light, dark | empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, degraded workspace |
| 150% | 1024x768 minimum, 1440x900 typical, 2560x1440 large | light, dark | empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, degraded workspace |
| 200% | 1024x768 minimum, 1440x900 typical, 2560x1440 large | light, dark | empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, degraded workspace |

### Linux DV-1102 visual matrix

| Scaling | Window size | Themes | Required states |
|---|---|---|---|
| 100% | 1024x768 minimum, 1440x900 typical, 2560x1440 large | light, dark | empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, degraded workspace |
| 200% | 1024x768 minimum, 1440x900 typical, 2560x1440 large | light, dark | empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, degraded workspace |

For each captured state, review:

- no clipped primary actions;
- no overlapping or unreadable text;
- visible focus indicator;
- keyboard path to primary actions;
- no focus trap;
- state is not communicated by color alone;
- contrast is acceptable for text and essential indicators;
- no emoji or unrelated Unicode pictogram icons;
- no hard-coded theme color visible in the wrong theme;
- popup/dialog placement remains attached to the triggering context;
- English and Simplified Chinese strings are complete enough for the flow.

## 6. Platform checklist template

Copy this template into the platform evidence packet as `DV-1101-checklist.md` or `DV-1102-checklist.md`.

```markdown
# Data Viewer v1 Platform Acceptance Checklist

- Task: DV-1101 Windows manual acceptance matrix / DV-1102 Linux manual acceptance matrix
- Platform:
- OS version/build:
- Display server / scaling mechanism:
- CPU architecture:
- Reviewer:
- Date/time/timezone:
- Candidate commit:
- GitHub Actions run:
- Job ID:
- Package artifact name:
- Package artifact ID:
- GitHub artifact digest:
- Archive SHA-256:
- `Data Viewer --version` output:
- Evidence directory or URL:

## Preflight

- [ ] DV-1009 complete in `tasks/todo.md`
- [ ] Candidate commit has green Windows/Linux quality jobs
- [ ] Package artifact downloaded from the recorded run
- [ ] Artifact digest verified
- [ ] Archive SHA-256 verified
- [ ] SBOM present and reviewed
- [ ] Third-party licenses present and reviewed
- [ ] `release-security-review.json` reports no blocking findings
- [ ] Packaged executable launches outside the source checkout

## Functional matrix

Record `pass`, `fail`, `blocked`, or `not applicable with reason` for every row in section 4.

| ID | Status | Evidence path or URL | Notes / issue |
|---|---|---|---|
| FMT-HDF5 |  |  |  |
| FMT-NPY |  |  |  |
| FMT-NPZ |  |  |  |
| FMT-CSV |  |  |  |
| FMT-TSV |  |  |  |
| FMT-TXT |  |  |  |
| FMT-MAT |  |  |  |
| FMT-NIFTI |  |  |  |
| FMT-XLSX |  |  |  |
| FMT-JSON |  |  |  |
| FMT-YAML |  |  |  |
| EDIT |  |  |  |
| EXPORT |  |  |  |
| PLUGIN |  |  |  |
| COMPARE |  |  |  |
| WORKSPACE |  |  |  |
| TASKS |  |  |  |
| SECURITY |  |  |  |
| PACKAGE |  |  |  |

## Visual/accessibility/localization matrix

Record one row per screenshot set. Each row must link the screenshot directory and any failure issue.

| Scaling | Window size | Theme | State | Status | Screenshot path or URL | Notes / issue |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## Platform differences

List every intentional platform difference. Each difference requires owner acceptance and must not affect scientific semantics, data integrity, or security.

| Difference | Reason | Accepted by | Issue / evidence |
|---|---|---|---|
|  |  |  |  |

## Blockers and limitations

| Item | Severity | Integrity/security impact? | Owner | Issue | Release decision |
|---|---|---:|---|---|---|
|  |  |  |  |  |  |

## Sign-off

I confirm this checklist was executed against the recorded packaged artifact and that no unresolved integrity or security blocker remains.

- Reviewer:
- Signature:
- Date:
```

## 7. Completion rules

- DV-1101 may be checked only after the Windows checklist is complete, signed, linked from `TEST_REPORT.md`, and no unresolved integrity/security blocker remains.
- DV-1102 may be checked only after the Linux checklist is complete, signed, linked from `TEST_REPORT.md`, and no unresolved integrity/security blocker remains.
- DV-1103 may start only after both platform checklists are complete. It must trace every `FR-001` through `FR-010`, nonfunctional requirement, release blocker, and known limitation to current implementation and evidence.
- DV-1104 may publish only after DV-1103 passes and the release assets, checksums, SBOM/licenses, release notes, evidence links, and rollback instructions are attached to the GitHub Release.
