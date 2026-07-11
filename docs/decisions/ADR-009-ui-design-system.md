# ADR-009: Native High-Density Qt Design System

- Status: Accepted
- Date: 2026-07-11

## Context

The current UI has a useful IDE-like shell but inconsistent colors, icons, panel responsibilities, states, and focus. A scientific workbench needs dense information, legible provenance, and cross-platform accessibility without becoming a generic card dashboard.

## Decision

Use a native PyQt6 design system inspired by modern IDEs and Fluent 2 clarity: semantic light/dark tokens, 4 px spacing scale, compact controls, small radii, monochrome SVG icons, single authoritative navigation structures, explicit active split/context, and full async/dirty/read-only/error states.

Taste settings are variance 4, motion 2, density 8. Data surfaces dominate; full plots live in tabs. Emoji/Unicode pseudo-icons, scattered hard-coded colors, glass effects, oversized shadows, and card nesting are prohibited.

## Alternatives

- Embed a web frontend: rejected because it adds runtime/interaction complexity and abandons current PyQt investment.
- Adopt a pixel clone of an official design library: rejected because native Qt/platform behavior and scientific density matter more.
- Cosmetic stylesheet-only refresh: rejected because information architecture, state, focus, and accessibility are structural issues.
- Maximal custom painting: rejected due to accessibility and maintenance cost.

## Consequences

- Tokens/components/states precede broad screen restyling.
- Visual acceptance spans themes, DPI, sizes, states, and platforms.
- Custom data views require accessible roles/summaries.
- Existing useful shell concepts can remain while duplicate navigation and sidebar plots are removed.

## Related documents

`docs/UI_UX_SPEC.md`, `ARCHITECTURE.md`.
