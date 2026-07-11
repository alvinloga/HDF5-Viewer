# UI/UX Specification

## 1. Design intent

Data Viewer is a professional, quiet, high-density scientific desktop workbench. It is inspired by modern IDE information architecture and Fluent 2 clarity while remaining native PyQt6. It is not a web dashboard and must not mimic an official Fluent component library.

Taste settings:

- design variance: 4/10 — stable grid with limited asymmetry around the primary data surface;
- motion intensity: 2/10 — restrained state transitions only;
- visual density: 8/10 — compact professional controls, hierarchy through spacing and dividers rather than card stacks.

## 2. Experience principles

1. Data is the visual focus; chrome recedes.
2. Every operation states its target, scope, and mode.
3. The user can inspect metadata before loading expensive payloads.
4. Long work is visible, cancellable, and does not freeze navigation.
5. Read-only, dirty, conflicted, sampled, stale, and error states are unmistakable without color alone.
6. Common actions are available by mouse and keyboard in at most two interactions after the target is selected.
7. Views never disguise conversions, flattening, sampling, or loss of provenance.

## 3. Application shell

```text
┌──────────────────────────────── Command bar ────────────────────────────────┐
│ Open  Workspace  Save  Export │ breadcrumbs │ search / command palette     │
├───────┬───────────────────────┬───────────────────────────────┬─────────────┤
│       │ Files / Structure     │ tabs + split data workspace   │ Inspector   │
│ Nav   │                       │                               │ Overview    │
│ rail  │ hierarchical browser  │ table / text / image / plots │ Attributes  │
│       │ favorites / search    │ compare / plugin results      │ Statistics  │
│       │                       │                               │ Plugins     │
├───────┴───────────────────────┴───────────────────────────────┴─────────────┤
│ Tasks / Output / Problems                                                    │
├──────────────────────────────── Status bar ──────────────────────────────────┤
│ source • mode • shape/dtype • slice/scope • task state • coordinates         │
└───────────────────────────────────────────────────────────────────────────────┘
```

Panel defaults: left 280 px, inspector 320 px, bottom 220 px. Panels are resizable, collapsible, and persist semantic state. At 1024×768, the inspector collapses before the data workspace becomes unusable. There is no fixed-width layout assumption.

## 4. Navigation model

- Navigation rail switches Files, Structure, Search, Favorites, Plugins, and Workspaces.
- A single structure tree is authoritative; duplicate tree controls are forbidden.
- One click selects and shows metadata; Enter/double click opens the primary view.
- Tabs belong to split groups. The active split has both a border/focus indicator and accessible label.
- Commands resolve against an explicit `ActiveContext`: active view, selected resource, selection, dirty state, and task state.
- Breadcrumb segments are interactive and keyboard reachable.
- Back/forward navigate resource/view history, not arbitrary widget focus.

## 5. Design tokens

Tokens live in one module and expose light/dark semantic roles. Components never hard-code palette values.

### Spacing and geometry

- base unit: 4 px;
- spacing: 4, 8, 12, 16, 24, 32 px;
- compact control height: 28 px; standard: 32 px; prominent: 36 px;
- row height: 26–30 px based on platform font metrics;
- radius: 4 px controls, 6 px independent surfaces;
- dividers: 1 physical pixel when device ratio permits;
- no glassmorphism, outer glow, oversized shadow, pill-shaped general controls, or nested card grids.

### Typography

- UI: platform-native sans serif through Qt font roles;
- numeric/path/code: platform-appropriate monospace;
- hierarchy derives from weight, size, and spacing, not all-caps decoration;
- minimum ordinary text target: 12 CSS-equivalent px at 100%, respecting OS scaling;
- tabular numbers align by decimal where practical.

### Color roles

Required roles: canvas, surface, raised surface, input, hover, pressed, selected, border, strong border, primary text, secondary text, disabled text, accent, focus, success, warning, error, info, dirty, read-only, comparison A/B.

Accent is blue-cyan and used for selection/focus/primary actions. Success, warning, and error colors express their real meanings only. All semantic states also use icon/text/shape.

## 6. Icons and motion

- Use one coherent monochrome SVG icon set with 16/20/24 px grids.
- Emoji, miscellaneous Unicode glyphs, and text pretending to be icons are forbidden.
- Icons include accessible names when not paired with visible text.
- Motion duration: 80–160 ms for hover/press/panel transitions; progress may animate continuously.
- No decorative entrance animations, bounce, parallax, or animated scientific data by default.
- Respect reduced-motion settings where available.

