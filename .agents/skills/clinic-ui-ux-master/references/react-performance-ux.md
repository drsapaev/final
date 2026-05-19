# React Performance UX

Use this reference when performance, responsiveness, slow interactions, re-render churn, or bundle drift affects frontend UX.

## Principle

Performance is a clinical usability feature. Slow role panels, delayed input, and heavy route bundles make staff workflows less reliable.

## Audit Order

1. Identify route, role, and high-frequency interaction.
2. Locate component tree and data fetching path.
3. Check expensive render sources.
4. Check effect dependencies and derived state.
5. Check list/table rendering.
6. Check bundle-heavy imports.
7. Check event handlers and layout work.
8. Validate with profiler, browser trace, test, or build output when available.

## Render Churn

Look for:

- state kept too high in the tree
- entire role panel re-rendering for local form changes
- derived values stored in state through effects
- object/array/function props recreated in hot paths
- inline component definitions inside render
- context providers causing broad updates
- large tables rerendering all rows for one row change

Prefer:

- local state near the interaction
- derived values during render when cheap
- memoization only where it prevents real repeated work
- stable callbacks when passed to many children
- splitting large role panels by workflow section

Do not add memo everywhere. Require a plausible reason or measurement.

## Effects

Check:

- unnecessary effects that only derive state
- effects with broad object dependencies
- missing cleanup for subscriptions/timers
- repeated fetches caused by unstable dependencies
- polling that continues when route/section is not visible
- state updates after unmount

Prefer:

- event handlers for interaction logic
- primitive dependencies
- cleanup functions
- shared hooks already used by the project
- cached or deduplicated API access when existing helpers support it

## Bundle And Imports

Look for:

- barrel imports from large libraries
- importing heavy chart/editor/AI modules before the feature opens
- MUI imports on routes moving to canonical UI
- duplicate icon libraries on the same route
- large demo or example modules in production paths

Prefer:

- direct imports where project convention allows
- lazy loading for heavy optional panels
- route-level splitting when already used by the app
- one icon system per active surface

Do not change bundling strategy as part of a small visual patch unless the task is performance-specific.

## Lists And Tables

Check:

- stable row keys
- no expensive filtering/sorting on every keystroke without need
- no full table recomputation for unrelated UI state
- pagination, virtualization, or server filtering where data volume is large
- action column stays responsive

For clinic tables, prioritize reliable row identity and action clarity over micro-optimizations.

## Interaction Responsiveness

High-risk interactions:

- patient search
- appointment create/reschedule
- queue join/refresh
- payment submit/status refresh
- lab report generate/print
- EMR section navigation

Check:

- input typing does not lag
- loading states appear quickly
- long operations do not block navigation
- disabled state prevents double submit
- optimistic state is not misleading

## Static Searches

Use:

```powershell
rg -n "useEffect\\(|useMemo\\(|useCallback\\(|React\\.memo|memo\\(" frontend/src
rg -n "from 'lucide-react'|from \"lucide-react\"|@mui/" frontend/src
rg -n "\\.map\\(|\\.filter\\(|\\.sort\\(" frontend/src/pages frontend/src/components
```

Review results selectively. A pattern is not a bug without workflow impact.

## Validation

Choose one or more:

- `npm run build` to catch bundle/build regressions
- targeted Vitest for logic changes
- browser route smoke for visible responsiveness
- React profiler when available
- performance trace for slow route or interaction
- before/after static inventory for imports or inline work

## Stop Conditions

Stop and split if:

- optimization changes API timing or behavior
- route state becomes hard to reason about
- memoization obscures correctness
- bundle changes affect many routes
- performance proof is unavailable and risk is high
