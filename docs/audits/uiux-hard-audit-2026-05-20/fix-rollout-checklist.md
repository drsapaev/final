# UI/UX Hard Audit Fix Rollout Checklist

This checklist tracks the small-PR rollout for the `2026-05-20` hard UI/UX audit.

Rules:

- Mark a step complete only after its PR is merged into `main`.
- Keep each PR limited to one route, role, or state family.
- Use `clinic-frontend-design` / `clinic-ui-ux-master` as the UI/UX guard for frontend fixes.
- Preserve backend/API/RBAC/payment/queue/EMR/lab behavior unless a later plan explicitly scopes a contract change.
- Record validation evidence in each PR body.

## Rollout Status

- [x] PR-0: audit baseline and rollout checklist merged.
- [x] PR-UX-1: payment cancel semantic status merged.
- [x] PR-UX-2: queue join recovery states merged.
- [x] PR-UX-3: authenticated UI QA harness merged.
- [x] PR-UX-4: cashier payment accessibility merged.
- [x] PR-UX-5: doctor current patient workflow merged.
- [x] PR-UX-6: admin support legacy cleanup merged.
- [x] PR-UX-7: AdminPanel design-system slice merged.
- [ ] PR-UX-8A: cardiology specialty slice merged.
- [ ] PR-UX-8B: dermatology specialty slice merged.
- [ ] PR-UX-8C: dentistry specialty slice merged.
- [ ] PR-UX-9: MUI island policy and inventory merged.
- [ ] Final: rollout completion summary merged.

## Current Defaults

- Rollout mode: small PRs only.
- Failure policy: fix the current PR, then continue.
- Auth QA policy: add a safe authenticated UI QA harness before certifying protected role panels.

## Validation Baseline

- [ ] `git diff --check`
- [ ] docs-only diff for PR-0
- [ ] frontend lint/build for frontend code PRs
- [ ] targeted browser QA for changed UI routes
- [ ] GitHub Actions green before merge
