# Runtime Performance QA

Use this reference for live UX performance checks: Core Web Vitals, layout shift, network chains, route load time, browser trace, and Lighthouse-style review.

## Principle

Do not optimize abstract scores before critical workflows. Measure the route and interaction the staff or patient actually uses.

## Targets To Watch

Use current documentation or tooling for exact thresholds when reporting formal numbers. For project work, focus on:

- route load delay
- input responsiveness
- layout shift
- long tasks
- unnecessary network chains
- render-blocking assets
- console/runtime errors
- repeated polling or duplicate requests

## Workflow

1. Pick route and role.
2. Define the user action: load dashboard, search patient, join queue, submit payment, generate report.
3. Open route in browser tooling.
4. Capture baseline: console, network, screenshot, performance trace if available.
5. Identify high-impact bottleneck.
6. Patch the smallest source issue.
7. Re-run the same route/action.
8. Report before/after evidence or state limitation.

## Core Web Vitals Lens

Use this lens without overfitting:

- LCP-like issue: main content takes too long to appear.
- INP-like issue: clicks/typing feel delayed or blocked.
- CLS-like issue: content shifts while staff is trying to act.

Clinic examples:

- queue join form shifts when queue status loads
- admin dashboard cards jump after metrics arrive
- appointment table blocks typing while filtering
- payment result shows placeholder then shifts status/action layout

## Network

Check:

- duplicate API calls on mount
- waterfall requests that could be parallel
- failed requests hidden by generic UI
- polling that runs on inactive sections
- large response consumed by a small widget
- static assets or demo code loaded on active clinical routes

Do not change backend contracts in a UI performance patch.

## Layout Shift

Check:

- images/icons without stable dimensions
- skeletons smaller than loaded content
- late banners/alerts pushing critical controls
- table columns resizing after data loads
- sidebars appearing after main content
- font or theme loading causing visible jump

Fix with:

- stable dimensions
- skeletons that match final layout
- reserved alert/status space where appropriate
- predictable grid/table columns

## Long Tasks And Heavy UI

Look for:

- large synchronous filtering/sorting
- formatting dates/amounts repeatedly in large tables
- rendering hidden tabs
- heavy charting/AI components loaded by default
- broad context updates

Prefer:

- split panels
- lazy optional modules
- memoized expensive transforms where justified
- pagination or virtualization for big tables
- existing project hooks and helpers

## Lighthouse/Trace Report Fields

When using browser performance tooling, report:

- route and role
- device or viewport
- throttling mode if any
- main issue category
- source candidate
- before/after observation
- confidence level

## Validation

Useful checks:

- browser screenshot before/after
- console/network review
- trace summary
- build output
- route smoke
- targeted test for changed logic

Avoid claiming quantified improvement unless measured.