## 7. Core view behavior

### Tables and arrays

- Virtualized rows/columns; no widget per cell.
- Frozen row/column headers remain outside the source data.
- A visible slice expression always accompanies high-dimensional data.
- Copy/export dialogs state coordinates and scope.
- Edited cells show a dirty marker, original value access, validation state, and undo.
- Loading placeholders preserve header/layout and do not display fake data.

### Text

- Line numbers are presentation metadata.
- Encoding, line ending, size, and truncation/preview status are visible.
- Large text uses paged/streamed access and a clear partial-view banner.

### Images and volumes

- Image pixels are not distorted to fit; aspect is preserved.
- Zoom percentage, interpolation mode, value under cursor, and source coordinates are visible.
- NIfTI orthogonal views label anatomical/axis orientation, voxel and world coordinates, volume/time index, window/level, and raw/scaled values.
- Crosshairs and linked navigation are keyboard operable and may be hidden.

### Comparison

- Left/right identity and alignment mode remain visible.
- Synchronized navigation can be toggled.
- Differences use legends, values, and patterns; never red/green alone.
- Incompatible resources show actionable reasons before running computation.

### Plugin results

- Full plots open in workspace tabs, not narrow sidebars.
- Inspector shows provenance, parameters, warnings, and scope.
- Sampled or stale results have persistent labeled badges.

## 8. Standard states

Every async content surface implements:

| State | Required presentation |
|---|---|
| initial | short purpose and primary next action |
| loading | resource name, phase, progress if known, Cancel |
| empty | what is empty, why it may be valid, relevant action |
| ready | content plus scope/provenance |
| partial | explicit bounded/preview banner and Load/Refine action |
| error | concise cause, affected target, Retry/Details/remediation |
| disabled | visible reason in tooltip/status help |
| dirty | label/icon plus changed count and review access |
| read-only | label and Save As/export alternative |
| conflicted | blocking banner and safe choices |
| stale | cause and recompute/reload action |

Raw tracebacks appear only in Diagnostics/Output details.

## 9. Dialog rules

- File open is non-destructive and should not require confirmation.
- Import options use preview-first nonmodal or sheet-like flow.
- Save summary is modal because it authorizes disk mutation.
- Destructive confirmations name the resource and consequence; no generic “Are you sure?”.
- Validation occurs inline; Enter does not submit an invalid or destructive default unexpectedly.
- Long paths are selectable and middle-elided while preserving filename.

## 10. Command and shortcut baseline

| Command | Shortcut |
|---|---|
| Open file | Ctrl+O |
| Open workspace | Ctrl+Shift+O |
| Save document | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Export | Ctrl+E |
| Close view | Ctrl+W |
| Command palette | Ctrl+Shift+P |
| Find in current context | Ctrl+F |
| Global resource search | Ctrl+Shift+F |
| Split view | Ctrl+\\ |
| Toggle bottom panel | Ctrl+J |
| Undo/redo | Ctrl+Z / Ctrl+Shift+Z |

On Linux, conflicting desktop shortcuts may have an alternate mapping. Shortcut text comes from the command registry, not duplicated labels.

## 11. Accessibility

- Full keyboard traversal with visible focus.
- Logical tab order and no focus traps.
- Accessible names/roles/values for custom views, icons, progress, tables, and plots.
- Minimum WCAG 2.2 AA contrast target for text and essential non-text indicators.
- Screen-reader summaries for plots include title, axes, series, range, warnings, and exportable data table.
- Selection, errors, comparison sides, and dirty state do not rely on hue.
- UI remains usable at 200% OS scaling and with enlarged fonts.

## 12. Localization and content

- All user-visible strings use centralized translation resources.
- English is the source locale; Simplified Chinese ships in v1.
- Paths, dtypes, plugin IDs, and formulas are not translated.
- Messages use: what happened, affected target, safe next action.
- Avoid anthropomorphic, celebratory, or vague copy in scientific workflows.

## 13. Visual acceptance matrix

Capture and review deterministic screenshots for both platforms at:

- Windows: 100%, 150%, 200% scaling;
- Linux: 100%, 200% scaling under the supported Qt platform;
- 1024×768 minimum, 1440×900 typical, 2560×1440 large;
- light and dark themes;
- empty, loading, large tree, table, dirty edit, error, comparison, plot, NIfTI, tasks, and degraded workspace states.

Acceptance requires no clipped primary actions, overlapping text, inaccessible focus, unreadable contrast, emoji icons, detached popup positioning, or theme-specific hard-coded colors.
