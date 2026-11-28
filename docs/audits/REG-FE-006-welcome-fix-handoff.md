# REG-FE-006 — Registrar Welcome confirmation handoff

**Status** The source fix is verified on #4099 and awaits an ordered merge into `main`. [Source PR](https://github.com/drsapaev/final/pull/4099)

## Verified source

- The published source commit `c3683e2cac654c09e42585e27b1c860cb10eae9c` sends Welcome's `in_cabinet` and `complete` actions through the shared confirmation callback. Its PowerShell gate completed on November 19, 2026 at 18:45:28 UTC with exit 0 and the documented narrow override. [Source commit](https://github.com/drsapaev/final/commit/c3683e2cac654c09e42585e27b1c860cb10eae9c) · [Gate evidence](https://github.com/drsapaev/final/pull/4099)
- Unified CI passed on that commit. The source PR records focused Vitest, TypeScript, Vite and synthetic Chromium evidence. [Unified CI](https://github.com/drsapaev/final/actions/runs/43808227462) · [Source validation](https://github.com/drsapaev/final/pull/4099)

## Original audit context

**Priority:** P2. **Scope:** Registrar Welcome page only; confirmation for `in_cabinet` and `complete`.
**Base:** `main` commit [`b93ea7117e2272d18c19fe1c4825695392c9b550`](https://github.com/drsapaev/final/commit/b93ea7117e2272d18c19fe1c4825695392c9b550), rechecked 2026-11-16; after previous main advanced, all four source/test blob SHAs below remained unchanged.
**Existing finding:** [2026-10-29 registrar frontend review ledger REG-FE-006](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/docs/audits/2026-10-29-registrar-frontend-review-ledger.md). **Audit:** [#4059 group98](https://github.com/drsapaev/final/pull/4059#issuecomment-6905825021). Do not create another finding ID or claim a source fix from this docs-only branch.

## Source-backed root cause

- [`frontend/src/pages/registrar/views/WelcomeView.tsx#L785-L814`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/views/WelcomeView.tsx#L785-L814): actions `in_cabinet` and `complete` call `updateAppointmentStatus` directly, with neither confirmation nor shared handling.
- [`frontend/src/pages/registrar/useRegistrarRowActions.ts#L87-L140`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarRowActions.ts#L87-L140): canonical `handleTableAction` already awaits `confirm()` and exits on rejection, then invokes the existing status mutation.
- [`frontend/src/pages/RegistrarPanel.tsx#L270-L300`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/RegistrarPanel.tsx#L270-L300): this shared callback is already instantiated and passed to Worklist; Welcome receives direct mutation callback instead.

**Desired behavior**: use the SAME parent `handleTableAction` callback from Welcome, without reimplementing the dialog logic. Cancel/decline => **zero status mutations**; confirm => **one mutation through canonical path**. No backend/API, queue identity, authorization, payment or clinical policy change. Preserve `view`, `edit`, `payment`, `print`, `call`, `more` behaviors.

## Original gate and execution plan

**Chosen mode:** `gate_known_root_cause` (root cause proven, clinical workflow/queue status change = mandatory blocking gate under root `AGENTS.md`). Exact first-touch files:

1. `frontend/src/pages/registrar/views/WelcomeView.tsx` — blob `ad0cf3a6cac39631013d0c4cad5221d0dd8feedc`
2. `frontend/src/pages/RegistrarPanel.tsx` — blob `233f4eb6cc651a14643f2744182999560106c732`
3. `frontend/src/pages/registrar/views/__tests__/WelcomeView.honestStates.test.tsx` — blob `556b870bb38b9658fe8a36d3c3453b311c61f92b`
4. `frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts` — blob `15b06d837e9bb7991b56cf111fbdd91d03191f82`

**Read-only references:** `AGENTS.md`, `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md`, `ai/langgraph/scripts/agent_gate.py`, `ai/langgraph/scripts/run_agent_gate.ps1`, `useRegistrarRowActions.ts`, `appointmentsTableContracts.ts`, and the audit ledger. **Denied:** backend, DB/migrations, queue ownership/fairness, payment, auth/RBAC, production, AGENTS.md/gate logic changes, live patient data, tests outside this bounded scope unless a newly justified handoff authorizes them.

From the agent's fresh isolated worktree, with working directory `ai/langgraph`, use PowerShell and pass the **required task positional argument**:

```powershell
.\scripts\run_agent_gate.ps1 'REG-FE-006: route Registrar Welcome in_cabinet and complete via confirmation-gated handleTableAction; synthetic regression tests; no backend policy changes' --known-root-cause frontend/src/pages/registrar/views/WelcomeView.tsx --scope frontend/src/pages/registrar/views/WelcomeView.tsx --scope frontend/src/pages/RegistrarPanel.tsx --scope frontend/src/pages/registrar/views/__tests__/WelcomeView.honestStates.test.tsx --scope frontend/src/pages/registrar/__tests__/useRegistrarRowActions.test.ts --format json
```

**Important prior correction:** the first audit handoff comment omitted the mandatory `task` positional argument, which would fail argument parsing. The command above includes it. **Fail closed** if `result != gate_ok`, `gate_misroute`, `override_used`, scope drift, required handoff missing, or any reported stop condition. If `handoff_required=true`, read the actual `execution_prompt` and perform/honor its handoff protocol before touching code. Never call bare `agent_gate.py` as a substitute, fake the gate, alter gate code or bypass the stop.

## Archived candidate

The archived diff records the first proposal against `b93ea711`. Use #4099 for the verified implementation and its test changes. [Archived candidate](./patches/REG-FE-006-candidate.patch) · [Verified source](https://github.com/drsapaev/final/pull/4099)

The proposal included these four file changes.
- Welcome `WelcomeViewProps` and destructuring: replace direct `updateAppointmentStatus` with typed `handleTableAction`.
- Welcome `onActionClick('in_cabinet'|'complete')` delegates to parent callback rather than writing queue state.
- `RegistrarPanel` passes `handleTableAction={handleTableAction}` to Welcome.
- Synthetic Welcome test stubs clickable table actions and verifies precise delegation; hook test adds **negative completion** case (declined confirmation => no status mutation). Existing canonical hook tests cover positive and denied `in_cabinet`.

**Test-first instruction:** Prefer first applying only the regression test changes; confirm they fail against the old source, then apply the source changes and show they pass. If candidate patch no longer applies, reconcile against fresh source and re-run gate if actual scope changes. If no local test execution or gate launcher exists, **do not** claim success and leave the work as an unmerged handoff.

## Original validation and acceptance

- Synthetic Welcome `in_cabinet` and `complete` actions dispatch **exactly once** to the existing `handleTableAction` with the same queue/visit record; no direct status mutation.
- Under real hook `confirm=false` for either action => `updateAppointmentStatus` **never** called; `confirm=true` => correct status (`in_cabinet` / `done`) and record, exactly once. Existing `call`, `print`, `view`, `payment`, `more` unaffected.
- Run targeted Vitest from `frontend`: `npm run test:run -- src/pages/registrar/views/__tests__/WelcomeView.honestStates.test.tsx src/pages/registrar/__tests__/useRegistrarRowActions.test.ts`. Run `npm run type-check`, scoped ESLint WITHOUT autofix, `git diff --check`, and current-head PR CI. Report what truly ran and outputs. Protect `ai/langgraph/scripts/run_agent_gate.ps1`.
- Keep `REG-FE-006` and the #4063 remediation count open until the source fix is independently verified in `main` after the applicable gate and CI pass. [Audit PR](https://github.com/drsapaev/final/pull/4059)

## Handoff evidence from November 16, 2026

**Completed:** source and parent/hook/test ownership inspected on current main; root skill `code-security` and `javascript-testing-patterns` consulted; four-file candidate diff prepared and statically parsed; candidate staged as non-executable reference **only in this handoff branch**; exact required gate invocation corrected; test/rollback plan recorded.

**Not completed:** local project gate (no repo-execution PowerShell), red-to-green Vitest, TypeScript, ESLint, true `git apply --check` on a fresh checkout, clinical workflow browser regression, source edit or source PR, merge, production deployment. This branch contains **no application or test changes**. No PHI used. No tests or gate claimed as successful.

The initial handoff led to a separate source branch. The verified commit and release status are recorded above.

To roll back the source change after release, revert #4099. [Source PR](https://github.com/drsapaev/final/pull/4099)

## Documentation CI reconciliation (2026-11-16)

Initial handoff Draft PR #4097 `PR Review Quality Gate` failed **solely on PR-description template sections**, not on application tests. Logs of run `43805953344` identified missing `Summary`, `Cyclic Execution Evidence`, `Contract Impact`, `RBAC / Permissions`, `Notification / Realtime`, `Frontend Resilience`, `Scope Gate`, and `Validation`. The reviewer corrected the existing Draft PR **body** using the canonical required eight headings; this docs-only follow-up commit triggers fresh pull-request checks against that metadata. `Unified CI`, `Security Scan`, `Gitleaks`, `Agent Workflow Guards`, and `PR Lifecycle Recommendation` had already passed on the initial docs-only head. None of those checks counts as actual `run_agent_gate.ps1` output or source-fix test evidence. The fixing agent must inspect the latest HEAD-specific CI result and treat any red check as open.

## Final candidate integrity recheck (2026-11-16; reference only)

- Actual patch in this branch [`docs/audits/patches/REG-FE-006-candidate.patch`](./patches/REG-FE-006-candidate.patch) now has **9 exact-context unified-diff hunks across 4 files**. The additional hunk updates the Welcome component header documentation to reference `handleTableAction` rather than its removed direct `updateAppointmentStatus` prop. An initial malformed diff context was corrected in the *patch document* only, not application source.
- **Static exact-apply simulation passed** on all 9 hunks against four GitHub-fetched blobs of `main=b93ea7117e2272d18c19fe1c4825695392c9b550`: old/new context and declared hunk counts matched, new hunk offsets matched, removal of direct status calls and parent callback wiring matched, synthetic test insertions matched. This is **NOT** a real full-repo worktree `git apply --check`, nor Vitest/tsc/lint.
- The earlier handoff commit `a31e3ccd83b88c74183926aaddc484dc6bb2584c` had all six PR CI checks SUCCESS (Unified, Security, Gitleaks, Agent Workflow Guards, PR Review Quality, Lifecycle). The *newest patch-document commit* has to be checked independently; no app runtime tests have run.
