# Implementation Slices

Use this reference when turning UI/UX findings into safe patches or PRs.

## Slice Principles

- One role, route, component family, or state family per patch.
- Preserve runtime behavior unless the task explicitly includes behavior.
- Prefer source-compatible improvements over visual rewrites.
- Keep validation proportional to risk.
- Stop before expanding into unrelated cleanup.

## Safe Patch Types

### Visual State Patch

Scope:

- empty, loading, error, disabled, forbidden, success, warning, pending

Good for:

- payment status
- queue state
- lab report generation
- appointment forms

Validation:

- targeted test if state has coverage
- route/browser smoke
- screenshot when visible

### Legacy Surface Migration

Scope:

- one active page using `legacy-*` classes
- shell, toolbar, table, inputs, buttons

Validation:

- static search for remaining legacy classes in touched file
- browser check at mobile/tablet/desktop
- no API/data changes

### Inline Style Reduction

Scope:

- repeated style groups in one file
- replace with existing tokens/classes/components

Validation:

- count before/after if useful
- build or targeted test
- screenshot if layout changed

### Component Consistency Patch

Scope:

- one component primitive or repeated local pattern

Validation:

- affected screens only
- story/demo if present
- targeted tests

### Accessibility Patch

Scope:

- labels, focus, keyboard path, ARIA association, table headers, modal semantics

Validation:

- keyboard smoke
- targeted accessibility test if available
- browser check

## Unsafe Patch Signs

Pause or split when:

- route semantics change
- role permissions change
- queue/payment/EMR/lab state logic changes
- backend contract changes
- a new component API needs many boolean props
- patch spans many role panels
- test failure cause is unclear
- a visual cleanup requires data-model changes

## Suggested PR Boundaries

Good PR:

- `ui: audit legacy scheduler table`
- `ui: align payment cancel state`
- `ui: reduce admin panel stat card drift`
- `ui: improve queue join mobile form`
- `ui: add accessible labels to cashier payment actions`

Too broad:

- `redesign frontend`
- `modernize all panels`
- `replace MUI everywhere`
- `clean all inline styles`
- `new design system`

## Validation Matrix

For docs/skill-only:

- metadata/frontmatter check
- no app files changed
- `git diff --check`

For one visible component:

- lint or targeted unit test
- browser smoke for route using component

For role route:

- route smoke
- mobile/tablet/desktop visual check
- targeted tests if present
- build if shared imports changed

For shared UI primitive:

- tests for primitive if present
- build
- at least two consuming routes checked if practical

## Commit Summary Template

Use:

```text
ui: improve <role/surface> <specific issue>
```

Examples:

```text
ui: align registrar schedule toolbar states
ui: improve queue join mobile form layout
ui: reduce admin panel card style drift
```

## Final Report Template

Include:

- changed files
- user-facing behavior preserved
- visual/UX improvement
- validation run
- not changed
- next smallest slice
