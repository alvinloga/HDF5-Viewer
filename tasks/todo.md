# Data Viewer v1 Executable Task Ledger

## How to use this file

Select the first unchecked task whose dependencies are checked. Read its listed contracts and `AGENTS.md`. Implement only that scope. A checkbox may be marked complete only after acceptance, verification, and documentation updates pass for the current revision.

Common completion rules for every task:

- tests are added/updated before or with behavior;
- success, empty, malformed/error, cancellation, and close/lifecycle paths are covered where applicable;
- targeted tests plus required wider gates pass;
- no public API/on-disk/spec behavior changes without matching contract/ADR updates;
- task evidence is recorded in the PR/commit notes; checkpoint evidence is also appended to `TEST_REPORT.md`;
- normally no more than 3–5 product files change, excluding tests, fixtures, generated locks, and docs.

Paths under `data_viewer/` are target paths created incrementally during migration.

---

## P0 — Trustworthy baseline

### [x] DV-0001 Create canonical project metadata and package skeleton

- Depends: none.
- Read: Product Spec §2, Dependencies §1–4, Migration §3 Stage A.
- Scope: `pyproject.toml`, `data_viewer/__init__.py`, `data_viewer/__main__.py`, minimal packaging metadata; keep legacy `main.py` runnable.
- Acceptance: one canonical package name/version source; Python 3.12 declared; runtime/dev/packaging groups separated; no NetCDF/Zarr dependency; `python -m data_viewer` exits with a clear development-shell message until bootstrap task.
- Verify: `python -m pip install -e ".[dev]"`; `python -c "import data_viewer; print(data_viewer.__version__)"`; legacy compile command.

### [x] DV-0002 Resolve and lock Windows/Linux dependencies

- Depends: DV-0001.
- Read: Dependencies entire document, ADR-008.
- Scope: selected lock/constraints configuration, Windows/Linux lock outputs, dependency license inventory process.
- Acceptance: clean Windows and Linux Python 3.12 environments install from committed locks; all direct imports smoke; exact lock generation command documented; PyQt6 distribution license decision recorded or public packaging explicitly blocked.
- Verify: fresh-venv locked install and import smoke for PyQt6, NumPy, h5py, pandas, SciPy, NiBabel, openpyxl, PyYAML, Matplotlib, jsonschema, platformdirs.

### [x] DV-0003 Repair and isolate pytest collection

- Depends: DV-0001, DV-0002.
- Read: Testing §1–4.
- Scope: `tests/conftest.py`, pytest config, application-path/config fixtures; do not weaken product assertions.
- Acceptance: full collection succeeds; Qt uses offscreen in headless runs; tests write only temporary dirs; locale/theme/config/singletons reset; static and collected counts are reported distinctly.
- Verify: `python -m pytest --collect-only -q`; run twice in different order/seed if configured; assert repository `config.json` unchanged.

### [x] DV-0004 Consolidate legacy tests and establish fixture factories

- Depends: DV-0003.
- Read: Testing §3, §5.
- Scope: remove exact duplicate tests, create `tests/fixtures/` factory helpers, retain unique regression coverage.
- Acceptance: every removed test is proven duplicate; tiny HDF5/NPY/CSV fixture factories are deterministic; no large opaque binary added; current baseline failures are classified, not hidden.
- Verify: full non-GUI suite; fixture creation/reopen smoke; `git diff` review for assertion loss.

### [x] DV-0005 Add quality and dual-platform CI before build/release

- Depends: DV-0002, DV-0003.
- Read: Testing §12, ADR-008, Release.
- Scope: split/update `.github/workflows/` for lint/type/test/build; release depends on all required jobs.
- Acceptance: Windows/Ubuntu matrices run locked install, collection, lint, types, compile, unit/integration/offscreen GUI; reports uploaded; build/release cannot run past failed tests; dependency caches key on lock hash.
- Verify: workflow syntax validation; CI run on both platforms; deliberate test failure proves build/release blocked, then revert deliberate failure.

### [x] DV-0006 Record Checkpoint 0 evidence

- Depends: DV-0001 through DV-0005.
- Scope: update `TEST_REPORT.md` only with actual commands/results/environment/lock hash.
- Acceptance: clean install/collection/gates have reproducible evidence; remaining baseline failures have owners/task IDs; no percentage without denominator/artifact.
- Verify: independent rerun of documented commands on at least one local platform and CI evidence for the other.

---

## P1 — Domain and runtime kernel

### [x] DV-0101 Implement immutable resource/domain/capability types

- Depends: DV-0006.
- Read: Architecture §5, DataSource API §3, ADR-002.
- Scope: `data_viewer/domain/resources.py`, `metadata.py`, `capabilities.py`, focused tests.
- Acceptance: canonical ResourceId/path/domain/capability/metadata types match the contract; JSON-safe serialization is explicit; equality/hash behavior stable; no GUI/library-specific object fields.
- Verify: domain unit tests, mypy, API import test.

### [x] DV-0102 Implement normalized selections and payload values

