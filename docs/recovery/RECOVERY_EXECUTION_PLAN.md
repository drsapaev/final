# Recovery Execution Plan

## Stage A - Analysis Output Freeze
- Completed in this audit pass.
- No merge/cherry-pick/rebase/reset/delete-branch was performed.
- The six recovery markdown artifacts are the output of this stage.

## Stage B - Safe Recovery Workspace
- Keep recovery work isolated from `main`.
- If implementation work starts later, do it in a dedicated worktree or branch off current `main`.
- Do not rewrite history or move `main` until the recovery plan is approved.

## Stage C - Lowest-Risk Recover Now
1. `dependabot/github_actions/actions/checkout-6`
2. `dependabot/github_actions/actions/setup-node-6`
3. `dependabot/github_actions/actions/setup-python-6`
4. `origin/dependabot/github_actions/actions/upload-artifact-7`
5. `origin/dependabot/github_actions/docker/build-push-action-7`
6. `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19`
7. `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136`
8. `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13`
9. `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43`
10. `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0`

Gating rule for Stage C:
- Recover one ref at a time.
- Validate immediately after each ref.
- Stop and reclassify if any conflict or regression appears.

## Stage D - Manual Ports / Reimplementations
- Start with only one narrow slice from each stale family.
- Prefer current `main` as the base, not the historical branch tip.
- Good candidates for later manual porting are the notification-adapter precursor, the w2a service/repository ideas, and the queue parity harnesses.

## Stage E - Regression Validation
- Targeted backend pytest for any backend change.
- Targeted frontend vitest for any component or hook change.
- `npm run build` for frontend runtime changes.
- Browser smoke for the affected role or panel.
- `git diff --check` before any commit.

## Stage F - Docs Reconciliation
- Update `docs/QUEUE_SYSTEM_ARCHITECTURE.md`.
- Archive `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` and the older queue implementation/fix reports.
- Keep the runbooks and evidence logs current.

## Executive Table
| Bucket | Meaning | Current contents |
|---|---|---|
| Recover now | Small isolated maintenance that can be safely applied | Current dependabot refs only, if dependency hygiene is still in scope |
| Reimplement later | Valuable idea, stale branch | w2a, w2c, post-w2c, wip-jules, notifications precursor |
| Drop forever | Obsolete / unsafe / binary snapshot | `123`, `feat/macos-ui-refactor` |
| Docs only | Evidence or stale architecture notes | `codex/startup-operator-first-hardening`, `origin/codex/post-w2c-next-legacy-slice-review`, stale queue/notification architecture docs |

## Safest Next Step
- Keep this pass analysis-only.
- If implementation is approved later, begin with the dependency refs in Stage C, then stop and re-check after each one before touching any wave branch.
