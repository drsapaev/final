# REG-FE-006 — fixing-agent handoff (BLOCKED: mandatory gate; NOT a fix)

**State:** `HANDOFF_READY / CODE_NOT_MODIFIED / GATE_NOT_RUN / TESTS_NOT_RUN / NO_SOURCE_PR / DO_NOT_MERGE`.
**Priority:** P2. **Scope:** Registrar Welcome page only; confirmation for `in_cabinet` and `complete`.
**Base:** `main` commit [`b93ea7117e2272d18c19fe1c4825695392c9b550`](https://github.com/drsapaev/final/commit/b93ea7117e2272d18c19fe1c4825695392c9b550), rechecked 2026-11-16; after previous main advanced, all four source/test blob SHAs below remained unchanged.
**Existing finding:** [2026-10-29 registrar frontend review ledger REG-FE-006](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/docs/audits/2026-10-29-registrar-frontend-review-ledger.md). **Audit:** [#4059 group98](https://github.com/drsapaev/final/pull/4059#issuecomment-6905825021). Do not create another finding ID or claim a source fix from this docs-only branch.

## Source-backed root cause

- [`frontend/src/pages/registrar/views/WelcomeView.tsx#L785-L814`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/views/WelcomeView.tsx#L785-L814): actions `in_cabinet` and `complete` call `updateAppointmentStatus` directly, with neither confirmation nor shared handling.
- [`frontend/src/pages/registrar/useRegistrarRowActions.ts#L87-L140`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarRowActions.ts#L87-L140): canonical `handleTableAction` already awaits `confirm()` and exits on rejection, then invokes the existing status mutation.
- [`frontend/src/pages/RegistrarPanel.tsx#L270-L300`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/RegistrarPanel.tsx#L270-L300): this shared callback is already instantiated and passed to Worklist; Welcome receives direct mutation callback instead.

**Desired behavior**: use the SAME parent `handleTableAction` callback from Welcome, without reimplementing the dialog logic. Cancel/decline => **zero status mutations**; confirm => **one mutation through canonical path**. No backend/API, queue identity, authorization, payment or clinical policy change. Preserve `view`, `edit`, `payment`, `print`, `call`, `more` behaviors.

## Gate / execution boundary — MUST run BEFORE applying any source change

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

## Prepared candidate (NOT applied)

The candidate diff is stored **in this same handoff branch** at [`docs/audits/patches/REG-FE-006-candidate.patch`](./patches/REG-FE-006-candidate.patch). It only changes the above four files; it is a **proposal** and must be independently rechecked against fresh current main after the gate, not blindly applied. Source changes not yet present in the branch:
- Welcome `WelcomeViewProps` and destructuring: replace direct `updateAppointmentStatus` with typed `handleTableAction`.
- Welcome `onActionClick('in_cabinet'|'complete')` delegates to parent callback rather than writing queue state.
- `RegistrarPanel` passes `handleTableAction={handleTableAction}` to Welcome.
- Synthetic Welcome test stubs clickable table actions and verifies precise delegation; hook test adds **negative completion** case (declined confirmation => no status mutation). Existing canonical hook tests cover positive and denied `in_cabinet`.

**Test-first instruction:** Prefer first applying only the regression test changes; confirm they fail against the old source, then apply the source changes and show they pass. If candidate patch no longer applies, reconcile against fresh source and re-run gate if actual scope changes. If no local test execution or gate launcher exists, **do not** claim success and leave the work as an unmerged handoff.

## Validation and acceptance

- Synthetic Welcome `in_cabinet` and `complete` actions dispatch **exactly once** to the existing `handleTableAction` with the same queue/visit record; no direct status mutation.
- Under real hook `confirm=false` for either action => `updateAppointmentStatus` **never** called; `confirm=true` => correct status (`in_cabinet` / `done`) and record, exactly once. Existing `call`, `print`, `view`, `payment`, `more` unaffected.
- Run targeted Vitest from `frontend`: `npm run test:run -- src/pages/registrar/views/__tests__/WelcomeView.honestStates.test.tsx src/pages/registrar/__tests__/useRegistrarRowActions.test.ts`. Run `npm run type-check`, scoped ESLint WITHOUT autofix, `git diff --check`, and current-head PR CI. Report what truly ran and outputs. Protect `ai/langgraph/scripts/run_agent_gate.ps1`.
- Only a real source PR with passed gate + green checks + independently verified merged main may mark historical `REG-FE-006` fixed. Do **not** alter existing #4063 counts for this docs handoff. Keep this Draft handoff unmerged; add a new comment to existing audit [#4059](https://github.com/drsapaev/final/pull/4059) after source-fix submission or blocker resolution.

## Handoff bookkeeping (actual actions by audit agent)

**Completed:** source and parent/hook/test ownership inspected on current main; root skill `code-security` and `javascript-testing-patterns` consulted; four-file candidate diff prepared and statically parsed; candidate staged as non-executable reference **only in this handoff branch**; exact required gate invocation corrected; test/rollback plan recorded.

**Not completed:** local project gate (no repo-execution PowerShell), red-to-green Vitest, TypeScript, ESLint, true `git apply --check` on a fresh checkout, clinical workflow browser regression, source edit or source PR, merge, production deployment. This branch contains **no application or test changes**. No PHI used. No tests or gate claimed as successful.

**Fixing agent next action:** fresh isolated worktree from current origin/main → run gate exactly and read execution prompt → first tests (RED), then source patch (GREEN) → checks, separate source PR → follow-up review → merge only when allowed → update audit and old ID after independent main recheck. Branch owner must reconcile moving main and preserve user changes.

**Rollback:** revert the minimal source change of the future fix PR; no migration/data operation required.