- Depends: DV-0101.
- Read: DataSource API selection/payload sections, Safe Editing coordinates.
- Scope: `data_viewer/domain/selection.py`, `payload.py`, tests.
- Acceptance: All/Index/Slice/Hyperslab/table-page selections normalize bounds/negative indices/steps without implicit flattening; payload maps display values to original coordinates; invalid selections return structured validation errors.
- Verify: parametrized and property tests for scalar through high-dimensional shapes; mypy.

### [x] DV-0103 Implement structured error taxonomy and diagnostics values

- Depends: DV-0101.
- Read: DataSource API structured errors, Architecture error handling.
- Scope: `data_viewer/domain/errors.py`, `data_viewer/app/diagnostics.py`, tests.
- Acceptance: stable error code/category/severity/target/remediation/details/cause ID; safe user message separated from traceback; source/plugin/task/workspace errors map consistently.
- Verify: mapping/serialization/redaction tests and exception-chain tests.

### [x] DV-0104 Implement Task state machine and cooperative cancellation

- Depends: DV-0103.
- Read: Architecture task model, ADR-003, Testing determinism.
- Scope: `data_viewer/tasks/state.py`, `cancellation.py`, `dispatcher.py`, tests.
- Acceptance: legal queued/running/cancelling/terminal transitions; thread-safe progress; cooperative token; exactly one terminal result; no `QThread.terminate`; callbacks marshal to GUI thread through an injectable dispatcher.
- Verify: transition/race/cancel/error tests, repeated stress, GUI-thread dispatch test.

### [x] DV-0105 Implement SourceAdapter/Session registry and conformance harness

- Depends: DV-0101 through DV-0104.
- Read: DataSource API entire document, ADR-002.
- Scope: `data_viewer/sources/api.py`, `registry.py`, `tests/conformance/source_adapter.py`, fake adapter.
- Acceptance: exact public v1 contract; bounded probe arbitration; duplicate format/extension diagnostics; lifecycle enforcement; fake adapter passes metadata/list/read/cancel/error/close conformance.
- Verify: conformance suite, forbidden library-object boundary tests, mypy.

### [x] DV-0106 Implement DocumentController ownership and request versioning

- Depends: DV-0104, DV-0105.
- Read: Architecture source lifecycle, ADR-003.
- Scope: `data_viewer/app/documents.py`, `data_viewer/app/active_context.py`, tests.
- Acceptance: controller solely owns session; view IDs borrow resources; new navigation invalidates old request results; close cooperatively cancels/waits then closes once; dirty/active-task hooks exist without GUI dependency.
- Verify: rapid navigation stale-result test, close-during-read, double-close, task failure, multiple-view-one-source tests.

### [x] DV-0107 Implement platform paths, bounded cache, config, and logging primitives

- Depends: DV-0103.
- Read: Architecture cache/config/platform, Dependencies platformdirs.
- Scope: `data_viewer/infrastructure/paths.py`, `cache.py`, `config.py`, `logging.py` plus tests.
- Acceptance: platform-standard locations; versioned validated config; byte/entry/age cache limits and eviction; test override; logs redact configured sensitive paths/values; no repository config writes.
- Verify: Windows/Linux CI path tests, corrupt config recovery, cache eviction/cleanup, redaction tests.

### [x] DV-0108 Record Checkpoint 1 kernel evidence

- Depends: DV-0101 through DV-0107.
- Acceptance: fake vertical flow proves open/list/read/cancel/stale/close; imports obey layers; full existing suite remains green.
- Verify: kernel/conformance/full non-GUI/compile/lint/type commands recorded in `TEST_REPORT.md`.

---

## P2 — HDF5 vertical slice

### [x] DV-0201 Implement HDF5 probe and session lifecycle

- Depends: DV-0108.
- Read: Format Support §4.1, DataSource API, ADR-002/003.
- Scope: `data_viewer/sources/hdf5/adapter.py`, `session.py`, fixtures/tests.
- Acceptance: signature validation, least-permission mode, stable fingerprint, explicit close, safe error mapping; no recursive scan or payload read on open; external links not followed.
- Verify: valid/wrong-extension/malformed/locked/missing/unicode path/open-close stress tests plus shared conformance probe/lifecycle.

### [x] DV-0202 Implement lazy hierarchy and metadata

- Depends: DV-0201.
- Scope: HDF5 listing/metadata modules and tests.
- Acceptance: direct-child pagination; group/dataset/link/broken-link representation; cycle protection; shape/dtype/chunk/compression/fill/storage/attributes; large tree open is bounded.
- Verify: hierarchy/link/attribute fixtures, pagination stability, instrumentation proves no full recursive walk.

### [x] DV-0203 Implement direct bounded HDF5 selections

- Depends: DV-0102, DV-0202.
- Scope: HDF5 selection reader/conversion and tests.
- Acceptance: selection sent to h5py before materialization; scalar/empty/1D/2D/high-dimensional/compound/string/complex/boolean values retain coordinates and dtype semantics; byte estimates enforce budget.
- Verify: selection equivalence/property tests, whole-read spy rejection, cancellation between chunks, memory benchmark smoke.

### [x] DV-0204 Build minimal target Qt bootstrap and shell

