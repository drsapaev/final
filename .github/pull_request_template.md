<!--
Before requesting review:
- Run the local gate when you can: `python scripts/run_pr_review_gate_checks.py --body-file <path-to-this-pr-body.md>`.
- Use examples from `docs/runbooks/PR_REVIEW_SAMPLE_BODIES.md`.
- Replace irrelevant sections with `not applicable - <short reason>`.
- Keep proof narrow: targeted test, smoke, diff inspection, or explicit not-checked note.
-->

## Summary

Describe the change in 2-4 bullets.

## Cyclic Execution Evidence

- Fresh main sync:
- Clean workspace:
- Branch:
- Scope gate:
- Red-check handling:

See `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` for the Evidence-Based Small PR Protocol.

## Contract Impact

- Canonical surface:
- Request shape:
- Response shape:
- Status codes:
- Frontend consumer:
- Compatibility path or alias:
- Contract proof:

If no API, websocket, event, or frontend consumer contract changed, replace this section with `not applicable - <short reason>`.

## RBAC / Permissions

- Roles allowed:
- Roles denied:
- Positive auth proof:
- Negative auth proof:

If no route, endpoint, guard, role helper, or auth-sensitive behavior changed, replace this section with `not applicable - <short reason>`.

## Notification / Realtime

- Event type or websocket channel:
- Payload version / ack behavior:
- Read/unread or delivery semantics:
- Reconnect/resync proof:

If no notification, websocket, chat, or realtime behavior changed, replace this section with `not applicable - <short reason>`.

## Frontend Resilience

- Empty data proof:
- Partial data proof:
- Forbidden secondary path behavior:
- Missing draft/resource behavior:
- Stale route/deep-link behavior:

If no user-facing panel or frontend data flow changed, replace this section with `not applicable - <short reason>`.

## Scope Gate

- Allowed paths:
- Denied paths:
- Migration/docs/test impact:
- Rollback note:

## DevBrain Memory Impact

- [ ] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

Per `docs/AGENTS_UI.md` §13 (two-tier gate). Tier 1 is blocking for every UI PR; Tier 2 requires backend infrastructure and may be explicitly deferred.

### Tier 1 — blocking (must all be green before merge)

- [ ] `npm run test` (Vitest unit)
- [ ] `npm run type-check` (tsc strict)
- [ ] `npm run lint:check` (ESLint + jsx-a11y)
- [ ] `npm run check-theme` (token compliance)
- [ ] `npm run audit:icon-controls` (a11y)
- [ ] `npm run build`
- [ ] Self-contained Playwright suite (48 tests / 6 specs, chromium; dev server only, no backend/credentials)

### Tier 2 — backend-dependent E2E

- Status (pick one): [ ] RUN — all passed / [ ] RUN — partial (list failures below) / [ ] NOT RUN
- If NOT RUN — reason:
- If NOT RUN — skipped specs:
- If NOT RUN — deferral acknowledged by reviewer: [ ]

### Snapshot updates (if any visual baseline changed)

- Snapshot files updated in this PR:
- Intentional visual delta explanation:
- Causality proof (A/B or pixel-diff): [ ] provided

Do not use "all green" / "safe to merge" / "fully verified" wording when Tier 2 is deferred. Correct form: "Tier 1 PASS; Tier 2 NOT RUN — <reason>".

See `docs/runbooks/PR_REVIEW_QUALITY_GATES.md` for the review checklist behind this template.
