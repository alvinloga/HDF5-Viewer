# Data Viewer v1 Traceability and Documentation Truth Audit Template

This template is the required starting point for DV-1103 after DV-1101 and
DV-1102 have completed, signed, and validator-passing evidence packets.

It does not complete DV-1103 by itself. Do not mark DV-1103 complete until this
template is filled with current implementation evidence, reviewed, and linked
from `TEST_REPORT.md`.

## 1. Candidate and platform evidence

| Field | Value |
|---|---|
| Candidate version | TODO |
| Candidate commit | TODO |
| GitHub Actions run | TODO |
| Windows DV-1101 signed packet | TODO |
| Windows packet validator command/result | `python tools/validate_release_acceptance_packet.py <windows-evidence-dir> --task-id DV-1101` -> TODO |
| Linux DV-1102 signed packet | TODO |
| Linux packet validator command/result | `python tools/validate_release_acceptance_packet.py <linux-evidence-dir> --task-id DV-1102` -> TODO |
| Package artifact pair | TODO |
| SHA-256 checksum files | TODO |
| SBOM and third-party licenses | TODO |
| `release-security-review.json` result | TODO |

DV-1103 must stop immediately if either signed platform packet is missing,
still contains `pending-manual` or `pending-after-upload`, fails
`tools/validate_release_acceptance_packet.py`, or records an unresolved
integrity/security blocker.

## 2. Functional requirement traceability

Every row must link implementation task IDs, source modules or public contracts,
tests, CI/manual evidence, known limitations, and reviewer notes.

| Requirement | Product requirement summary | Implementation tasks/modules | Automated tests and CI evidence | Manual Windows evidence | Manual Linux evidence | Status | Known limitations / notes |
|---|---|---|---|---|---|---|---|
| FR-001 | Open and identify supported inputs with safe probing and structured errors. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-002 | Browse hierarchical and flat sources lazily with searchable metadata. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-003 | View scalar, array, table, text, workbook, structured, image, and volume resources with explicit identity/scope. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-004 | Bound data scale through full/chunk/page/sample modes, cache, and temporary extraction budgets. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-005 | Analyze and visualize with compatible built-in plugins and reproducible provenance. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-006 | Compare resources only with explicit compatibility/alignment policies. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-007 | Safely edit supported formats with patch review, conflict checks, and failed-save protection. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-008 | Export explicit scopes with provenance, overwrite control, progress, and cancellation. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-009 | Save and restore `.dvw` workspaces without embedding large source data. | TODO | TODO | TODO | TODO | TODO | TODO |
| FR-010 | Provide structured diagnostics, task/problem surfaces, and no automatic uploads. | TODO | TODO | TODO | TODO | TODO | TODO |

Status values: `proved`, `proved-with-documented-limitation`,
`not-proved-blocking`, or `not-applicable-with-reason`.

## 3. Nonfunctional and release-blocker traceability

| Area | Requirement or blocker | Implementation tasks/modules | Evidence | Status | Known limitations / notes |
|---|---|---|---|---|---|
| Performance | Launch/open/tree/table/slice/cancel/cache budgets are measured and enforced. | TODO | TODO | TODO | TODO |
| Reliability | No `QThread.terminate()`, stale results ignored, source leases respected, atomic replacement verified. | TODO | TODO | TODO | TODO |
| Security | Pickle/YAML/XLSX/plugin boundaries, no arbitrary external plugin loading, no shell commands from file content. | TODO | TODO | TODO | TODO |
| Accessibility | Keyboard access, visible focus, non-color-only states, contrast, localization, high-DPI evidence. | TODO | TODO | TODO | TODO |
| Cross-platform | Windows and Linux package artifacts pass the same release matrix for the same commit. | TODO | TODO | TODO | TODO |
| Packaging | Version/name/artifact layout/checksums/SBOM/licenses/security review are coherent. | TODO | TODO | TODO | TODO |
| Rollback | Previous artifact/tag recovery and post-release smoke are documented. | TODO | TODO | TODO | TODO |

## 4. V1 format and gzip matrix

Each format row must cite contract tests, smoke/manual evidence, editability
state, gzip behavior, and any accepted limitation.

| Format | Base behavior evidence | `.gz` wrapper evidence | Edit state | Export / Save As evidence | Status | Known limitations |
|---|---|---|---|---|---|---|
| HDF5 | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| NPY | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| NPZ | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| CSV | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| TSV | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| TXT | TODO | TODO | Safe editing for uncompressed inputs | TODO | TODO | TODO |
| MAT | TODO | TODO | Read-only in v1 | TODO | TODO | TODO |
| NIfTI | TODO | Native `.nii.gz` plus generic wrapper routing evidence | Read-only in v1 | TODO | TODO | TODO |
| XLSX | TODO | TODO | Read-only in v1 | TODO | TODO | TODO |
| JSON | TODO | TODO | Read-only in v1 | TODO | TODO | TODO |
| YAML/YML | TODO | TODO | Read-only in v1 | TODO | TODO | TODO |