- Depends: DV-0106, DV-0107.
- Read: UI/UX §3–4, Migration Stage C.
- Scope: `data_viewer/gui/app.py`, `shell.py`, `commands.py`, update `__main__.py`.
- Acceptance: target app launches; Open command creates controller asynchronously; shell has navigation/workspace/inspector/bottom/status regions; legacy bootstrap remains available only as explicit development fallback.
- Verify: offscreen launch/open/cancel/close tests; GUI-thread responsiveness probe.

### [x] DV-0205 Build HDF5 structure, array/table, and metadata vertical views

- Depends: DV-0202 through DV-0204.
- Read: UI/UX core views/states.
- Scope: structure model, array/table view model, metadata inspector, tests.
- Acceptance: tree lazy expands; single click metadata/Enter open; virtual table requests pages/slices; high-dimensional axis controls; explicit loading/empty/partial/error/read-only states; active source/path/shape/dtype/slice visible.
- Verify: pytest-qt navigation/state/rapid-select/close tests; no widget-per-cell test; deterministic screenshots for vertical slice.

### [x] DV-0206 Record Checkpoint 2 HDF5 vertical evidence

- Depends: DV-0201 through DV-0205.
- Acceptance: representative large hierarchy opens/navigates without UI freeze or uncontrolled load; repeated open/close stable; known legacy differences recorded.
- Verify: HDF5 conformance, GUI vertical e2e, stress/memory, full gate recorded in `TEST_REPORT.md`.

---

## P3 — Safe editing and export

### [x] DV-0301 Implement patch/change-set and dtype validation

- Depends: DV-0102, DV-0206.
- Read: Safe Editing §3–5, ADR-004.
- Scope: `data_viewer/editing/patches.py`, `validation.py`, `history.py`, tests.
- Acceptance: immutable coordinate patches/fingerprints; overflow/string truncation/complex/nonfinite/missing/structured rules; undo/redo/discard; reverting all is clean.
- Verify: dtype edge/property tests and unrelated-coordinate invariants.

### [x] DV-0302 Implement save/conflict state and review model

- Depends: DV-0301, DV-0106.
- Scope: `data_viewer/editing/session.py`, `review.py`, controller integration, tests.
- Acceptance: CLEAN/DIRTY/SAVING/SAVE_FAILED/CONFLICTED legal transitions; external fingerprint check; review lists target/strategy/resources/patches/size/warnings; close choices Save/Discard/Cancel.
- Verify: state transition, external change, close dirty/multiple documents, validation failure tests.

### [x] DV-0303 Implement verified atomic replacement service

- Depends: DV-0302, DV-0107.
- Read: Safe Editing §7, §10–11.
- Scope: `data_viewer/persistence/transaction.py`, `recovery.py`, filesystem adapter, tests.
- Acceptance: same-directory temp, disk preflight, write/flush/fsync/reopen validate/atomic replace/final reopen; honest cross-filesystem behavior; startup recovery metadata; cancellation only before commit boundary.
- Verify: injected failure at every step, Windows lock/Linux permission CI tests, insufficient disk, cancellation, orphan cleanup.

### [x] DV-0304 Implement HDF5 persistence strategies

- Depends: DV-0203, DV-0303.
- Scope: HDF5 writer/validator and tests.
- Acceptance: safe direct selections only under contract conditions; structural/unsafe cases use replacement; every changed coordinate reread; unaffected data/metadata verified; failed verification yields integrity warning and retained change log.
- Verify: cell/attribute/multi-patch/compound tests, fault matrix, source-change conflict, large bounded selection.

### [x] DV-0305 Implement export plan and receipt service

- Depends: DV-0102, DV-0303.
- Read: Safe Editing §9, Product FR-007.
- Scope: `data_viewer/exporting/plan.py`, `service.py`, `receipt.py`, tests.
- Acceptance: full/slice/selection/filtered/result/rendered scopes explicit; raw/display/scaled semantics; conversion warnings before write; receipt includes fingerprint/resource/selection/parameters/version/result.
- Verify: scope coordinate golden tests, cancel/failure/overwrite tests, receipt schema/round trip.

### [x] DV-0306 Build edit review, save, conflict, and export UI

- Depends: DV-0302 through DV-0305.
- Read: UI/UX state/dialog rules.
- Scope: edit markers/history panel, save summary/conflict dialog, export flow, tests.
- Acceptance: dirty/read-only/conflict not color-only; original/current values accessible; destructive target named; invalid save disabled; read-only offers Save As/export; task progress/cancel/details visible.
- Verify: pytest-qt full edit/save/conflict/close/export flows and theme screenshots.

### [x] DV-0307 Record Checkpoint 3 persistence evidence

- Depends: DV-0301 through DV-0306.
- Acceptance: HDF5 edit and generic transaction integrity proven; export scope/provenance proven; no read-only overwrite path.
- Verify: all editing/export/fault/e2e tests on Windows/Linux CI and ledger update.

---

## P4 — Format adapters and writers

### [x] DV-0401 Implement NPY adapter and writer

