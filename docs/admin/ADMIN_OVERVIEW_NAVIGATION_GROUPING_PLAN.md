# Admin Overview Navigation Grouping Plan

Date: 2026-06-01
Mode: route grouping decision and implementation guide

This document records the intended direction for the overloaded Admin sidebar
`Overview` section. It exists so future agents do not move admin routes by
visual similarity or personal preference without preserving route ownership,
auth, browser behavior, and existing staff workflows.

## Original Audit State

The original admin deep audit found these routes in the same sidebar section:

| Route | Owner | Current role in UI | Grouping issue |
| --- | --- | --- | --- |
| `/admin` | `admin.operations` | Admin dashboard / operational overview | Correct high-level overview entry. |
| `/admin/analytics` | `admin.analytics` | Analytics dashboard | Fits overview, but is also a dedicated analytics surface. |
| `/admin/reports` | `admin.reports` | Reports and generated summaries | Fits high-level review, but can become a reporting workflow. |
| `/admin/system` | `admin.system` | System management/status | Operational tooling, not overview content. |
| `/admin/webhooks` | `admin.integrations` | Webhook tooling | Integration tooling, not overview content. |
| `/admin/cloud-printing` | `admin.operations` | Printing operations | Operational tooling, not overview content. |
| `/admin/medical-equipment` | `admin.operations` | Equipment operations | Operational tooling, not overview content. |
| `/admin/graphql-explorer` | `admin.integrations` | API/developer explorer | Integration/developer tooling, not overview content. |

The problem is not that these routes are broken. The problem is that the
sidebar label `Overview` currently mixes:

- summary views;
- operational tools;
- integration tools;
- developer/debugging tools.

That makes the AdminPanel feel broader than one section should be and gives
future agents weak ownership signals.

## Current Target Grouping

The accepted target grouping is:

| Target section | Routes | Boundary |
| --- | --- | --- |
| `Overview` | `/admin`, `/admin/analytics`, `/admin/reports` | Summary, trends, and review surfaces only. No deep tooling or CRUD ownership. |
| `Operations` | `/admin/system`, `/admin/cloud-printing`, `/admin/medical-equipment` | Operational tooling that admins use to keep the clinic running. |
| `Integrations` | `/admin/webhooks`, `/admin/graphql-explorer` | External/API/developer integration surfaces. |

`Management`, `System`, Telegram, notifications, files, finance, settings,
security, and audit remain unchanged until their own route-family PRs name the
owner and validation plan.

## Runtime Change Policy

A future runtime PR may move route `nav.section` values only if it also includes:

1. A route contract test that asserts the expected section for each moved route.
2. Browser smoke for every moved route as Admin.
3. Proof that active sidebar selection still matches the route.
4. Proof that no route path, owner, component, RBAC, or API contract changed.
5. Updated screenshots or browser notes for desktop and narrow tablet if the
   sidebar grouping materially changes navigation density.

Do not combine this grouping change with AdminPanel extraction, settings
consolidation, Telegram/notification route changes, or user-management route
aliasing. Those are separate risk families.

## Small PR Order

1. `test(admin): guard overview route sections`
   - Add contract tests for the current grouping decision.
2. `refactor(admin): regroup overview sidebar routes`
   - Change only `nav.section` and related route tests for the selected routes.
   - Browser-smoke each moved route.
3. `docs(admin): record overview regrouping evidence`
   - Update audit status after the runtime PR is merged green.

## Stop Conditions

Stop and re-plan instead of editing the route registry if:

- any moved route has a 4xx/5xx browser load failure;
- Admin auth fails for a moved route;
- a route's visible heading no longer matches its route purpose;
- a proposed move changes route paths, component ownership, RBAC, or API calls;
- the change starts to pull in AdminPanel extraction or unrelated UI cleanup.
