# Continued Code Review — group 86 (addendum to existing Draft PR #4059)

**Review time:** 2026-11-15 Asia/Tashkent. **Pinned current main:** [`b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a`](https://github.com/drsapaev/final/commit/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a), unchanged since groups 84–85. **Read-only sources:** `backend/app/services/password_reset_service.py`, `backend/app/models/authentication.py`, `backend/app/api/v1/endpoints/password_reset.py`, current issue #4063, PRs #4074/#4075/#4064, repo AGENTS.md and code-security skill. This file is a **small separate Markdown addendum** to the cumulative 47–85 report in [the same existing Draft audit PR #4059](https://github.com/drsapaev/final/pull/4059); the 47–85 report remains intact. The earlier attempt to append the large report timed out before any commit was observed. No runtime source edits or merge by reviewer.

## One NEW independent current-main source candidate — P2 conditional `PASSRESETATOMIC-BE-001`

This is **not** an established production incident or an executed PostgreSQL concurrency reproducer. The actual on-main source offers two independently concerning paths:

1. [`password_reset_service.py:79–85`](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/backend/app/services/password_reset_service.py#L79-L85): `_find_token_row()` does a normal `SELECT...first()` by token hash, with **no `with_for_update`**, conditional claim or other single-use serialization.
2. [`password_reset_service.py:304–332`](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/backend/app/services/password_reset_service.py#L304-L332): `reset_password_with_token` reads the token and checks `used` once before updating the account. [`password_reset_service.py:355–379`](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/backend/app/services/password_reset_service.py#L355-L379): it writes `user.hashed_password` and calls **`db.commit()` at line 370**; only **after that commit** it sets `token_row.used=True`, `used_at` and calls a **second `db.commit()` at line 378**. Inline source comment that this happens "в той же транзакции" is incorrect.
3. [Model `PasswordResetToken`:132–160](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/backend/app/models/authentication.py#L132-L160) has a unique token hash and `used` Boolean, but no optimistic concurrency/atomic claim. [Public confirm endpoint](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/backend/app/api/v1/endpoints/password_reset.py#L196-L229) invokes this service and maps `TOKEN_ALREADY_USED` to 409; that response contract depends on reliable single-use behavior.

**Conditional READ COMMITTED interleaving:** sessions A/B both read the same unused, unexpired reset token; each passes the same used/expiry check. A commits a new password; B waits for the user row lock, then may commit a second password based on its already-validated token. Neither explicitly rechecks/claims the token after the user-row update; both may mark it used later and return success. **Last password wins**. Separately, if token-marking commit fails, the first commit already changed the password and the token may remain reusable even though the API reports failure. This is a plausible race and transaction-boundary bug, not a proven external exploit. Requires a valid reset token, not anonymous token guessing.

**Not a duplicate:** tracked `PASSRESET-BE-001` is phone verification throttling / user enumeration, `PASSRESET-BE-002` is token transport via URL vs header, `PASSRESET-BE-003` is password-length validation. [Open proposed fix #4075](https://github.com/drsapaev/final/pull/4075) addresses those three plus ACTIVATION IDs but does not change this service’s two-commit reset. [Issue #4063](https://github.com/drsapaev/final/issues/4063) now contains a new unchecked `PASSRESETATOMIC-BE-001` exactly once, outside historical core382 + group33 extra21.

### Required remediation/acceptance test — NOT executed

- Replace the split commit with **one explicit transaction**. Lock or atomically conditionally claim the unused and unexpired token **before** changing user credentials; recheck under lock, write password hash and `used/used_at`, commit once, rollback both on any error. Verify helper methods do not commit prematurely.
- PostgreSQL two-session/barrier test: same reset token, distinct valid passwords, force both transactions into concurrent confirm execution. **Exactly one** succeeds; loser returns consistent replay/used-token error and must not overwrite winner. Verify final password and `used=True`.
- Inject failure on token update/commit; check old password retained and no half-completed reset. Include single-session success and sequential replay tests. Authenticated session/JWT revocation remains a separate lifecycle question unless the fixing agent validates and scopes it explicitly.
- Root [AGENTS.md](https://github.com/drsapaev/final/blob/b142a30dc433dbd2486a421f1b8ba1c0a5cabb9a/AGENTS.md) mandates `ai/langgraph/scripts/run_agent_gate.ps1` for auth/security/DB changes: running ordinary pytest or green CI cannot stand in for that mandatory gate. Fixer must first obtain actual authorization and gate evidence.

## Group86 status of parallel remediation

[#4075](https://github.com/drsapaev/final/pull/4075) latest head `f170a6e69ef5a51be7e19c2bbe77ac26160fcf25` is **OPEN/unmerged**; its latest diff still includes 4 registry/workflow files **outside its declared 5-file Scope Gate**, duplicating independently open #4064. Its new `test_status_masks_license_key_and_machine_hash` now monkeypatches the real activation status function to provide synthetic values: good isolated masking check, **not** a full DB activation integration test. At last check newest [Unified CI run 43636120289](https://github.com/drsapaev/final/actions/runs/43636120289) was **in progress**. Prior [group85 direct review comment](https://github.com/drsapaev/final/pull/4075#issuecomment-6883257961) details earlier-head CI OpenAPI/generated API drift and scope issues; do not claim they persist on a new head until its jobs finish. #4074 (three template fixes) is also open/unmerged; [P2 conditional zero-active concurrent templates gap](https://github.com/drsapaev/final/pull/4074#issuecomment-6882558889) and mandatory gate issue remain. Draft #4060 remains unmerged.

## Deduplicated cumulative inventory and next agent handoff

| Metric | Group86 cumulative | This group |
| --- | ---: | ---: |
| Unique source-observed candidate IDs in owner #4063 | **404** | **+1** |
| Historical owner-checked merged verified IDs | **27** | **0** |
| Owner unchecked pending adjudication | **377** | **+1** |
| Old machine registry #4064 rows (currently open/unmerged) | **403** | **0**; must sync one new ID |
| Machine `FIXED_VERIFIED_ON_MAIN` statuses | **41** | **0** newly merged; **14** unchecked historical mismatches |
| Open #4075 activation/passreset proposed IDs | **5** (already within 377) | no merge |
| Open #4074 notification-template proposed IDs | **3** (within 377) | no merge |
| Open Draft #4060 proposed notification IDs | **24** (within 377) | no merge |
| Newly merged source fixes verified this step | **0** | **0** |

**Accounting:** core historical 382 + group33 extra 21 + new group86 extra 1 = **404**. `377 unchecked` is **not** the number of confirmed active bugs. Separately **41 machine-labelled fixed**, only **27 owner checkboxes checked**; 14 are old merged PRs still missing per-ID current-main re-adjudication. The open registry PR #4064 must add `PASSRESETATOMIC-BE-001` as `UNVERIFIED` or `CONFIRMED_OPEN` only after appropriate triage and rerun `check_registry.py --issue-check` against **404** owner IDs, before claiming 1:1 green. Do not delete/rename previous IDs.

**Reporting:** a previous fixing-agent [wave3f report actually exists IN common audit PR #4059](https://github.com/drsapaev/final/pull/4059#issuecomment-6882735990), as requested by owner. After **each next fixing step**, even failed/blocked, publish a **NEW top-level comment IN audit PR #4059** with **404 unique total**, historical and this-step fix delta, open/draft vs merged statuses, exact SHAs, tests/gate evidence, blocker and cross-link from the relevant fixing PR and #4063. Standing [protocol](https://github.com/drsapaev/final/pull/4059#issuecomment-6881110112).

**Reviewer's execution:** source inspection and docs-only report/tracker/comments; no app edit, actual PostgreSQL concurrency/test run, provider sends, sensitive clinic data, mandatory code gate run, production change or merge.