- Depends: DV-0108, DV-0303.
- Read: Format Support §4.2, NumPy security rule.
- Scope: NPY adapter/session/writer and fixtures/tests.
- Acceptance: `allow_pickle=False`; mmap when valid; scalar/empty/structured/order/byte-order preserved; object arrays rejected; replacement save validates header/shape/dtype/patches.
- Verify: shared conformance, security fixtures, round-trip/property/fault tests.

### [x] DV-0402 Implement NPZ adapter and archive-rebuild writer

- Depends: DV-0401.
- Read: Format Support §4.3.
- Scope: NPZ adapter/session/writer and tests.
- Acceptance: synthetic member hierarchy; no pickle; traversal/duplicate/encrypted/ratio/count/size defenses; edits rebuild verified archive; unaffected member semantics preserved.
- Verify: conformance, adversarial ZIP fixtures, edit/reopen/fault tests.

### [x] DV-0403 Implement delimited import preview and CSV/TSV adapter

- Depends: DV-0108, DV-0303.
- Read: Format Support §4.4.
- Scope: delimited options/preview/session modules and tests.
- Acceptance: bounded preview; explicit encoding/dialect/header/missing/dtype schema; strict decoding; chunked stable row identity; no silent inference after confirmation.
- Verify: delimiter/quote/BOM/unicode/malformed/large chunk fixtures and conformance.

### [x] DV-0404 Implement CSV/TSV verified writer

- Depends: DV-0301, DV-0403.
- Scope: delimited writer/validator and tests.
- Acceptance: confirmed dialect/encoding preserved; full temporary rewrite; row/column/schema validation; patches apply only original row coordinates; external conflict handled.
- Verify: round-trip dialect/line endings/quotes/missing/dtype tests and transaction fault matrix.

### [x] DV-0405 Implement TXT text/table dual-mode adapter and writer

- Depends: DV-0403, DV-0404.
- Read: Format Support §4.5.
- Scope: TXT mode/stream/session/writer and tests.
- Acceptance: strict UTF-8/BOM initial behavior; bounded text preview; user-confirmed alternative encoding/table parse; line endings/final newline preserved in text mode; no lossy silent table inference.
- Verify: encoding/line-ending/large text/table ambiguity/edit/reopen tests.

### [x] DV-0406 Implement JSON structured adapter

- Depends: DV-0108.
- Read: Format Support §4.9.
- Scope: JSON adapter/resource mapping/budget validator and tests.
- Acceptance: UTF-8/BOM, JSON Pointer paths, scalar root, duplicate-key warning, byte/depth/collection/string budgets; read-only capability.
- Verify: conformance plus duplicate/deep/large/malformed/unicode fixtures.

### [x] DV-0407 Implement restricted YAML adapter

- Depends: DV-0406.
- Read: Format Support §4.10.
- Scope: YAML adapter/restricted loader/resource mapping and tests.
- Acceptance: safe loader only; Python/custom tags rejected; aliases/depth/size limited; typed nonstring keys and merge/alias semantics surfaced; read-only.
- Verify: conformance and adversarial constructor/alias-expansion/depth fixtures.

### [x] DV-0408 Implement MAT adapter for legacy and v7.3

- Depends: DV-0202, DV-0108.
- Read: Format Support §4.6.
- Scope: MAT dispatcher, SciPy session, HDF5-v7.3 mapping, tests.
- Acceptance: content/version detection; unified stable variable tree; explicit cells/structs/chars/sparse/complex/logical/nested handling; reference cycle/budget control; internal metadata hidden-by-default; read-only.
- Verify: conformance and representative generated/version fixtures including unsupported value states.

### [x] DV-0409 Implement safe XLSX adapter

- Depends: DV-0108.
- Read: Format Support §4.8.
- Scope: XLSX adapter/session/resource mapping and tests.
- Acceptance: workbook/sheet/cell/table/name/merge inspection; bounded read-only iteration; formula text/cached distinction; external links disabled; encrypted file error; blank vs missing preserved; no `.xlsm` claim.
- Verify: conformance and formulas/external/encrypted/merged/sparse/unicode workbook fixtures.

### [x] DV-0410 Implement NIfTI adapter and coordinate model

- Depends: DV-0102, DV-0108.
- Read: Format Support §4.7.
- Scope: NIfTI adapter/session/spatial metadata/coordinate transforms and tests.
- Acceptance: `.nii`/native `.nii.gz`; proxy bounded slices; header/affine/axis codes/voxel sizes/units/intent/scaling; exact voxel↔world mapping; no silent canonicalization/resampling; 3D/4D; read-only.
- Verify: conformance and known affine/orientation/scaling/time/invalid-header golden tests; full-materialization spy.

### [x] DV-0411 Remove NetCDF/Zarr product paths

- Depends: DV-0401 through DV-0410.
- Read: ADR-001, Migration.
- Scope: registry/dependencies/menu/docs/build tests; historical mentions may remain labeled.
- Acceptance: not registered, advertised, imported, or packaged; no shared domain depends on them; user receives ordinary unsupported-format error.
- Verify: case-insensitive repository search with reviewed historical exceptions; registry/package dependency tests.

