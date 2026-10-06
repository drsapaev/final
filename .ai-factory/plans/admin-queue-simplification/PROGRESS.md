## Current checkpoint — PR #3620 regression correction committed locally; push and exact-head CI pending (2026-10-06T22:19+05:00)

Plan version: 3.41
Current task: T09.3
Current status: IN_PROGRESS (PR #3620 is open; stale test corrected in local commit; evidence checkpoint needs commit/push and hosted rerun)
Worktree: C:\Users\DrSapaev\.codex\worktrees\aqs-t093-cabinet-ui\final
Branch: codex/aqs-t093-cabinet-ui
Base: origin/main c38533b352e792e723495744cb1f17f6a583fb4c
Runtime code commit: 8d77dfa3b06b0e9167faee7216c14b2601d11080
Focused regression correction commit: 0556ab0626dc975ef46eac7ac3eb0bab832d5a22
Current remote PR HEAD: 0e02ff20db8459e1f5728273fc058e7ab86ffd08 (push pending)
Last updated: 2026-10-06T22:19+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T09.1 | MERGED | PR #3612 | 89b4888a013978182e45f34ac2e07a9679c497c9 | EVIDENCE.md#t091-pr-3612-merged |
| T09.2 | MERGED | PR #3614 | c2ccde2e46bbc115e816d4c383df93b1c8665ab1 | EVIDENCE.md#t092-pr-3614-merged |
| T09.3 | IN_PROGRESS | PR #3620 | | EVIDENCE.md#t093-ci-contract-test-follow-up |

## Current checkpoint
- Completed: T09.3 code is based on c38533b352e792e723495744cb1f17f6a583fb4c. PR #3620 previous HEAD 0e02ff20db8459e1f5728273fc058e7ab86ffd08: Frontend E2E passed; Backend tests had 5,347 passed and one failed old HTTP 400 assertion. The failure is fixed in test-only commit 0556ab0626dc975ef46eac7ac3eb0bab832d5a22. Full integration module 7/7, targeted post-format 1/1, Ruff check/format, py_compile and diff check passed locally.
- Changed but not verified: focused test correction is committed locally; four journal files are updated and unstaged. The correction has not been pushed, so hosted results still belong to 0e02ff20db8459e1f5728273fc058e7ab86ffd08.
- Remaining: commit the evidence/body checkpoint, push branch to PR #3620, publish the refreshed PR body, then inspect required checks on the resulting exact HEAD.
- Blocker: PostgreSQL proof beyond hosted backend CI, task-owned staging, backend-dependent E2E, manual viewport review, T18 and full STAGING_VALIDATION.md are NOT_RUN. No T09.3 Tier-2 deferral is accepted.
- Next exact action: commit the refreshed journals, push commits 0556ab062 and the evidence checkpoint, update/validate the PR body, then monitor the exact-head backend/E2E and required checks. Fix any in-scope failure in the same PR.
- Do not start T10 before PR #3620 merges and local main is synchronized.

## Current checkpoint — PR #3614 review fixes and exact-head validation (2026-10-06T16:26+05:00)

Plan version: 3.34
Current task/status: T09.2 review fixes / PR_OPEN — existing PR #3614.
Worktree: `C:\Users\DrSapaev\.codex\worktrees\aqs-t09-2-cabinet-apply\final`
Branch: `codex/aqs-T09.2-cabinet-apply`
Base: `1d146d857e1570ff2259975f081f80dc0b31ae82`
Latest code/evidence HEAD: `3cd2bf1103cd5759c49d9ca73ad8fed4ac686a1f`

- Review: one confirmed P1 (doctor display call ignores the reassigned DailyQueue cabinet) and one P2 (expected cabinet snapshot is stripped before equality check). User explicitly requested both fixes.
- Mode: mandatory `gate`. `scripts/run_agent_gate.ps1` from `ai/langgraph` returned `gate_ok`, `execute`, `handoff_required=true`, `gate_misroute=false`, `override_used=false`. The generated execution prompt was read. Use only its directly relevant first-touch files: cabinet endpoint, display call service, and focused cabinet service test module. The unrelated queue service/model/queue-time paths stay denied.
- Allowed runtime/tests: `backend/app/services/display_websocket_api_service.py`; `backend/app/api/v1/endpoints/queue_cabinet_management.py`; `backend/tests/unit/test_queue_cabinet_management_api_service.py`. The existing display-service unit module may be run read-only. Allowed records: this plan's PROGRESS, RESUME, EVIDENCE, DECISIONS, and main plan.
- Denied: schema/models/migrations, queue writers/defaults, nurse station assignment contract, legacy single/bulk/sync writers, unrelated display/queue paths, frontend, ops, shared staging, production, review publication, merge.
- Chosen semantics: for display calls, a non-empty saved `DailyQueue.cabinet_number` is the day's service location and takes precedence over `Doctor.cabinet`; when the snapshot is null/empty, retain current doctor-default fallback. Owner defaults and other writers do not change.
- CI follow-up: `6803195e` exposed an optional-field compatibility regression in `test_doctor_calls_patient_by_linked_doctor_id_not_user_id`; corrected with `getattr` and pushed in `3cd2bf11`.
- Stop: if fixing the reviewed call needs any additional runtime owner/path, ownership is ambiguous, a denied surface must change, or testing requires shared/production data.

## Current checkpoint
- Completed: P1 and P2 fixes, compatibility correction, and regressions are committed and pushed in existing PR #3614. Latest code/evidence HEAD `3cd2bf11` passed exact-head checks: **30 success, 13 skipped, 0 failures, 0 pending**. PR body was refreshed and its review-quality/lifecycle checks passed.
- Changed but not verified: no runtime/test edits remain. This documentation checkpoint must be pushed and its exact-head checks inspected.
- Remaining: commit/push this final progress checkpoint, verify resulting documentation HEAD checks, then await independent review and a separate staging/deferral decision.
- Blocker: staging remains NOT_RUN and no Tier-2 deferral is accepted; merge remains HOLD.
- First E2E attempt failed one unrelated lab dirty-guard locator wait while Vite proxy returned `ECONNREFUSED`; failed-job attempt 2 passed. Skipped checks (13) include staging/readiness, integration, Docker, load, metadata, selected release/security jobs and notifications; skipped jobs are NOT_RUN, not passes.
- Checks passed locally: display and cabinet focused suites (27 passed, 1 existing provider warning); Ruff check and format check; `py_compile`; `git diff --check`; commit hooks. PR-body validator passed 19 tests and both documented samples. Staging/browser/full system-health remain NOT_RUN; no deferral accepted; merge remains HOLD.

## Current authoritative checkpoint — T09.2 code-head CI passed (2026-10-06T13:39+05:00)

Plan version: 3.30
Current task/status: T09.2 / PR_OPEN — [PR #3614](https://github.com/drsapaev/final/pull/3614). Generated API freshness correction commit: `80e5ad8`; evidence checkpoint commit: `ca6a1ba8e34ab02cb8773ca38256c33b22516895`.
Worktree: `C:\Users\DrSapaev\.codex\worktrees\aqs-t09-2-cabinet-apply\final`
Branch: `codex/aqs-T09.2-cabinet-apply`
Base commit: `1d146d857e1570ff2259975f081f80dc0b31ae82` (merged PR #3613; synchronized with `origin/main`)
Latest verified PR HEAD before this journal-only refresh: `ca6a1ba8e34ab02cb8773ca38256c33b22516895`; base `1d146d857e1570ff2259975f081f80dc0b31ae82`.
Last updated: 2026-10-06T13:39+05:00

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T09.1 | MERGED | [PR #3612](https://github.com/drsapaev/final/pull/3612) | `89b4888a013978182e45f34ac2e07a9679c497c9` | `EVIDENCE.md#t091-pr-3612-merged` |
| T09.2 | PR_OPEN | [PR #3614](https://github.com/drsapaev/final/pull/3614) | | `EVIDENCE.md#t092-generated-api-freshness-correction` |

## Current checkpoint
- Completed: PR #3613 merged and `origin/main` synchronized; T09.2 apply behavior and post-sync validation remain recorded in EVIDENCE. Correction commit `80e5ad8` fixes generated API freshness; pinned generator output matches the complete artifact. Exact code/evidence HEAD `ca6a1ba8e34ab02cb8773ca38256c33b22516895` passed run `37435553039`: 26 success, 13 skipped, 0 failure, 0 pending. Backend, Frontend E2E/lint/type-check/unit/build, OpenAPI freshness, Code Quality, parity, context-boundary, security and required gate passed. Two duplicate lifecycle/review-quality runs were cancelled; their replacement runs passed.
- Changed but not verified: PR body candidate and this journal now record the exact-head results; the body gate passed 19 tests and both samples. Remote description and journal checkpoint are not yet pushed. The resulting documentation-only head needs a fresh check snapshot. Commit-time ESLint was skipped because the local package is unavailable; hosted Frontend lint passed. Staging/browser/full system-health remain NOT_RUN; no deferral has been accepted.
- Remaining: validate and push the evidence/PR-body checkpoint, verify resulting exact-head checks, then obtain independent review and a separate explicit Tier 2 staging/deferral decision.
- Blocker: merge remains on hold pending independent review and the staging/deferral decision. No staging or production validation is claimed.
- Next exact action: update remote PR description, commit/push this evidence update, and inspect the resulting exact HEAD. Do not merge from this checkpoint.
- Checks to rerun after any runtime/generated change: exact CI generated-types freshness, frontend lint/type-check, and `git diff --check`; prior focused cabinet + disposable PostgreSQL evidence remains valid because this fix changes no API schema or runtime code.

## Prior checkpoint — T09.1 continuation decision (superseded)

## Current authoritative checkpoint — T09.1 continuation decision (2026-10-06T09:26+05:00)

Plan version: 3.23
Current task/status: T09.1 / PR_OPEN — draft [PR #3612](https://github.com/drsapaev/final/pull/3612). Reviewed PR HEAD `a8f7980b1d160726e169050a8bc8f8043294a36b`; code HEAD `390e14b40d6eafb462e05d07f777c1e063a36c14`; current CI **26 success, 13 skipped, 0 failed, 0 pending**. No outstanding source-review P0/P1/P2.
Decision: at the user's request for a continuation decision, the executing agent accepts a **#3612-specific backend/staging deferral** for this unused read-only preview. This is not a human/GitHub review, merge or deployment. UI Tier 1/Tier 2 are not applicable; no UI runtime changed. Full six-field record: `EVIDENCE.md#t091-pr-3612-continuation-decision`.
Scope/mode: continuation of the existing T09.1 narrow override; documentation/PR-description only, no further gate run or scope expansion. Allowed edits: canonical plan, PROGRESS, RESUME, EVIDENCE and existing PR description. No runtime, test, generated API, migration, ops, auth-policy, staging or production changes.
Deferred coverage: real-PG preview, runtime Admin/non-Admin API checks and synthetic workflow/browser acceptance remain NOT_RUN with zero completion credit. T09.2 must prove real-PG preview/apply, stale 409, audit rollback, replay and called/active safety **before its merge**; T09.3 must validate its UI consumer; T18/full pre-deploy staging remain mandatory. This deferral is not inherited by any later PR.
Next exact action: validate/push this journal-only decision and check the resulting PR head. Recommend completing #3612 review/merge next; no merge in this decision-only turn. T09.2 starts only after confirmed merge, branch cleanup and main synchronization. Stop on new runtime changes, an unclear owner/contract, or a required out-of-scope path.

## Historical checkpoint — T09.1 cabinet preview (2026-10-06T07:42:29+05:00)

Plan version: 3.22
Execution permission: user authorized implementation of the full plan and said “мёрж и продолжать”; PR #3609 has been merged. Continue T09.1 only in its approved read-only preview scope.
Current task: T09.1 — read-only preview and typed DTO for an explicit clinic-today cabinet reassignment.
Current status: PR_OPEN — draft [PR #3612](https://github.com/drsapaev/final/pull/3612), latest PR HEAD `390e14b40d6eafb462e05d07f777c1e063a36c14`, base `6141fa33c1872d4c0da4c9d1a7f2e95ab3438d92`. Source review found no remaining P0/P1/P2 after the two OpenAPI fixes and generator-parity correction. Current check rollup: 29 success, 13 skipped, 0 failed; frontend E2E passed on rerun. PR description now passes local template validation and hosted PR Review Quality Gate. Worktree `C:\Users\DrSapaev\.codex\worktrees\aqs-t09-preview\final`, branch `codex/aqs-T09.1-cabinet-preview`. Main `C:\final` remains untouched and unrelated `.gate_artifacts/` is preserved.
Mode: mandatory `gate` for queue mutation/audit domain. Initial gate and its one `--known-root-cause backend/app/services/queue_cabinet_management_api_service.py` retry both routed to migration / Alembic `0078_*.py`; generated prompts were read. This is a confirmed misroute because T09.1 is a read-only preview and adds no storage. After the required retry, use the narrow override grounded in the user's approved plan; record `gate_misroute=true`, `override_used=true`. Do not change the gate router or add a migration.
Canonical anchors: T09 in `codex-admin-queue-simplification.md`; `backend/app/services/queue_cabinet_management_api_service.py`; `backend/app/repositories/queue_cabinet_management_api_repository.py`; `backend/app/api/v1/endpoints/queue_cabinet_management.py`; `backend/app/services/queue_domain_service.py::_build_cabinet_payload`; `backend/app/services/queue_status.py`; `backend/app/models/service_execution.py`; focused cabinet service tests.
Allowed paths: the cabinet management service, repository, endpoint, `backend/tests/unit/test_queue_cabinet_management_api_service.py`, new focused integration tests if required, generated `backend/openapi.json` and `frontend/src/types/generated/api.ts`, and the canonical plan plus `PROGRESS.md`, `RESUME.md`, `EVIDENCE.md`.
Reference-only / denied: frontend runtime; models and migrations; audit writers; doctor/resource default writers; legacy bulk and sync writes; unrelated APIs/tests; ops, other generated output, shared staging, production/live data. T09.1 must not add apply, audit, or mutation behavior.
Completed: PR #3609 merged at `6141fa33c1872d4c0da4c9d1a7f2e95ab3438d92`; GitHub reported 17 successful and 18 skipped checks, with no failed applicable check. Main synchronized. The prior worktree was archived. FastAPI and PostgreSQL skills were read. Typed owner semantics, waiting statuses, called/clinical blockers, and resource default writer were traced in source.
Changed and validated locally: read-only Admin preview endpoint/DTO, batched repository reads, service policy, focused tests, OpenAPI snapshot, generated API types, and the four plan checkpoints. Preview uses clinic-local today; keeps day cabinet separate from doctor/resource default; counts only waiting entries; blocks called, active clinical statuses (including legacy `in_progress`) and active `ServiceExecution`; rejects missing, duplicate, invalid-owner and non-today targets. No rows are written and no patient fields are returned.
Validation: focused cabinet service + OpenAPI modules **49 passed, 1 warning**; Ruff check/format, Black, `py_compile`, `git diff --check`, standalone generated TypeScript and repository `npm run generate:api-types:check` **PASS**. On exact HEAD `390e14b4`, hosted backend tests, frontend lint/type-check/API parity, frontend unit tests/build, OpenAPI freshness, E2E rerun, security and PR quality gates passed. Current rollup is **29 success, 13 skipped, 0 failed**. Skipped staging/production readiness, PG integration, k6, Docker, DAST, Telegram, metadata, Supabase Preview, classify-and-route and notifications are not passes. The first E2E run had one unrelated lab-dirty-guard timeout among 60 passing tests; rerun of the failed job passed. PostgreSQL-specific validation, runtime Admin auth integration, synthetic staging/browser acceptance and production remain **NOT_RUN**. See `EVIDENCE.md#t091-final-review-and-exact-head-validation`.
Blocker: none. Stop if a required field needs patient data, ownership is ambiguous, preview mutates state, any apply/audit behavior is required, or a path outside the allowlist is needed.
Next exact action: commit and push this final review/evidence checkpoint, inspect all checks on the resulting exact PR head, then await the user's review/merge direction for PR #3612. Do not merge or begin T09.2 without that direction; T09.2 must wait until this PR cycle closes and main is synchronized.
Checks to run after this checkpoint is pushed: confirm exact-head backend, frontend, OpenAPI, security, E2E and PR quality statuses; rerun relevant validation only if runtime/generated API files change.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T08.3.3 | MERGED | PR #3609 | `6141fa33c1872d4c0da4c9d1a7f2e95ab3438d92` | `EVIDENCE.md#t0833-pr-3609-merged` |
| T09.1 | MERGED | [PR #3612](https://github.com/drsapaev/final/pull/3612) | `89b4888a013978182e45f34ac2e07a9679c497c9` | `EVIDENCE.md#t091-pr-3612-merged` |
| T09.2 | IN_PROGRESS | `codex/aqs-T09.2-cabinet-apply` | | `EVIDENCE.md#t092-pre-edit-gate-and-scope` |

## Historical checkpoint — T08.3.3 GraphQL quota proof (2026-10-05T21:10:45+05:00)

Plan version: 3.12
Execution permission: user authorized implementation of the full plan, then asked to fix and continue; PR #3607 was explicitly authorized and is now merged.
Current task: T08.3.3 — direct GraphQL last-slot quota proof and source-backed reachable-writer parity.
Current status: PR_OPEN — [#3609](https://github.com/drsapaev/final/pull/3609), current head `e84fd4d7edf7859ca5ea2534b65645149ed29e44`, base `main` at `589520ae132313ca9488f3994be8d28f6041975a`. Worktree `C:\Users\DrSapaev\.codex\worktrees\aqs-t08-3-3-graphql\final`, branch `codex/aqs-T08.3.3-graphql`. The main checkout fast-forwarded to the same base; unrelated untracked `.gate_artifacts/` was preserved.
Mode: mandatory `gate`. Initial gate and its one `--known-root-cause backend/app/graphql/mutations.py` retry both returned `Mode: migration`, first-touch `backend/alembic/versions/0078_*.py`, because the description mentioned the writer evidence “table”. The generated execution prompt was read. The machine result did not set `gate_misroute`, but its Alembic route conflicts with the explicit test-only T08.3.3 plan; after the required retry, apply a narrow override grounded in the user's approved plan. Report `gate_misroute=true` (observed) and `override_used=true` (manual scope override); do not edit the router or migration.
Canonical anchors: T08.3.3 in `codex-admin-queue-simplification.md`; `backend/app/graphql/mutations.py::_join_queue_impl`; `backend/tests/integration/test_daily_queue_lock_parity_pg.py`; `backend/app/services/queue_api_service.py::get_or_create_daily_queue`; `backend/app/repositories/queue_api_repository.py`; T08 writer coverage table in `EVIDENCE.md`.
Allowed paths: `backend/tests/integration/test_daily_queue_lock_parity_pg.py`; `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,RESUME,EVIDENCE}.md`.
Read-only references: `backend/app/graphql/mutations.py`; `backend/app/services/queue_api_service.py`; `backend/app/repositories/queue_api_repository.py`; existing GraphQL resolver tests and queue admission source. If the test exposes a runtime gap, stop and create a separately gated runtime task.
Denied paths: `backend/app/**` runtime edits; `backend/alembic/**`; `backend/app/models/**`; frontend; ops/Docker; unrelated tests; generated output; staging and production/live data; feature flag changes.
Completed: PR #3607 merged at `589520ae132313ca9488f3994be8d28f6041975a`; exact reviewed head `37eb0d4b5d8628bdd8598990ad93a0f4093a7c96` had 17 success, 18 skipped and 0 failure; main synchronized after checking no tracked edits or process executable rooted in `C:\final`. Added and passed the new direct GraphQL PostgreSQL contention/replay regression. The full PG module passed 6/6 with zero skips; the focused GraphQL quota unit cases passed 3/3. Completed the mounted-writer and counter-mutation source inventory; no runtime gap found in this test/evidence slice.
Changed and locally validated: `backend/tests/integration/test_daily_queue_lock_parity_pg.py` plus the canonical plan and progress/evidence journals. No runtime/model/migration/API code changed. Disposable PostgreSQL 16 container and task keepalive were stopped/removed; loopback port 55437 was released; temporary synthetic password file was removed.
Validation complete: `ruff check`, `ruff format --check`, `black --check`, `py_compile`, and `git diff --check` all passed. Ruff and Black initially disagreed on three existing diagnostic-only assertions; concise `repr` messages now satisfy both without changing predicates. Initial launcher/formatter invocations were corrected; final whole-file checks pass.
PR #3609 exact-head checks on `e84fd4d7edf7859ca5ea2534b65645149ed29e44`: **10 success, 4 skipped, 0 failed, 0 pending**. Successes include Python/JavaScript/Actions CodeQL analyses, security scan, gitleaks, GitGuardian, PR Review Quality Gate, secret scan, and lifecycle recommendation. Skips include Supabase Preview, classify-and-route, and notification-only jobs; they are not passes. No backend test job appeared in the check-run rollup; PostgreSQL integration and GraphQL quota unit tests were run locally as listed above. PR state OPEN, mergeStateStatus BLOCKED, reviewDecision empty; no formal review or merge was submitted. This journal update will create a new PR head, so verify checks on that head before closing the cycle.
Blocker: none currently. Stop if PostgreSQL isolation is unavailable, the GraphQL resolver requires a runtime change, a reachable writer lacks the canonical quota boundary, or ownership/identity is ambiguous.
Next exact action: commit/push this final check-status checkpoint and verify the new exact-head checks. Then wait for human review/merge direction; do not start T09 until T08.3.3 is merged.
Checks to rerun after the next change: `git diff --check` before the checkpoint commit; after push, verify exact-head GitHub checks. Any code change requires repeating the PG module and focused GraphQL quota unit cases.

> Historical checkpoint below: T08.3.2 clock P2 correction before PR #3607 merged.

## Historical checkpoint — T08.3.2 clock P2 correction (2026-10-05T19:21:23+05:00)

Plan version: 3.9
Current task: fix the remaining QR-session clock seam in PR #3607.
Current status: PR_OPEN, locally validated and exact-head CI green. Code correction `8c8ac83e5ab16185404bf6c901aea15041214195`; latest branch checkpoint before this final record is `5fd78c4b3c78f4e4c8dfa2a7e18160c0edd00dff`. PR #3607 is OPEN, mergeable, clean against base `c1781c46a1b03c3404604542bcc9c4c9951f4c89`.
Branch: `codex/aqs-T08.3.2-clockfix`; rebased onto fresh `origin/main` (dependency-only PR #3608).
Mode: `gate_known_root_cause`. The mandatory rerun returned `narrow_override`, `execute`, `handoff_required=true`, `gate_misroute=true`, `override_used=true`; known owner `backend/tests/integration/test_qr_family_phone_identity.py`. The generated prompt was read. Its first-touch also listed unrelated ops/packaging files. Narrow basis: user explicitly requested correction of the review P2; approved T08.3.2 scope permits this existing test module and its plan journals only. No third gate run; no runtime/ops changes.
Canonical anchors: `backend/tests/integration/test_qr_family_phone_identity.py`; `backend/app/services/queue_svc/_base.py::_now`; `backend/app/services/qr_queue/_base.py::_now`; `backend/app/services/qr_queue/_sessions.py::start_join_session`; current T08.3.2 plan/evidence.
Allowed paths: QR PostgreSQL test module and this plan's canonical document, `PROGRESS.md`, `RESUME.md`, `EVIDENCE.md`.
Denied paths: `backend/app/**`, models, migrations, API, frontend, `ops/**`, Docker/Compose, unrelated tests, generated output, shared staging, production/live data.
Confirmed defect: patching only `queue_service.datetime` leaves `qr_queue_service.datetime` live. A read-only probe of the real QR window check at 23:59:30 returned `after_end_time` while queue service time was 12:00.
Change in progress: patch both public clock facades to one clinic-local noon; add a focused assertion that both facades report the same frozen time. The four existing tests already pass the matching clinic day to their seed helpers.
Validation: focused clock-facade test PASS (1 passed, 11 deselected); full module PASS on disposable PostgreSQL 16 (12 passed, 0 skipped, 1 warning); Ruff check, Ruff format check, `py_compile`, and `git diff --check` PASS. Commit hooks including Black and gitleaks PASS. Disposable PostgreSQL and WSL holder were removed. GitHub checks on exact HEAD `5fd78c4b3c78f4e4c8dfa2a7e18160c0edd00dff`: **17 success, 18 skipped, 0 failure, 0 in progress**. Skipped jobs: staging/production readiness, k6, integration/Docker, frontend unit/build/lint/e2e, Telegram release, docs/metadata, DAST, Supabase Preview, classify-and-route, and two failure notifications. Skips are not passes. PR description update passed its local 19-test validator; follow-up quality/lifecycle checks passed.
Stop conditions: any runtime edit, unclear clock ownership, unavailable isolated PG, or required path outside approved test/docs scope.
Next exact action: commit and push this current progress checkpoint, then verify the new documentation-only HEAD checks and refresh the PR description's head reference. Wait for the user's review/merge decision; do not merge or start T08.3.3 without separate user instruction.

> Previous checkpoints below are chronological evidence and are superseded by this active correction checkpoint.

## Current authoritative checkpoint — T08.3.2 post-merge P2 follow-up (2026-10-05T17:38:38+05:00)

Plan version: 3.7
Execution permission: IMPLEMENTATION_ACTIVE — user asked “исправляй” for the confirmed P2 in the merged #3600 tests.
Current task: remove wall-clock dependence from the four QR-session v1 PostgreSQL tests.
Current status: PR_OPEN — [PR #3607](https://github.com/drsapaev/final/pull/3607), code/test commit `ae0bd8a7f24b27f7b1981911b2b9ecfaec9ede2f`; exact PR HEAD `d4d1524aa96f7260825b6f0caf1b9cb724044490` passed 10 checks, 4 were skipped, 0 failed. A new documentation-only checkpoint will require checking its resulting HEAD.
Branch: `codex/aqs-T08.3.2-clockfix`; base `origin/main` = `ba03fdfb8d14d38a68a2d16df93145562cd87c63`; merge #3600 = `b3bd5272389da88513cc1ac23985b390489554f9`.
Mode: `gate_known_root_cause`. Gate output was `gate_ok` / `execute`, `handoff_required=true`, with the confirmed test module plus unrelated Docker/Compose paths in first-touch; `gate_misroute=false`, `override_used=false`. Its execution prompt was read. The user's explicit P2 fix request and approved T08.3.2 test-only scope authorize this existing PG test module and plan checkpoint updates; only those paths were used. No runtime/ops changes.
Canonical anchors: `backend/tests/integration/test_qr_family_phone_identity.py`; queue admission clock seam `backend/app/services/queue_svc/_base.py::_now` and `backend/app/services/queue_service.py::datetime`; T08.3.2 in the canonical plan; `docs/runbooks/AGENT_SESSION_WORKTREES.md` and `docs/runbooks/WSL_STAGING_SESSION.md`.
Allowed paths: the QR PG test module and this plan's canonical document plus `PROGRESS.md`, `RESUME.md`, `EVIDENCE.md`.
Denied paths: runtime, models, migrations, API, frontend, `ops/**`, Docker/Compose, generated output, unrelated tests, shared staging and production/live data.
Actual source change: fixed-clinic-day fixture freezes the queue service clock at 12:00 Asia/Tashkent; the four new tests pass that same day to synthetic queue/token seed helpers. This keeps real v1 window enforcement active and avoids the 23:59 cutoff flake.
Validation: PostgreSQL 16 module **11 passed, 0 skipped, 1 warning** using a unique Alembic-upgraded scratch DB on loopback. Ruff, Black check, `py_compile`, and `git diff --check` passed. The initial run without a held WSL session returned 11 skipped after its disposable DB disappeared; it is recorded as NOT_RUN, not a pass. The successful rerun held the task-owned WSL process for the full test command; its container and holder were removed afterward.
Stop conditions: any need to change runtime behavior or edit outside the approved test/docs scope; inability to keep the queue clock and seeded day consistent; DB isolation failure.
PR body quality gate passed (19 validator tests, samples and this body); PR #3607 is open and attached to this task. The exact-head check snapshot is recorded in `EVIDENCE.md`. Next exact action: push this evidence-only update and verify checks on the resulting PR HEAD; then wait for the user's review/merge decision. Do not start T08.3.3 until this follow-up PR cycle is merged.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T08.3.2 | MERGED | [PR #3600](https://github.com/drsapaev/final/pull/3600) | `b3bd5272389da88513cc1ac23985b390489554f9` | `EVIDENCE.md#t08.3.2` |
| T08.3.2-P2 | MERGED | [PR #3607](https://github.com/drsapaev/final/pull/3607) | `589520ae132313ca9488f3994be8d28f6041975a` | `EVIDENCE.md#t0832-pr-3607-merged` |
| T08.3.3 | IN_PROGRESS | `codex/aqs-T08.3.3-graphql` | | `EVIDENCE.md#t0833-gate-and-scope` |

> The checkpoint below is historical: it predates the merge of #3600 and the P2 follow-up recorded above.

## Current authoritative checkpoint — T08.3.2 (2026-10-05T13:48:16+05:00)

Plan version: 3.4
Execution permission: IMPLEMENTATION_ACTIVE — user said “продолжай” after T08.3.1 merged.
Current task: T08.3.2 — real PostgreSQL proof for QR join-session transaction, replay snapshot and partial batches.
Current status: PR_OPEN — [PR #3600](https://github.com/drsapaev/final/pull/3600), code/test commit `b3ca1a270aa8ac2b0808487a398442acb39c6466`. Applicable CI, security and quality checks passed for exact PR HEAD `27fccddc509f5e7557f57d1038c84dcd2eeae954`; path-aware jobs were skipped. This journal update requires a fresh exact-head check. Managed worktree base is `34ca6e59080dc679a6c7f921ac88a6aacb34e996`; branch `codex/aqs-T08.3.2-qr-session`.
Mode: `gate_known_root_cause`. First mandatory gate routed to unrelated Docker/Compose packaging (`gate_misroute=false`, `override_used=false`, `handoff_required=true`). Required one retry with confirmed owner `backend/app/services/qr_queue/_sessions.py` returned `narrow_override` (`gate_misroute=true`, `override_used=true`, `handoff_required=true`). Its execution prompt was read. The returned first-touch list still contains unrelated packaging files and omits a test owner; apply the plan-approved narrow scope below. This is an explicit gate misroute/override and must be reported.
Narrow override basis: the user's approved T08.3 plan explicitly allows the QR session service to remain read-only while adding real PostgreSQL proof in an existing QR-session PG test module or one newly gated module. No runtime behavior change is authorized by this checkpoint. If evidence reveals a runtime defect, stop and obtain a fresh gate before any runtime edit.
Canonical anchors: `.ai-factory/plans/codex-admin-queue-simplification.md` T08.3.2; `backend/app/services/qr_queue/_sessions.py` (`complete_join_session`, `complete_join_session_multiple`, replay snapshot); `backend/tests/integration/test_qr_family_phone_identity.py` (synthetic scratch-PostgreSQL fixture and QR session flows); `backend/app/services/queue_domain_service.py` and focused allocator/quota tests as read-only references; `docs/runbooks/AGENT_SESSION_WORKTREES.md`; `docs/runbooks/CODEX_SUPERPOWERS_GUARD.md`.
Allowed paths: `backend/tests/integration/test_qr_family_phone_identity.py`; `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,RESUME,EVIDENCE}.md`.
Denied paths: `backend/app/**` (including `_sessions.py`), `backend/alembic/**`, `backend/app/models/**`, `frontend/**`, `ops/**`, `output/**`, `test-results/**`, `storage/**`, all unrelated tests, production/live data and shared staging. Use synthetic rows in the module's unique disposable PostgreSQL database only; creation flag remains default-off.
Validation: full `backend/tests/integration/test_qr_family_phone_identity.py` against a disposable PostgreSQL 16 container — **11 passed, 1 warning**; `backend/tests/unit/test_qr_queue_service_allocator_boundary.py` on its SQLite fixtures — **4 passed, 1 warning**; scoped Ruff check, `py_compile`, `ruff format --check`, `black --check`, and `git diff --check` — PASS. Pre-commit Black normalized a few old long lines in this module; two assertion messages were shortened to keep Black/Ruff formatting aligned, with no behavior change.
Stop conditions: gate-approved path mismatch; any runtime defect; test fixture cannot prove independent PostgreSQL sessions or cannot guarantee disposable DB isolation; unclear partial-result contract; production/staging data access; database/service instability.
Completed checks: exact lost-response replay returns the saved response without another issuance; pre-commit injected failures in both single and multi flows leave the committed session, patient, entry and issuance counter untouched; a permitted partial multi-target result commits only the accepted item, reports the rejected item, persists exact snapshot and replays without counter changes. The first PG-connected runs exposed only test-fixture setup issues (v1 time window, missing QR profiles, then non-unique synthetic profile keys); those fixtures were corrected and the final full-module run passed.
Next exact action: commit and push this CI-evidence checkpoint, inspect checks on the resulting exact PR HEAD, and wait for the user's review/merge decision. Do not merge or start T08.3.3 without the PR cycle closing and separate authorization.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T08.3.1 | MERGED | PR #3599 | `a452c54e5851611476c1b2ac3e3298aeff467eca` | `EVIDENCE.md#t08.3.1` |
| T08.3.2 | PR_OPEN | [PR #3600](https://github.com/drsapaev/final/pull/3600) | | `EVIDENCE.md#t08.3.2` |
| T08.3.3 | PLANNED | | | |

## Current authoritative checkpoint — T08.3.1 (2026-10-05T00:28:28+05:00)

Plan version: 3.0
Execution permission: IMPLEMENTATION_ACTIVE — user authorized sequential plan implementation and explicitly said “GO merge, потом продолжай”.
Current task: T08.3.1 — PostgreSQL proof for the legacy queue-token admission transaction
Current status: PR_OPEN. T08.3.1 passed local PostgreSQL/unit/static validation; PR #3599 is open, with code/test commit `465dc814e`; exact-head GitHub CI is pending. PR #3596 / T08.2c merged at `7f3b751241eaa1f9a0ffdf07fff09cbdec32eba7`. Fresh worktree `C:\Users\DrSapaev\.codex\worktrees\aqs-t08-3-pg-proof\final`; branch `codex/aqs-T08.3-pg-proof`; base `origin/main` = merge commit above. Current PR contains two PostgreSQL integration tests and the approved plan checkpoint journals.
Mode: `gate_known_root_cause`; retry returned `narrow_override`, `gate_misroute=true`, `override_used=true`, root-cause test owner `backend/tests/integration/test_daily_queue_lock_parity_pg.py`. The first gate routed the generic “PostgreSQL” keyword to unrelated Docker/Compose packaging. Narrow scope basis: approved T08.3 plan requires independent PostgreSQL concurrency proof and does not authorize packaging changes.
Allowed paths: `backend/tests/integration/test_daily_queue_lock_parity_pg.py`; `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,RESUME,EVIDENCE}.md`.
Denied paths: `backend/app/**`, `backend/alembic/**`, `backend/app/models/**`, `frontend/**`, `ops/**`, `output/**`, `test-results/**`, `storage/**`, production/live data, and all other tests. If a runtime defect appears, stop and obtain a new gate before changing runtime.
Completed: added independent PostgreSQL-session tests for last-slot contention, exact-token replay at a full cap, and caller rollback of entry/counter/token usage. The focused five-test PostgreSQL module passed; three existing quota/window/GraphQL unit modules passed; Ruff, `py_compile`, and `git diff --check` passed.
Environment note: the first full-module run was interrupted when WSL stopped Docker (systemd logged a normal daemon termination; `OOMKilled=false`) and showed one mixed-creator unique violation followed by database-shutdown errors. Under a held WSL session, the mixed-creator regression passed alone and the entire module passed 5/5. Treat the first run as environment-interrupted, not as a source PASS or a confirmed runtime defect.
Next exact action: verify checks on exact PR HEAD `465dc814eb97e567dc1c130539bc5f5037ed69e9`, fix any in-scope failures in this PR, and wait for the user's separate merge authorization. Do not begin T08.3.2 or merge #3599 without that authorization.
Checks to rerun if changed: the focused PostgreSQL module, the three queue quota/window/GraphQL unit modules, scoped Ruff/`py_compile`, and `git diff --check`.

> The T08.2c snapshot below is historical; its OPEN-PR and “do not start T08.3” instructions were superseded by the confirmed merge of PR #3596.

Plan version: 2.9
Execution permission: IMPLEMENTATION_ACTIVE — user resumed the full plan on 2026-10-01
Start here: [RESUME.md](RESUME.md), then this file and current-task EVIDENCE
Canonical plan: [codex-admin-queue-simplification.md](../codex-admin-queue-simplification.md)
Current task: T08.2c — availability/report parity
Current status: T08.2b / PR #3581 MERGED at `742bf08bd82da5f2ab8160ce474bdeab5694aa26`. T08.2c / PR #3596 remains OPEN and mergeable at exact remote HEAD `068fdbede3d08e0bfbd1384ecea7f27cf02827ed`, base `3da3e0ddaa1cf7afed7732905c6699ec4fafada5`. The five requested P2 fixes and focused regressions are committed and pushed; local tests and PR-body quality checks pass. Exact-head CI on current HEAD completed with 31 successful checks, 12 skipped checks, 0 failures. Skips are recorded below and are not passes. Worktree `C:\final\_wt_aqs_t082c_availability`, branch `codex/aqs-T08.2c-availability`. PR body now records the completed exact-head CI. Keep the PR open for the user's review/merge decision. T08.3 must wait for this PR cycle to close; v1 creation stays default-off and PostgreSQL concurrency proof belongs to T08.3.
Last completed task: T08.2b — MERGED (#3581, merge commit `742bf08bd82da5f2ab8160ce474bdeab5694aa26`)
Worktree: C:\final\_wt_aqs_t082c_availability
Branch: codex/aqs-T08.2c-availability
Base commit: 3da3e0ddaa1cf7afed7732905c6699ec4fafada5
Current code commit: `4d301ad64208af81de53b1c7bf88f6735473b6da` (five P2 fixes, pushed to PR #3596)
Current evidence checkpoint: `068fdbede3d08e0bfbd1384ecea7f27cf02827ed`; exact-head GitHub CI passed (31 success, 12 skipped, 0 failures), PR body refreshed and validated
Last updated: 2026-10-04T19:07:37+05:00, Asia/Tashkent

> Historical checkpoint superseded: current T07 status and exact-head evidence are recorded in dated sections below and in RESUME.md; do not use the earlier snapshot as a continuation instruction.

| Task | Status | Branch / PR | Merge commit | Evidence |
|------|--------|-------------|--------------|----------|
| T00 | MERGED | `codex/aqs-T00-docs` / [PR #3536](https://github.com/drsapaev/final/pull/3536) | `bae927f5c88010808d9091e7f47d09bbfdfa1005` | `EVIDENCE.md#t00` |
| T01 | MERGED | `codex/aqs-T01-profile-modal` / [PR #3537](https://github.com/drsapaev/final/pull/3537) | `967bd398c14bce4b835bd5be1205532387e2a909` | `EVIDENCE.md#t01` |
| T02 | MERGED | `codex/aqs-T02-queue-settings-state` / [PR #3538](https://github.com/drsapaev/final/pull/3538) | `b4ba6320797f056da19bbdc5cc672b3a97d2091e` | `EVIDENCE.md#t02` |
| T03 | MERGED | `codex/aqs-T03-cabinet-read` / [PR #3540](https://github.com/drsapaev/final/pull/3540) | `1e781da72bd927926b538b139a6c251cd09848b5` | `EVIDENCE.md#t03-merge-checkpoint` |
| T04 | MERGED | `codex/aqs-T04-empty-profiles` / [PR #3541](https://github.com/drsapaev/final/pull/3541) | `ecc14b05411c7e7b54efca2966416cd6a69df37c` | `EVIDENCE.md#t04-merge-checkpoint` |
| T05 | MERGED | `codex/aqs-T05-settings-cache` / [PR #3543](https://github.com/drsapaev/final/pull/3543) | `fd53206f03b0361de6fc345f53b2bacf4195845c` | `EVIDENCE.md#t05-merge-checkpoint` |
| T06.1 | MERGED | `codex/aqs-T06-policy-schema` / [PR #3545](https://github.com/drsapaev/final/pull/3545) | `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` | `EVIDENCE.md#t06.1-merge-checkpoint` |
| T06.2 | MERGED | `codex/aqs-T06.2-creation-policy` / [PR #3546](https://github.com/drsapaev/final/pull/3546) | `b804a71a6bad22400324e2236a3221317eac3158` | `EVIDENCE.md#t06.2-merge-checkpoint` |
| T07 | MERGED | codex/aqs-T07-admission-window / PR #3557 | 425df11c7a84f0d1e7954df0d00415927212669a | EVIDENCE.md#t07-merge-and-t08-gate-source-audit |
| T08 | IN_PROGRESS | T08.1a/#3571, T08.1b/#3572, T08.2a/#3576, T08.2b/#3581 MERGED; T08.2c / PR #3596 OPEN at `068fdbed`; exact-head CI: 31 success, 12 skipped, 0 failures. Awaiting the user's review/merge decision. | | EVIDENCE.md (latest T08.2c entry) |
| T09 | PLANNED | | | |
| T10 | PLANNED | | | |
| T11 | PLANNED | | | |
| T12 | PLANNED | | | |
| T13 | PLANNED | | | |
| T14 | PLANNED | | | |
| T15 | PLANNED | | | |
| T16 | PLANNED | | | |
| T17 | PLANNED | | | |
| T18 | PLANNED | | | |

## Current checkpoint

### Authoritative continuation — five P2 fixes pushed, exact-head CI passed (2026-10-04)

- PR #3596 is OPEN and mergeable; verified remote HEAD is `068fdbede3d08e0bfbd1384ecea7f27cf02827ed`, base `3da3e0ddaa1cf7afed7732905c6699ec4fafada5`. Worktree/branch are `C:\final\_wt_aqs_t082c_availability` / `codex/aqs-T08.2c-availability`.
- Fixed exactly five confirmed review P2s: inactive queue identity falls back to the wrong owner axis in Admin status; public status accepts an inactive queue with the wrong tag; inactive doctor identity can shadow an active QueueResource; rowless status reports a cap different from the constructor defaults; inactive QR status discards retained waiting/called queue length. See the latest dated EVIDENCE entry for path-by-path mapping.
- Actual runtime/test modifications are restricted to `backend/app/crud/online_queue.py`, `backend/app/crud/queue_resource_routing.py`, `backend/app/services/qr_queue/_queue_ops.py`, `backend/app/services/queue_domain_service.py`, `backend/tests/unit/test_online_admission_window.py`, and `backend/tests/unit/test_queue_domain_service.py`. Allowed checkpoint files are this file, `RESUME.md`, and `EVIDENCE.md`; local scope note is `.scratch/PR3596_FIX_SCOPE.md` and must not be committed.
- Mandatory gate result: `gate_known_root_cause` / bounded `narrow_override`, root `backend/app/services/queue_domain_service.py`, `gate_misroute=false`, `override_used=true`, `handoff_required=false`. The repo-approved T08.2c read/report scope and exact five review findings justify the narrow sibling-path scope; no admission writer, schema/migration/model, frontend, staging or production path is allowed.
- Final focused local checks on committed code: `test_online_admission_window.py` plus `test_queue_domain_service.py` — **57 passed, 1 warning** (SQLite fixtures); scoped Ruff **PASS**; `py_compile` **PASS**; focused formatter ranges **PASS**; `git diff --check` **PASS**. The PR body gate passed 19 unit tests, both documented sample bodies, and the actual updated PR body. PostgreSQL concurrency, staging/browser and production checks are NOT_RUN; T08.3 owns PostgreSQL admission proof.
- Commit `4d301ad64208af81de53b1c7bf88f6735473b6da` contains the five fixes. Current PR HEAD `068fdbede3d08e0bfbd1384ecea7f27cf02827ed` is an evidence-only checkpoint and exact-head GitHub CI completed: **31 success, 12 skipped, 0 failure**. The PR body was refreshed to state this and passed the local body gate (19 tests and documented samples) and remote PR Review Quality Gate. Skipped path-aware jobs include staging/production readiness, integration, Docker, k6 load, metadata, selected security/DAST, Supabase Preview, and failure notifications; they are not passes.
- Next exact action: await the user's independent review and merge decision for PR #3596. Do not publish a review or merge. Keep `C:\final` untouched and do not start T08.3 until #3596 closes.

- T08.2b / PR #3581 is confirmed MERGED at `742bf08bd82da5f2ab8160ce474bdeab5694aa26`; its reviewed code head was `5c32825355fba8bce3ef92a6fcf979a76567da0d`.
- Four additional exact-head P2 report/identity findings were fixed in `ba148e83`, and a related inactive doctor-owned status case was caught and fixed in `210a11fd`: Admin queue status now looks up `DailyQueue` by `Doctor.id`; inactive doctor-queue detection matches the exact nullable tag; Admin aggregates and public status no longer advertise fresh quota for inactive identities. Fail-first reproduced all five assertions for the four findings and the follow-up doctor-owned case; all 56 tests in the three affected unit modules pass (1 warning), as do scoped Ruff, `py_compile`, and `git diff --check` on the rebased tree.
- T08.2c report contract is implemented across concrete QR/status, Admin status, and specialty aggregates: v1 exposes the persisted cap/counter and clamped remaining quota; legacy issuance/remaining stay unknown; active waiting/called queue length is separate; mixed clinic-wide overviews expose no singular quota. Existing `current_usage`, `current_entries`, and numeric legacy `remaining_slots` meanings are preserved. Future-date availability remains advisory as before.
- Five automated P2 findings were reproduced and fixed in `98025bf35545227ba0862cfe1a9fc10e14105df2`: duplicate rowless resource quota; lost clinic-wide queue length on early returns; changed legacy compatibility fields; missing opened-queue policy version; fabricated quota for an inactive resource identity. Fail-first was 5 failed / 35 passed; focused post-fix modules 40 passed / 1 warning; five new regression selections 5 passed / 35 deselected / 1 warning. Focused pre-review report/OpenAPI set was 85 passed / 1 warning; selected resource integration cases 4 passed / 167 deselected / 1 warning. Scoped Ruff, py_compile, OpenAPI freshness, TypeScript freshness, and `git diff --check` passed.
- Previous exact GitHub state: rebased PR #3596 HEAD `38d1fa533b6006c5010d9131652b38e1b18b842e` passed applicable Backend, Frontend E2E/unit/lint/build, OpenAPI/docs, parity, PR Required, quality, security/secret, CodeQL, regression, context-boundary, role-system, locale, lifecycle, PR-body, and Telegram gates. Path-aware skips included staging/production readiness, Docker, integration, load, metadata, nightly DAST and Supabase; skipped jobs are not passes. This check set is exact for `38d1fa5`; the documentation-only status update being prepared will require a fresh check on its own head before merge.
- Path-aware checks skipped (not passed): staging/production readiness, Docker build, integration tests, load tests, and other skipped jobs shown by `gh pr checks`. This read/report-only slice has no staging deferral or staging proof. PostgreSQL concurrency/replay/partial-result proof remains T08.3. The v1 creation flag remains default-off.
- The nine automated review findings (five prior plus four new P2s) and the adjacent inactive-doctor case are covered by the regression suite. GitHub `reviewDecision` is empty; no independent human approval or merge is recorded. The PR remains open.
- No staging, PostgreSQL race test, production access, deployment, flag activation, ownership/numbering, admission-writer, schema, or clinical-lifecycle change occurred. The broad 171-case resource runtime integration module remains NOT_RUN for this follow-up.
- Commit hooks: the initial commit attempt showed Windows Application Control blocks the local Gitleaks and Black executables (`WinError 4551`). Ruff-format also made unrelated formatting changes in four legacy-file regions; those hook-only changes were removed from the worktree. The successful source commit skipped only `gitleaks`, `ruff-format`, and `black`; the other applicable hooks passed. Exact-head GitHub secret checks are still required.
- The current exact PR head `38d1fa533b6006c5010d9131652b38e1b18b842e` has passed applicable CI, with path-aware skips listed above. Next exact action: amend the evidence checkpoint, verify and lease-push it, publish the matching PR body, then confirm applicable checks on the resulting exact PR head. Do not self-approve or merge #3596; wait for independent human review. Do not begin T08.3 until this PR cycle closes.
- Stop on any indication that the aggregate requires a singular quota across heterogeneous owners/policies, or that a writer/schema/ownership change is necessary. T08.3 remains separate.

- User confirmed that they merged PR #3576 themselves. GitHub reports it merged at `1ed6d05874c2ea205a625bb70879adb10b077be4`; exact code HEAD was `35b6943cce8c0295b8e9a68077cb881c73fcda20`. Current base is fresh `origin/main` `4e6f125f17c637fc27296e2d0ec9d23f5d376775` in `C:\final\_wt_aqs_t082b_admission`.
- T08.2b source inventory: legacy `/queue/legacy/join`, mounted `/online-queue/join`, QR `/queue/join/complete` (single and multiple), and permanent-direction sessions all delegate successful admissions to `QueueBusinessService.join_queue_with_token`. It checks the DailyQueue lock-refreshed quota, increments v1 only for a new entry, and keeps entry/counter/session outcome in the existing transaction boundary. GraphQL was the only confirmed independent successful writer and is quota-aware after #3576.
- No additional active successful online-admission writer was found. The old `crud.online_queue.join_online_queue` has no app caller and its old router is not mounted. The Telegram callback is mounted but calls a missing `join_queue` method before any queue write. `/queue/open` creates/opens a queue but does not issue an entry; `QueueApiService` already takes the canonical daily-queue creation lock. Staff service additions, transfers and derivatives are not independent online issuances under D1 and do not increment the counter.
- T08.2b runtime patch: none indicated by source evidence. The evidence-only inventory and existing test anchors are recorded in `EVIDENCE.md`; no tests were run because no runtime or test source changed. `git diff --check` passed after the inventory was written.
- Gate: first run routed the queue task to generic model/window and unrelated Telegram files. The only known-root retry used `backend/app/services/queue_svc/_operations.py`, returned `narrow_override`, and still included unrelated paths. The user-approved T08 plan and required coverage table are the manual basis for the narrow docs-only checkpoint; no additional gate run is permitted.
- PostgreSQL concurrency/replay/partial-result proof remains T08.3. T08.2c reporting parity is still planned. `QUEUE_POLICY_V2_CREATION_ENABLED` remains default-off; no staging or production work was performed.
- The repository PR-body quality gate passed: 19 unit checks, both documented samples, and this PR body.
- Next exact action: push this journal checkpoint, resolve the live PR #3581 HEAD/base, and wait for its applicable checks and merge. After merge, start T08.2c from fresh `origin/main`.

### Historical completed context (T08.2a and earlier)

> Superseded: the T08.2a PR #3576 is merged. The older OPEN/checks-pending instructions below are retained as history only; do not resume them. Continue from the current T08.2b checkpoint above.

- T08.1b / PR #3572 is confirmed MERGED at `95ff3b4752a091f22f9702977d611a3b6d9f1595`; its exact-head applicable CI passed on `6df007c7f63c0ce7be40ac9a6f70c9524fddca65`. Backend tests, PR Required Gate, CodeQL, gitleaks, security scan, parity and quality passed; path-aware frontend jobs were skipped, not passed. PostgreSQL concurrency and staging remain NOT_RUN. The v1 creation flag remains default-off.
- T08.2a is the first bounded slice of T08.2: align the direct GraphQL `Mutation._join_queue_impl` writer with the canonical v1 issuance counter. Preserve GraphQL's current lock order, claim/duplicate handling, clinic-local time window, direct commit boundary, and legacy active-entry cap.
- Implementation: v1 checks `online_issued_count >= max_online_entries` (zero remains a closed cap) and increments only after adding a new online entry, before the existing commit. Legacy still counts waiting/called rows. T08.2a unit coverage is 7/7 and the GraphQL integration module is 17/17 on isolated SQLite fixtures.
- Gate: initial prompt routed to unrelated Telegram manager files despite the T08.2 GraphQL source anchor. The single retry with `backend/app/graphql/mutations.py` returned `narrow_override`, including the confirmed runtime file but omitting the planned regression test and evidence files. Narrow manual scope is based on the user-approved T08.2 contract; no third gate invocation.
- First-touch scope: `backend/app/graphql/mutations.py`; `backend/tests/unit/test_graphql_queue_claim_coordinator.py`; `backend/tests/integration/test_graphql_resolvers_real_db.py` for the plan-required full-schema/database check; `.ai-factory/plans/codex-admin-queue-simplification.md`; `.ai-factory/plans/admin-queue-simplification/{PROGRESS,RESUME,EVIDENCE}.md`; one factual append to `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` because this is a confirmed gate-routing miss. No other adapter/report, Telegram runtime, schema, feature flag, staging or production paths.
- Validation: fail-first reproduced two v1 failures, then GraphQL unit 7/7 and integration module 17/17 passed; scoped Ruff, pinned pre-commit, compileall, `git diff --check` and PR-body gate (19 tests) passed. Ruff format check on the legacy integration file itself reports pre-existing unrelated formatting drift; no broad formatter rewrite was applied. PostgreSQL concurrency/replay/partial-result proof remains T08.3.
- Stop if GraphQL cannot keep the counter in the same existing transaction, a required lock-order change appears, another writer is discovered, or the GraphQL legacy/v1 cap contract is ambiguous.
- T07/PR #3557 is MERGED as 425df11c7a84f0d1e7954df0d00415927212669a; exact-head applicable CI finished 27 SUCCESS / 12 SKIPPED / 0 failures. Its three named Tier-2 deferrals remain NOT_RUN; full STAGING_VALIDATION remains mandatory before deployment.
- PR #3557/T07 and PR #3571/T08.1a are confirmed MERGED. #3571 exact head was `5ac829ba203dbd3b6805eb8ad30b95d9e4aa1a31`; merge commit is `d397656c7f597d72d6a6c92676cd204aff72d4d8`. Its backend-focused local tests and exact-head applicable CI are recorded in earlier EVIDENCE entries; no v1 flag activation or deployment occurred.
- T08.1b source audit found the quota-reset risk: active-only lookup followed by a v1 zero-counter insert could shadow an inactive row with the same identity. Shared policy now checks all doctor/day/tag or resource/day rows before selecting a new v1 snapshot. Runtime constructors using the common snapshot pass the date. The Admin retention endpoint deletes only rows older than a cutoff with `days_to_keep >= 1`, so it cannot delete today's/future queue; past-day online admission is already rejected. Backup restore preserves policy/count and is a recovery path, not an admission writer. No ordinary counter/version mutation writer was found.
- Validation on current code: `test_daily_queue_creation_policy.py` — 11 passed / 1 warning; queue API, queue limits, visit confirmation, force majeure, GraphQL claim and canonical quota modules — 36 passed / 1 warning. Ruff, Ruff format, Black, compileall and `git diff --check` pass. PR-body quality gate passed (19 unit checks plus documented samples and this body). SQLite fixture only; no PostgreSQL race proof.
- PR #3572 is MERGED at `95ff3b4752a091f22f9702977d611a3b6d9f1595`; the preceding “OPEN/checks pending” text is historical and superseded by the checkpoint above and the merge evidence entry.
- Blocker: none identified for T08.1b. Remaining T08.2 adapter/report parity and T08.3 PostgreSQL concurrency/replay/partial-result proof are still required before considering v1 rollout.
- Next exact action: re-read PR #3576's live HEAD and checks after this documentation checkpoint push; compare the PR HEAD with local `git rev-parse HEAD`, wait for all applicable checks and review, and fix in-scope failures in the same PR.
- Checks to rerun after any further runtime edit: policy suite, the six queue API/limits/visit/force-majeure/GraphQL/token suites, scoped Ruff, compileall and `git diff --check`. PostgreSQL concurrency proof remains T08.3.
## Checkpoint rules for the next agent

- Read RESUME, the canonical plan, this file, DECISIONS and current-task EVIDENCE before edits; pass the exact plan path to aif-implement.
- Preserve T00–T05 MERGED and exact merge SHAs. Never reset the registry to the initial all-PLANNED template or act on obsolete T03/T05 PR_OPEN journal entries.
- Record task/subtask, actual worktree/HEAD/diff/PR, anchors, scope, mode, validation and next action before edits and after meaningful checks.
- Keep deferrals PR-specific and distinguish accepted from passed. Record required NOT_RUN checks openly.
- Preserve unrelated local changes/scratch. Do not retry blocked deletion via an alternative method or discard the source T03 docs diff after recovering it here.

- Latest review/fix checkpoint (2026-10-03): deterministic baseline reproduction confirmed a new token entry could be created at 09:00:01 after passing the 09:00 gate at 08:59:59 and waiting for the numbering row lock. Fix commit `4595d67a6e484bab8a9a59277bdaf2775e143d56` locks and refreshes the queue before the gate. Regression now rejects both tagged and untagged queues without entry or usage increment. See `EVIDENCE.md#t07-token-cutoff-lock-review-fix`.
- Next exact action: update PR body with this Admin staging result and exact-head CI, commit and push the evidence checkpoint, then inspect checks for the actual pushed HEAD. Keep merge on hold pending independent human review and remaining Tier 2 or an explicit #3557-specific deferral. Do not begin T08.
