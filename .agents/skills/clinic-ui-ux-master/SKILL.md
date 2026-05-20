---
name: clinic-ui-ux-master
description: Project-specific master UI/UX skill for this clinic management frontend. Use for UI/UX audits, visual consistency, design-system convergence, role panels, dashboards, forms, tables, navigation, route views, empty/loading/error/forbidden states, accessibility, responsive behavior, browser visual QA, and safe frontend UI improvements across Admin, Doctor, Registrar, Cashier, Lab, Patient, queue, payment, EMR, and reporting workflows.
---

# Clinic UI/UX Master

Use this skill when the task is bigger than a one-off style tweak: mixed UI/UX, visual audit, design-system cleanup, role workflow polish, responsive/a11y review, or a UI implementation slice in the clinic frontend.

This is a medical operations system. Treat clarity, speed, role safety, and predictable staff workflows as the design language.

## Source Synthesis

This skill combines the useful parts of five external UI/UX skill styles, adapted for this project:

- From `frontend-design`: commit to an intentional visual direction and avoid generic AI-looking UI. In this project, "distinctive" means calm clinical hierarchy, not marketing spectacle.
- From `impeccable`: run context gates, form a shape brief before editing, and make deliberate craft decisions instead of opportunistic styling.
- From `web-design-reviewer`: inspect the running UI when possible, capture screenshots, test multiple viewports, fix source code minimally, and re-verify.
- From `design-audit`: separate audit from implementation, use a reduction filter, organize findings into phases, and do not touch functionality during visual work.
- From `ui-ux-pro-max`: apply a broad rule matrix for accessibility, responsive layout, touch targets, performance, forms, tables, charts, states, typography, color, spacing, and interaction quality.

The project-specific rule wins whenever generic design advice conflicts with clinical usability or existing architecture.

## Reference Loading

Load only the reference needed for the current task:

- `references/source-synthesis.md`: when choosing which external-skill behavior to apply.
- `references/audit-matrix.md`: for detailed P0-P3 audits, checklists, and scoring.
- `references/role-workflows.md`: for role-specific Admin, Doctor, Registrar, Cashier, Lab, Patient, queue, payment, EMR, and reporting work.
- `references/design-system-convergence.md`: for inline-style, legacy-class, MUI, token, or component-layer cleanup.
- `references/visual-qa-playbook.md`: for browser screenshots, viewport checks, console/network review, and re-verification.
- `references/accessibility-hardening.md`: for WCAG, keyboard, focus, screen-reader, reduced-motion, and touch target reviews.
- `references/react-performance-ux.md`: for React render, bundle, effects, state, and interaction performance that affects UX.
- `references/runtime-performance-qa.md`: for Core Web Vitals, layout shift, network chains, Lighthouse/browser trace, and runtime UX checks.
- `references/design-token-inventory.md`: for CSS/token extraction, palette/typography/spacing inventory, hardcoded value cleanup, and design-system evidence.
- `references/implementation-slices.md`: for safe patch sizing, PR boundaries, validation, and stop conditions.
- `references/anti-patterns.md`: for clinical UI mistakes to actively avoid.
- `references/report-templates.md`: for audit, implementation, and visual QA report formats.

## Context Gate