### [x] DV-0412 Record Checkpoint 4 uncompressed format evidence

- Depends: DV-0401 through DV-0411.
- Acceptance: every uncompressed format passes common and specific matrices; edit/read-only capabilities truthful; security rules proven.
- Verify: adapter suite on Windows/Linux, format inventory report, ledger update.

---

## P5 — Gzip composition

### [x] DV-0501 Implement compound format detection and gzip stream wrapper

- Depends: DV-0412.
- Read: Format Support §5, ADR-007.
- Scope: suffix parser, gzip probe/stream, registry integration, tests.
- Acceptance: longest-first `.nii.gz`; content validation; bounded decompressed prefix; streaming inner adapters for text formats; structured corrupt/truncated errors.
- Verify: all text-like gzip conformance fixtures, false-extension tests, cancellation.

### [x] DV-0502 Implement managed random-access extraction cache

- Depends: DV-0107, DV-0501.
- Scope: extraction task/cache identity/janitor and tests.
- Acceptance: free-disk/size/ratio/budget preflight; progress/cancel; canonical fingerprint cache keys; incomplete cleanup; expired startup cleanup; extracted handles obey source lifetime.
- Verify: random-access gzip fixtures, bomb-like limits, disk/cancel/crash-recovery simulation, cache invalidation.

### [x] DV-0503 Integrate every gzip format and read-only UX

- Depends: DV-0502.
- Scope: adapter registry capability wrapping, Open/Save As UI messages, tests.
- Acceptance: gzip form of every v1 extension opens; generic wrapper read-only; `.npz.gz`/`.xlsx.gz` inefficient warning; native NIfTI labeling; output dialogs do not propose nested compression.
- Verify: generated matrix across extensions on both platforms plus UI state tests.

### [x] DV-0504 Record Checkpoint 5 gzip evidence

- Depends: DV-0501 through DV-0503.
- Verify: complete gzip/security/cleanup/performance suite and ledger update.

---

## P6 — UI system and shell

### [x] DV-0601 Implement semantic themes, metrics, typography, and SVG icons

- Depends: DV-0206.
- Read: UI/UX §5–6, ADR-009.
- Scope: theme tokens/metrics/icon loader and component tests.
- Acceptance: light/dark roles centralized; 4 px scale and compact metrics; system/monospace roles; one monochrome SVG set; no emoji/Unicode pseudo-icons/hard-coded component colors.
- Verify: token completeness, contrast calculation, icon accessibility, repository palette/icon scan.

### [x] DV-0602 Implement command registry and ActiveContext

- Depends: DV-0106, DV-0601.
- Scope: command definitions, shortcuts, context predicates, tests.
- Acceptance: one source for label/shortcut/enabled reason/action; correct active split/view/resource/selection/task/dirty targeting; disabled reason visible; Linux conflicts have documented alternate.
- Verify: context matrix and rapid focus/split tests.

### [x] DV-0603 Rebuild navigation, tabs/splits, inspector, bottom panel, status bar

- Depends: DV-0205, DV-0602.
- Scope: shell panels/models/layout persistence hooks and tests.
- Acceptance: one authoritative structure tree; resizable/collapsible responsive panels; explicit active split; Tasks/Output/Problems; status source/mode/shape/dtype/scope/task; 1024×768 usable.
- Verify: pytest-qt focus/navigation/resize/panel tests and target screenshot matrix subset.

### [x] DV-0604 Implement standard asynchronous/state components

- Depends: DV-0601, DV-0603.
- Scope: standard initial/loading/empty/ready/partial/error/disabled/dirty/read-only/conflicted/stale components, tests.
- Acceptance: every state has required label/action/accessibility; errors have safe summary/details/retry; no fake data skeleton; states do not rely on color.
- Verify: component state matrix, keyboard/screen-reader property tests, theme screenshots.

### [x] DV-0605 Implement virtual table/array/text/image base views

- Depends: DV-0603, DV-0604, DV-0412.
- Scope: common view contracts and four view models/widgets, tests.
- Acceptance: paged/virtual access; no implicit flatten; coordinate/slice/scope visible; strict text partial banner; image aspect/zoom/interpolation/cursor value; plugin/result extensibility.
- Verify: large synthetic scroll/slice tests, no widget-per-cell, bounded read instrumentation, keyboard navigation.

### [x] DV-0606 Implement import/save/export/options dialogs to UI spec

- Depends: DV-0306, DV-0405, DV-0604.
- Scope: import preview, options, destructive confirmation, path/validation widgets, tests.
- Acceptance: non-destructive open; preview-first import; target-specific save summary; inline validation; long paths selectable/elided; safe default button behavior.
- Verify: keyboard/invalid/default/destructive/path/localization GUI tests.

### [x] DV-0607 Add accessibility, high-DPI, and English/Chinese localization baseline

- Depends: DV-0601 through DV-0606.
- Scope: translation catalogs, accessibility helpers, test tooling.
- Acceptance: all visible strings centralized; English and Simplified Chinese complete for v1 shell; names/roles/tab order/focus; 200% scaling; plot summary contract established.
- Verify: missing translation scan, focus traversal, accessible property audit, Windows/Linux DPI screenshots.

### [x] DV-0608 Record Checkpoint 6 UI evidence

- Depends: DV-0601 through DV-0607.
- Verify: UI/UX visual acceptance matrix subset plus automated GUI/accessibility/localization gates and ledger update.

---

## P7 — Plugin platform

### [x] DV-0701 Implement plugin manifest schema and built-in registry

- Depends: DV-0105, DV-0608.
- Read: Plugin API §2–3, §11, ADR-005.
- Scope: plugin public types, JSON Schema, registry/diagnostics, tests.
- Acceptance: packaged built-ins only; validate before import; unique stable IDs; API/schema versions; deterministic order; bad plugin does not fail startup.
- Verify: valid/invalid/duplicate/unsupported/lazy import tests.

### [x] DV-0702 Implement compatibility evaluator and parameter form

- Depends: DV-0701, DV-0602.
- Scope: compatibility service, supported JSON Schema subset, standard form renderer, tests.
- Acceptance: domain/dim/dtype/access/size/multi-input/dependency reasons exact; disabled visible; defaults/validation immutable and round-trip; plugins create no dialogs.
- Verify: compatibility reason matrix and schema/widget/property tests.

### [x] DV-0703 Implement budgeted InputAccess and plugin runner

- Depends: DV-0104, DV-0702.
- Scope: input access, runner/task integration, PluginError mapping, tests.
- Acceptance: no raw source/library handles; bounded reads/chunks; memory/temp budgets; progress/cancel; no partial final result; traceback only diagnostics.
- Verify: conformance runner tests, cancel under multiple chunks, budget/error/close/stale input tests.

### [x] DV-0704 Implement typed results, declarative PlotSpec, and provenance

- Depends: DV-0703, DV-0605.
- Scope: result validators/store, PlotSpec types/renderer interface, provenance UI/export, tests.
- Acceptance: summary/table/array/image/plot/collection validation; large result store bounded; plot marks supported; scope/sample/version/input/parameters/warnings always visible/exported.
- Verify: result schema/property tests, invalid/oversized rejection, theme/accessibility renderer contract.

### [x] DV-0705 Add plugin conformance kit and complete reference plugin

- Depends: DV-0704.
- Scope: reusable conformance tests and packaged Range/Dataset Profile reference implementation/manifest/tests.
- Acceptance: manifest, compatibility, params, chunks, cancel, progress, errors, numerical golden, edge inputs, result/provenance, forbidden imports all demonstrated.
- Verify: run conformance suite on reference plugin on Windows/Linux.

### [x] DV-0706 Record Checkpoint 7 plugin platform evidence

- Depends: DV-0701 through DV-0705.
- Verify: platform/conformance/UI integration and ledger update.

---

## P8 — Analysis and visualization plugins

Each plugin task depends on DV-0706, includes its manifest/package/numerical or rendering tests, and must pass the shared conformance kit.

### [x] DV-0801 Implement Dataset Profile and Descriptive Statistics

- Acceptance: shape/dtype/storage/count/missing/finite/range plus axis-aware mean/std/quantiles/extrema; stable algorithms; empty/complex/masked/nonfinite rules; chunked operation and scope label.
- Verify: independent NumPy/SciPy reference goldens across dtypes/axes/chunks.

### [x] DV-0802 Implement Distribution Summary

- Depends: DV-0801.
- Acceptance: histogram/robust spread/skew/kurtosis only when valid; explicit bins/missing policy; full or recorded deterministic sample.
- Verify: known distributions, constants, empty/nonfinite, deterministic sampling goldens.

### [x] DV-0803 Implement Correlation/Covariance

- Depends: DV-0801.
- Acceptance: selected numeric columns/axis, exact alignment/missing policy, symmetric labeled output, constant-column warning, size budget.
- Verify: known matrices, pairwise/listwise policy tests, refusal cases.

### [x] DV-0804 Implement Dataset Compare

- Depends: DV-0801.
- Acceptance: identity/shape/dtype/schema compatibility; no ambiguous broadcasting; exact equality and absolute/relative errors with zero/nonfinite rules; alignment/scope visible.
- Verify: identical/near/different/incompatible/aligned coordinate goldens.

### [x] DV-0805 Implement line, scatter, histogram, and box plots

- Depends: DV-0801, DV-0802.
- Acceptance: declarative plots; axes/series/units/legends; bounded points or explicit sampling; theme/accessibility/data-table/copy/export.
- Verify: PlotSpec goldens, sampling, empty/nonfinite, light/dark render smoke.

### [x] DV-0806 Implement image and multidimensional slice navigator

- Depends: DV-0605.
- Acceptance: aspect/zoom/interpolation/value/cursor/source coordinates; axis/index controls; linked slices; bounded reads; raw/display mode.
- Verify: coordinate/shape/high-dimensional/cancel/rapid navigation tests.

### [x] DV-0807 Implement correlation heatmap and missing-data map

- Depends: DV-0803.
- Acceptance: labeled axes/legend/range; large table budget/sampling; missing semantics; accessible table alternative.
- Verify: known matrix/missing pattern PlotSpec and render tests.

### [x] DV-0808 Implement NIfTI orthogonal viewer and inspector

- Depends: DV-0410, DV-0806.
- Acceptance: axial/coronal/sagittal linked crosshairs; correct orientation labels; voxel/world coordinates; 4D volume index; window/level; raw/scaled values; header/affine inspection; no source resampling.
- Verify: known affine/orientation/coordinate goldens and GUI navigation/screenshots.

### [x] DV-0809 Record Checkpoint 8 plugin catalog evidence

- Depends: DV-0801 through DV-0808.
- Verify: all conformance/numerical/render/performance/platform tests and ledger update.

---

## P9 — Workspace, comparison, usability

### [x] DV-0901 Implement `.dvw` schema, model, deterministic atomic save/load

- Depends: DV-0303, DV-0608.
- Read: Workspace Format, ADR-006.
- Scope: workspace model/schema/serializer/service and tests.
- Acceptance: exact v1 fields/types/budgets; no executable/bulk data; relative/absolute paths; unknown preservation; deterministic UTF-8; atomic save; source dirty independent.
- Verify: schema fixtures, golden round-trip, failure/newer-version/security tests.

### [x] DV-0902 Implement asynchronous restore, relocation, and degraded mode

- Depends: DV-0901, DV-0504.
- Scope: restore coordinator, relocation matcher, degraded UI, tests.
- Acceptance: available sources restore independently; missing/moved/changed/ambiguous explicit; no silent relink; view shells then metadata/payload; stale results; confirmed updates only.
- Verify: full restoration matrix, cancel/partial failure, non-ASCII relative paths on both platforms.

### [x] DV-0903 Implement comparison domain and workspace

- Depends: DV-0804, DV-0901.
- Scope: comparison alignment/state/controller/view and tests.
- Acceptance: left/right identity/alignment/difference visible; compatible index/axis/column modes; linked navigation toggle; no implicit broadcast; workspace persistence/provenance.
- Verify: alignment/difference/incompatibility/rapid navigation/restore tests.

### [x] DV-0904 Implement recent/pinned/favorites/history and global search

- Depends: DV-0603, DV-0901.
- Scope: navigation/recent/favorite/search services and UI models/tests.
- Acceptance: platform config not workspace leakage; path/name/domain/dtype/shape/regex filters; cancellable grouped results; back/forward semantic history; missing recent item remediation.
- Verify: search correctness/cancel/regex error, history/active split, config migration tests.

### [x] DV-0905 Implement session restore and external file change detection

- Depends: DV-0902, DV-0302.
- Scope: session manifest pointer/restore policy/file watcher integration/tests.
- Acceptance: startup asks/restores safely; dirty patches never auto-overwrite; change notification leads reload/Save As/cancel; self-save events do not cause false conflict.
- Verify: changed/deleted/replaced/self-save/restart/crash-recovery simulations.

### [x] DV-0906 Implement background export queue and Diagnostics

- Depends: DV-0305, DV-0107, DV-0603.
- Scope: export tasks/history, diagnostics bundle/redaction UI/service, tests.
- Acceptance: queued progress/cancel/retry; receipt access; Problems links to task/source; diagnostics includes versions/platform/plugins/recent errors but redacts configured paths/data; user previews bundle.
- Verify: multi-export/cancel/failure, redaction/property, diagnostics package tests.

### [x] DV-0907 Record Checkpoint 9 workbench evidence

- Depends: DV-0901 through DV-0906.
- Verify: workspace/compare/usability e2e matrix on Windows/Linux and ledger update.

---

## P10 — Hardening and packaging

### [ ] DV-1001 Establish and enforce performance/memory/cache budgets

- Depends: DV-0907.
- Read: Testing §11, Architecture cache/performance.
- Scope: benchmark generators/harness, budget config, regressions identified by evidence.
- Acceptance: launch/open/tree/table/slice/NIfTI/cancel/repeated close/gzip/plugin metrics on named hardware; numeric thresholds encoded after both-platform baseline; bounded behavior enforced.
- Verify: reproducible benchmark report with median/high percentile/peak memory.

### [ ] DV-1002 Run stress, leak, and adversarial hardening pass

- Depends: DV-1001.
- Scope: repeated open/close, rapid navigation, many tasks, corrupt formats, archives/decompression, workspace depth, plugin budgets; fixes remain small tasks if found.
- Acceptance: no persistent session/task/temp leak; cancellation latency within budget; adversarial inputs structured-fail without UI crash/unbounded resource use.
- Verify: soak/stress/security suite on both platforms with retained logs.

### [ ] DV-1003 Complete Data Viewer name and canonical version migration

- Depends: DV-0907.
- Read: Migration §5.
- Scope: package/bootstrap/window/About/diagnostics/build artifact/desktop metadata/docs/tests.
- Acceptance: one version source; every current surface says Data Viewer; remaining HDF5 Viewer occurrences are explicitly historical; git tags unchanged.
- Verify: case-insensitive repository/artifact/runtime scan and version consistency test.

### [ ] DV-1004 Migrate platform configuration and retire repository runtime config