## 5. Documentation truth audit

Before DV-1103 passes, audit these documents against actual implementation and
current evidence. A document fails the audit if it describes a target capability
as current without implementation and evidence.

| Document | Truth check | Result | Required correction |
|---|---|---|---|
| `README.md` | Product name, current status, quick-start, format matrix, known gaps. | TODO | TODO |
| `README_EN.md` | Same claims as README and no stale legacy-product-name release claim. | TODO | TODO |
| `docs/PRODUCT_SPEC.md` | Requirements still match implemented release scope and known limitations. | TODO | TODO |
| `ARCHITECTURE.md` | Architecture invariants match current module boundaries. | TODO | TODO |
| `docs/FORMAT_SUPPORT.md` | Format/edit/gzip behavior matches tests and manual packets. | TODO | TODO |
| `docs/UI_UX_SPEC.md` | Visual/accessibility/localization claims match signed screenshots. | TODO | TODO |
| `docs/TESTING.md` | Test strategy and gates match CI and manual release evidence. | TODO | TODO |
| `docs/DEPENDENCIES.md` | PySide6/MIT/LGPL obligations, SBOM, and dependency locks are current. | TODO | TODO |
| `docs/INDEX.md` | Source-of-truth ordering and release acceptance entries are current. | TODO | TODO |
| `RELEASE.md` | Release status, blockers, artifact names, and sequence are current. | TODO | TODO |
| `CHANGELOG.md` | User-visible changes and known limitations are accurate. | TODO | TODO |
| `TEST_REPORT.md` | Commands, platforms, commits, runs, and results are exact and current. | TODO | TODO |
| `tasks/todo.md` | Completed task checkboxes have evidence; open gates remain open. | TODO | TODO |

Recommended scans:

```bash
rg -n "specified but not implemented|pending-manual|pending-after-upload|TODO|<legacy-product-name>|PyQt6|NetCDF|Zarr" README.md README_EN.md docs RELEASE.md CHANGELOG.md TEST_REPORT.md tasks
python -m pytest tests/test_release_acceptance_docs.py tests/test_release_acceptance_packet.py -q
```

Explain every remaining match. Historical references are allowed only when they
are clearly labeled historical or out-of-scope.

## 6. Known limitations and release notes alignment

List every limitation that remains true for the candidate. Each accepted
limitation must be reflected consistently in `RELEASE.md`,
`docs/RELEASE_NOTES_TEMPLATE.md`, `CHANGELOG.md`, and `TEST_REPORT.md`.

| Limitation | User impact | Integrity/security impact? | Evidence | Release-note wording | Accepted by |
|---|---|---:|---|---|---|
| TODO | TODO | TODO | TODO | TODO | TODO |

## 7. Link and conflict audit

| Check | Command or method | Result |
|---|---|---|
| Local Markdown links | TODO | TODO |
| Duplicate authoritative backlog/spec claims | TODO | TODO |
| Stale release/version/name claims | TODO | TODO |
| Unresolved manual placeholders | TODO | TODO |
| Documentation lower-precedence conflicts | TODO | TODO |

## 8. Independent reviewer sample checks

The independent reviewer must sample across implementation, tests, evidence, and
documentation rather than reading this audit only.

| Sample | Reviewer check | Evidence inspected | Result | Notes |
|---|---|---|---|---|
| FR sample | Pick at least three FR rows including one edit flow and one plugin/visualization flow. | TODO | TODO | TODO |
| Format sample | Pick at least three formats including one gzip wrapper and one read-only format. | TODO | TODO | TODO |
| Platform sample | Compare one Windows and one Linux evidence packet row for the same behavior. | TODO | TODO | TODO |
| Security sample | Inspect one unsafe-input boundary and one release-security-review result. | TODO | TODO | TODO |
| Documentation sample | Verify one README/Release/CHANGELOG claim against source/tests/evidence. | TODO | TODO | TODO |

DV-1103 can pass only after the reviewer records no blocking discrepancy or all
blocking discrepancies have linked fixes and fresh evidence.

## 9. Final DV-1103 sign-off

I confirm that every Data Viewer v1 product requirement, nonfunctional
requirement, release blocker, known limitation, and user-visible documentation
claim has been traced to current implementation and evidence, or explicitly
classified as an accepted limitation.

- Reviewer:
- Signature:
- Date/time/timezone:
- Linked `TEST_REPORT.md` section:
