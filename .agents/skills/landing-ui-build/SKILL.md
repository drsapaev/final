---
name: landing-ui-build
description: Implement a landing page in the current frontend stack using the established brief, strategy, and design tokens. Use when building or fixing the actual landing UI.
---

# Landing UI Build

Build or repair the landing using the current frontend conventions. The implementation should stay grounded in run artifacts, not re-invent the brief in code.

## Workflow

1. Read:
   - `briefs/landing_brief.json`
   - `design/tokens.json`
   - `design/layout-spec.json`
   - `content/landing-copy.md`
   - `plans/build_status.json`
2. Implement only the sections approved in strategy.
3. Preserve semantic HTML and explicit heading order.
4. Keep styling centralized through tokens or clear section-level variables.
5. Prepare the page for audits:
   - stable selectors for CTA and forms
   - accessible labels
   - responsive layout
   - optimized assets and lazy loading where appropriate
6. When the implementation is ready, update `plans/build_status.json`:
   - set `ui_status` to `implemented`
   - list the main `entry_files`
   - add a preview URL if one exists

## Done Criteria

- desktop and mobile layouts both render correctly
- headings, landmarks, and CTA hierarchy are explicit
- there is a clear place to attach analytics and test selectors
- build output is ready for Lighthouse and Playwright checks

## Guardrails

- do not bypass the design system to patch one-off visuals everywhere
- do not hide content in images
- avoid shipping animation that harms LCP or INP