- Depends: DV-0107, DV-1003.
- Read: Migration §6.
- Scope: legacy config importer, target schema/version, bootstrap integration/tests.
- Acceptance: validate/preview/migrate atomically; legacy file not modified/deleted; corrupt/unknown safe; tests use temp paths; QStandardPaths/platformdirs target.
- Verify: first-run/migrate/decline/corrupt/upgrade/downgrade tests on both platforms.

### [ ] DV-1005 Build Windows and Linux Data Viewer artifacts

- Depends: DV-0002, DV-1003, DV-1004.
- Read: Dependencies, Release, ADR-008.
- Scope: PyInstaller specs/build scripts/workflows/package metadata.
- Acceptance: clean locked builds; Qt/native libs/resources/translations/icons/schemas/plugins/licenses included; names correct; no NetCDF/Zarr; deterministic enough for checksum tracking.
- Verify: CI build and extraction/import/launch smoke on both platforms.

### [ ] DV-1006 Add installed-artifact functional smoke and release chain

- Depends: DV-1005.
- Scope: packaged smoke harness/fixtures/workflow/release job dependencies.
- Acceptance: artifact launches, opens representative HDF5/CSV/NIfTI/gzip/workspace, runs reference plugin, exports, closes cleanly; release depends on both smoke jobs; logs/screenshots uploaded.
- Verify: successful tag-dry-run workflow; deliberate smoke failure blocks release, then revert deliberate failure.

### [ ] DV-1007 Generate SBOM, license notices, checksums, and security evidence

- Depends: DV-1005.
- Scope: CI generation/validation and release attachments.
- Acceptance: direct/transitive licenses reviewed; PyQt decision satisfied; SBOM and SHA-256 per artifact; dependency scan findings resolved or documented with owner/expiry; no credentials/paths leaked.
- Verify: regenerate and validate artifacts from CI outputs.

### [ ] DV-1008 Remove eligible legacy runtime code and compatibility bridges

- Depends: DV-1002, DV-1006.
- Read: Migration §4, §7.
- Scope: one legacy capability/removal group at a time; do not mix unrelated cleanup.
- Acceptance: parity/removal criteria proven; no runtime/test/build imports; target bootstrap default; legacy fallback removed; history/docs preserved.
- Verify: `rg` reference audit, import smoke, full tests, both packages.

### [ ] DV-1009 Record Checkpoint 10 release-candidate evidence

- Depends: DV-1001 through DV-1008.
- Verify: complete automated gates, performance/stress, package smokes, SBOM/licenses/checksums recorded in `TEST_REPORT.md`.

---

## P11 — Dual-platform v1 acceptance

### [ ] DV-1101 Complete Windows manual acceptance matrix

- Depends: DV-1009.
- Read: Product success criteria, UI/UX §13, Testing §14, Release.
- Acceptance: every format/gzip, edit/read-only/export, plugins, compare, workspace, error/cancel/recovery, English/Chinese, light/dark, 100/150/200% DPI, minimum/typical/large layout, keyboard/accessibility, packaged smoke pass; evidence identifies Windows version/hardware/artifact checksum.
- Verify: signed checklist, screenshots, logs, issue links; no unresolved integrity/security blocker.

### [ ] DV-1102 Complete Linux manual acceptance matrix

- Depends: DV-1009.
- Acceptance: same functional matrix as Windows at Linux 100/200% scaling on named supported distribution/display stack; documented platform differences are intentional and accepted.
- Verify: signed checklist, screenshots, logs, artifact checksum; no unresolved integrity/security blocker.

### [ ] DV-1103 Produce requirement traceability and documentation truth audit

- Depends: DV-1101, DV-1102.
- Scope: Product FR/NFR to task/test/platform evidence table; README/CHANGELOG/Release/Test Report updates; link/conflict scan.
- Acceptance: every requirement traced; no target feature described as current unless implemented; limitations accurate; commands/results current; all local links valid; no duplicate authoritative backlog/spec.
- Verify: independent reviewer checks traceability samples and repository scans.

### [ ] DV-1104 Publish Data Viewer v1

- Depends: DV-1103 and every earlier v1-gate task.
- Acceptance: canonical version/tag; both artifacts, checksums, SBOM/licenses, release notes, known limitations, evidence links published; post-download hash/launch/open/close smoke passes; rollback instructions retained.
- Verify: release URL/artifact hashes/post-release smoke recorded in `TEST_REPORT.md`; update `CHANGELOG.md` from Unreleased to version/date.

---

## Post-v1 backlog (not release scope)

These items require new product decisions and must not be implemented inside v1 tasks:

- third-party plugin installation, signing, permissions, sandbox/process isolation, marketplace;
- Parquet and Arrow IPC/Feather;
- DICOM series/PACS, NRRD/MHA/MHD, TIFF/OME-TIFF, FITS, SQLite;
- EEG/MEG formats;
- safe JSON/YAML/XLSX/MAT/NIfTI source editing;
- NetCDF and Zarr reconsideration;
- macOS packaging;
- remote sources, collaboration, telemetry, or cloud accounts.
