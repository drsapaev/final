---
name: clinic-frontend-design
description: Clinic-safe frontend UI/UX audit, planning, and improvement workflow for this medical management app. Use when working on Admin, Doctor, Registrar, Cashier, Lab, dashboard, form, table, route-view, empty/loading/error, accessibility, responsive, visual consistency, or design-system tasks in the clinic frontend.
---

# Clinic Frontend Design

Use this skill for clinic frontend UI/UX work where polish must not reduce clinical usability. This is an operations system for medical staff, not a marketing site.

## First Read

Before advising, planning, or editing, inspect the relevant current source and the smallest useful set of project rules:

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
  - Start with the `UI Layer Contract` section when deciding which UI layer to use.
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/src/routing/routeRegistry.js` when routes or panels are involved
- the specific role panel, component, hook, state, style, and test files for the requested screen
- `ARCHITECTURE_RULES.md` only if it exists

Prefer executable source and tests over broad historical docs when they disagree.

## Priorities

- Medical readability, speed, accessibility, predictable workflows, role clarity, and low cognitive load come before visual novelty.
- Reuse existing design tokens, CSS variables, components, routing, state, and macOS-style patterns.
- Keep Admin, Doctor, Registrar, Cashier, and Lab workflows distinct and easy to scan.
- Improve empty, loading, error, disabled, partial-data, and forbidden states when they are part of the touched workflow.
- Use small safe UI slices. Audit first when a flow affects auth, roles, routing, queue, payment, EMR, lab, or production-sensitive behavior.

## Avoid

- Do not apply a generic or unmodified `frontend-design` aesthetic.
- Do not make marketing/landing-page layouts for operational clinic screens.
- Do not add unusual fonts, aggressive motion, chaotic layouts, decorative complexity, gradient-orb decoration, or clever interactions that slow staff down.
- Do not create a parallel UI framework, duplicate design tokens, or one-off styling systems.
- Do not change backend contracts, route semantics, RBAC, queue behavior, payment behavior, EMR behavior, or lab behavior as part of a visual cleanup.

## Workflow

1. Identify the role, screen, workflow, user action, and risk level.
2. Inspect current implementation and design-system anchors before suggesting changes.
3. Diagnose concrete UI/UX issues: hierarchy, density, spacing, states, accessibility, responsiveness, workflow friction, and visual inconsistency.
4. Propose the smallest safe improvement slice using existing components/tokens first.
5. If implementing, touch only the approved UI slice and preserve existing contracts.
6. Validate with the narrowest relevant checks: frontend lint/test/build, role-specific tests, browser or Playwright smoke, and visual verification when available.

## Output

For audits or plans, include:

- UI/UX diagnosis
- files inspected
- safe design direction
- exact implementation slice
- validation commands
- risks and stop conditions

For implementation, include:

- changed files
- why the slice is safe
- validation run and result
- remaining risks
