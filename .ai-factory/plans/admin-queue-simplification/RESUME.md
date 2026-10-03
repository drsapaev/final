# Resume — admin queue simplification

Plan version: 2.3
Last updated: 2026-10-03T19:18:04+05:00, Asia/Tashkent
Execution permission: IMPLEMENTATION_ACTIVE; user confirmed #3557 merged and said continue. T07 is MERGED; T08.1a runtime/tests are committed as e0ebcfb756cf1ff31093c5905aed9b937a2fa769 and locally validated against base origin/main 473138216. The branch was fast-forwarded over a docs-only upstream commit before runtime edits. No production deployment or v1 activation is authorized.

## First read

1. Repo `AGENTS.md`, `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md`, and `docs/runbooks/AGENT_SESSION_WORKTREES.md`.
2. [Canonical detailed plan](../codex-admin-queue-simplification.md), especially T07 and the preserved invariants.
3. [PROGRESS.md](PROGRESS.md), [DECISIONS.md](DECISIONS.md), then the latest T08.1a evidence and the historical T07 [EVIDENCE.md](EVIDENCE.md#t07-served-frontend-exact-head-provenance).
4. Before ownership-sensitive changes: `docs/devbrain/PROJECT_MEMORY.md`, `DEVBRAIN_STATUS.md`, `MEMORY_ROUTING.md`, `DEV_BRAIN_ROLE_MAP.md`, the direction contract, and ADR-001.

## Verified current checkpoint

- T00–T06.2 are MERGED. PR #3546 / T06.2 is confirmed merged at `2026-10-01T17:48:53Z`: merge commit `b804a71a6bad22400324e2236a3221317eac3158`, exact PR head `2c6c04f996fdced70c8b8ecf1a8f24452336e83e`, base `1358c70bf4723d151861a9ef135bba147b118fee`. Applicable CI passed on that exact head. Focused local tests: 54 passed, 1 warning, SQLite only. Path-aware skips are not passes; PG runtime/staging/browser validation is NOT_RUN. The v1 creation flag remains default-off.
- T05 / PR #3543's staging deferral was separately accepted under the user's delegated decision. It contributes no staging proof and is not inherited by another PR. See DECISIONS and EVIDENCE; T18/pre-deploy still owns the deferred scenarios.
- Last verified exact PR code/evidence/CI HEAD: `ec3d214a6b00162fc9b910e181af77f0142b9e2c`; base `f1be5697dbc487d792e8d5ae60db53c079bbe638`. Runtime code is unchanged from reviewed `037c6493`. The PostgreSQL cutoff lock-wait, normal synthetic Admin 2FA/routes/settings run, and exact-head frontend provenance check passed. On ec3d214a, a clean worktree built image `sha256:d92ab5afec5c4d375004e361435e5be9e0a1684b90e2aa2494f15f3b5c618328`; every one of 255 extracted static files matched its HTTP response from the owned staging frontend. Evidence JSON is in ignored `output/staging/frontend-attestation-ec3d214a/attestation.json`. The helper's generic `served_revision_verified` remains false; the independent checksum artifact is the provenance proof. Exact-head CI on ec3d214a passed Backend, Frontend E2E, unit/build/lint, PR Required Gate, parity, docs, quality, context, role and applicable security checks. Skips are not passes. Tier 2 remains partial: `admin-navigation.spec.ts`, `queue-system.spec.ts`, `panel-qa-admin-live.spec.ts` and full `STAGING_VALIDATION.md` are NOT_RUN. The bounded #3557 deferral was ACCEPTED under user delegation on 2026-10-03; three named specs remain NOT_RUN, with owner/resume conditions in DECISIONS. Independent human GitHub APPROVED is absent.

## Active step — T08.1a, canonical token admission quota

- Current worktree: C:\final\_wt_aqs_t081_quota; branch codex/aqs-T081-online-quota; base 473138216ae040c1c7fa60e92334d33ef8a0b856; runtime/test commit e0ebcfb756cf1ff31093c5905aed9b937a2fa769. Evidence docs are changed but not yet committed. PR #3557 merge commit is 425df11c7a84f0d1e7954df0d00415927212669a. The branch was fast-forwarded across a docs-only upstream commit before code edits.
- Canonical owner: backend/app/services/queue_svc/_operations.py. queue_domain_service.py:allocate_ticket is only a compatibility facade. The gate misroute and its single permitted known-root retry are recorded in EVIDENCE and ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md. Do not repeat the gate or edit gate code in this quota PR.
- Local implementation: v1 check_queue_limits compares persisted online_issued_count with max_online_entries exactly, including zero. Doctor selection uses the same quota semantics for v1, while legacy selection/enforcement continue using active waiting/called entries. join_queue_with_token increments only after creating a new entry, under the existing DailyQueue lock and before the current commit/flush. Existing duplicate return and staff create_queue_entry paths do not increment; there is no decrement path.
- Focused coverage: zero/exhausted/available cap; legacy fallback; v1 doctor-selection parity against active desk rows; duplicate replay no-increment; new token entry count increment; a second request at the last-slot boundary is rejected; caller-owned commit=False rollback removes entry/counter/token usage together.
- Validation on current working tree: test_queue_join_claim_coordinator.py + test_online_admission_window.py + test_qr_least_loaded_routing.py: 64 passed, 1 warning using test-fixture SQLite. Ruff check, compile, git diff --check PASS. Ruff format check passes for the test file. The legacy _operations.py format check still reports broad formatter diffs in untouched regions; no unrelated whole-file reformat was applied.
- NOT_RUN: PostgreSQL last-slot concurrency, adapter/report parity (including GraphQL), identity/recreation protection, staging/browser and deployment checklist. These remain T08.1b/T08.2/T08.3/T18 obligations. QUEUE_POLICY_V2_CREATION_ENABLED remains default-off.
- Next exact action: commit the reviewed plan/evidence checkpoint, push codex/aqs-T081-online-quota, then create T08.1a PR against current origin/main. Wait for exact-head CI/review; do not begin T08.1b/T08.2 or enable the flag until this PR cycle completes.
- Stop if another admission writer enters this sub-scope, a replay is charged, the counter cannot share the existing transaction, or lock ordering must change. PostgreSQL proof is mandatory before considering v1 rollout.
## Merge, staging and rollout guardrails

- Continue one small PR cycle at a time from fresh `origin/main`; verify actual HEAD, diff, PR and checks before each merge. The user's “мержай и продолжай” authorizes continuing the planned cycles, but no deployment or flag activation.
- Report exactly which local/GitHub/staging/PG checks passed, failed, skipped or were not run. Do not call skips “pass”. If an explicitly required PG/staging gate is unavailable, record the limitation and follow the plan's stop/deferral rules; never substitute production.
- Do not enable `QUEUE_POLICY_V2_CREATION_ENABLED` in production or staging as part of T07. Do not restart production.
- The accepted #3543 deferral resumes at T18/pre-deploy: synthetic admin settings save → fresh command defaults → unchanged existing daily snapshot, affected admin/queue E2E, cold/repeat first-content timing, and applicable local PG coverage. Run all 10 items of `docs/runbooks/STAGING_VALIDATION.md` before any production rollout and record each item separately.

## Historical worktree preservation

- Earlier T03/T05/T06 worktrees and scratch were preserved per their checkpoints. Do not delete, clean, reset or rewrite them while doing T07. Use only this worktree for T07 code.
- Older PR-open text in timestamped EVIDENCE is historical. Current state is the header/table in PROGRESS and this RESUME; the latest appended exact-head review entry supersedes earlier T07 CI/review observations.
- T07 runtime code originated at `84ec10b40`; later commits include OpenAPI preservation, deterministic test setup, review fixes `f26a79fe`, `4595d67a`, and `c92862b7`, plus QR response-contract follow-up `a8ce8a6d`. Earlier PR heads `e7be14cd`, `1e74d645`, `ead1dbf7`, and `0c258a007` each had their own check sets; the latest exact-head result is recorded in the final T07 checkpoint of `EVIDENCE.md`. Path-aware skips are not passes. A Codex technical COMMENT exists; independent human review is absent. The PR-specific bounded deferral acknowledgement is checked under user delegation; this is not a GitHub self-approval. The branch is based on `cc446a85654f`; work only in the T07 worktree, never rebase in `C:\final`.
