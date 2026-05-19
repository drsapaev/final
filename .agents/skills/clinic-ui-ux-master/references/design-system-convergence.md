# Design-System Convergence

Use this reference when reducing mixed UI layers, inline styles, legacy classes, MUI drift, or duplicated tokens.

## Goal

Move active clinic surfaces toward the canonical project UI layer without a broad rewrite. Preserve workflow behavior, route semantics, data flow, and tests.

## Inventory First

Collect a small inventory before editing:

- current file and route
- imported UI layers
- `style={{` count in the touched file
- `legacy-` classes in the touched file
- `@mui/` imports in the touched file
- hardcoded colors, spacing, radius, shadows, z-index
- repeated local style objects
- existing tests or nearby examples

Useful searches:

```powershell
rg -n "style=\{\{" frontend/src
rg -n "legacy-" frontend/src
rg -n "@mui/" frontend/src
rg -n "#[0-9a-fA-F]{3,8}|rgb\(|rgba\(" frontend/src
```

## Canonical Preference

Prefer:

- existing clinic/macOS components under the current project UI layer
- existing CSS variables and tokens
- existing route registry metadata
- existing hook and state patterns
- component props already used by neighboring screens

Avoid:

- creating a new `ui2`, `new-ui`, `modern`, or parallel component namespace
- copying a component to make a one-off variant
- introducing new global tokens before checking existing ones
- mixing MUI and canonical components in the same new slice unless migration is staged

## Inline Style Reduction

Do not remove all inline styles in one pass. Use this order:

1. Extract repeated constants only inside the same file if the surface is still unstable.
2. Replace repeated layout shells with existing layout components or CSS classes.
3. Move stable repeated patterns to the canonical component layer only when at least two active screens need them.
4. Leave one-off dynamic styles inline when they are truly data-driven and readable.

Good first targets:

- repeated icon sizes
- repeated toolbar flex layouts
- repeated card padding and grid columns
- repeated status badge colors
- repeated empty/loading/error shell styles

Stop when:

- the patch changes behavior
- the patch touches too many role flows
- tests or route smoke become ambiguous
- you need a new abstraction that is not clearly reused

## Legacy Class Migration

For `legacy-*` classes:

1. Identify the active route and owner.
2. Replace page shell, toolbar, input, button, table, and muted/error states one group at a time.
3. Keep labels and data semantics unchanged.
4. Validate responsive behavior after replacing toolbar or table wrappers.

Prioritize legacy migration on active operational routes over historical/demo pages.

## MUI Drift

MUI may exist as legacy compatibility. Do not remove MUI from shared theme/provider code casually.

For active screens:

- do not introduce new MUI imports
- replace MUI screen-level cards, buttons, alerts, tables, and menus only when a canonical equivalent exists
- keep complex menus/dialogs if replacement would be a behavioral rewrite
- treat MUI cleanup as its own small PR when it touches interactions

## Token Rules

Use existing CSS variables and design tokens for:

- text colors
- surfaces
- borders
- focus rings
- spacing
- status colors
- shadows and elevation

Do not hardcode status colors in role screens unless the token is missing and the patch explicitly documents that gap.

## Component API Rules

Good component changes:

- remove duplicated markup
- reduce repeated style blocks
- improve accessibility or state handling
- match existing variants
- keep props simple

Bad component changes:

- boolean-prop explosion
- role-specific logic inside generic UI
- data fetching in visual primitives
- backend-specific terms inside shared components

## Suggested Slice Order

1. Inventory and report.
2. One active route: replace legacy shell/toolbar/table.
3. One high-traffic role panel: reduce repeated layout styles.
4. One state system: empty/loading/error consistency.
5. One component primitive: extract only after repeated usage is proven.
6. Browser QA and screenshots.