Before advising, planning, or editing, inspect the smallest relevant set:

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
  - Start with `UI Layer Contract`.
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/src/routing/routeRegistry.js` for route, panel, role, shell, or nav work
- relevant role panel/page/component/style/hook/test files
- `ARCHITECTURE_RULES.md` only if it exists

Prefer executable source and tests over historical reports. If a required anchor is missing, say so and continue with source evidence.

## Operating Modes

- `audit-only`: inspect and report. Do not edit files.
- `safe-patch`: one screen, component, state, or narrow styling slice.
- `system-convergence`: move a small surface from inline styles, legacy classes, or MUI drift toward the canonical UI layer.
- `visual-qa`: run or inspect the app, capture screenshots, compare viewports, and report before/after.

Escalate before changing auth, RBAC, route semantics, queue behavior, payment behavior, EMR behavior, lab behavior, backend contracts, data models, or API calls.

## Shape Brief

Before substantial edits, write a short brief:

- user role and workflow
- primary user action
- risk level
- current UI layer and drift sources
- intended tone: quiet, fast, clinical, readable
- primary hierarchy decision
- out-of-scope behavior and contracts
- validation plan

Do not implement a large visual change without this brief.

## Audit Matrix

Evaluate the touched surface against:

- visual hierarchy: primary action, scan order, density, information grouping
- spacing and rhythm: consistent gaps, compact clinical layout, no crowded controls
- typography: clear size hierarchy, restrained weights, no ornamental fonts
- color: token-based, accessible contrast, status colors used consistently
- alignment and grid: stable columns, no off-by-one visual drift
- components: canonical macOS-style components first, consistent states
- iconography: one icon language, consistent stroke/size, icons only when meaningful
- interaction states: hover, focus, active, disabled, loading, error, empty, forbidden
- accessibility: keyboard path, focus visibility, labels, ARIA where needed, contrast
- responsiveness: 375, 768, 1280, and 1920px; no overflow, clipping, or overlap
- touch: mobile controls large enough for thumb use
- performance: no heavy decorative motion, avoid layout shift, avoid unnecessary bundles
- workflow safety: role clarity, no misleading status, no hidden critical action

## Reduction Filter

For every visible element ask:

- Can it be removed without losing meaning?
- Is visual weight proportional to workflow importance?
- Would a staff member need an explanation to find the next action?
- Does this duplicate another component, token, route, or state?
- Does this look like a parallel design system?

Remove, merge, or downgrade anything that fails these checks, unless clinical safety requires redundancy.

## Implementation Rules

- Use existing components, tokens, CSS variables, route/state patterns, and tests first.
- Prefer canonical clinic/macOS UI primitives for role dashboards, forms, tables, payment states, queue screens, and app shell work.
- Do not introduce a new design framework, duplicate token system, unusual font stack, decorative background system, or broad animation layer.
- Replace inline styles and legacy/MUI drift incrementally; do not rewrite whole role panels in one pass.
- Keep cards shallow. Do not put cards inside cards unless the existing design system requires it for a specific component.
- Use stable layout constraints: grid tracks, min/max widths, fixed control sizes, aspect ratios, and predictable wrapping.
- Treat tables and forms as operational tools: compact, scannable, keyboard-friendly, with clear empty/loading/error states.
- For charts and analytics, prioritize readable labels, legends, units, and state messaging over decoration.

## Priority Levels

- `P0`: visual issue blocks task completion, hides critical state, breaks layout, or risks clinical/payment/queue misunderstanding.
- `P1`: confusing hierarchy, inaccessible control, responsive failure, inconsistent critical state, or severe design-system drift.
- `P2`: spacing, typography, alignment, icon, color, or component inconsistency that degrades trust or speed.
- `P3`: polish, motion, subtle state refinement, or low-risk copy clarity.

Fix P0/P1 before P2/P3.

## Browser Visual QA

When the app is runnable and the task affects visible UI:

1. Open the relevant route.
2. Capture or inspect at mobile, tablet, desktop, and wide desktop where practical.
3. Check for overlap, clipping, overflow, lost focus state, broken empty/loading/error states, and console errors.
4. After changes, re-check the same route and viewport.

If browser tooling is unavailable, state that limitation and use static evidence plus existing tests.

## Validation

Choose the narrowest useful checks:

- static search for UI layer drift: inline `style={{`, `legacy-`, `@mui/`, hardcoded colors, duplicate tokens
- frontend lint or targeted test when available
- `npm run build` for broad UI slices
- role-specific tests, Vitest, Playwright, or browser smoke when the touched workflow has coverage
- screenshot or visual verification for layout/responsive fixes

Do not run backend suites for visual-only frontend changes unless a contract or route behavior changed.

## Output

For audits, return:

- scope and mode
- files and routes inspected
- current UI layer inventory
- P0/P1/P2/P3 findings with evidence
- phased fix plan
- validation plan
- stop conditions

For implementation, return:

- shape brief
- changed files
- what was intentionally not changed
- validation commands and results
- remaining risks and next smallest slice
