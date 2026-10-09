# T10 PR #3633 Tier-2 staging rerun report

- Date: 2026-10-08T17:01:51+0500
- PR: https://github.com/drsapaev/final/pull/3633
- Exact worktree commit: 29a8ef169bb25fb1dfaa77ee3c726b515e1598e1
- Compose project: codex-t10-pr3633-current-20261008
- Outcome: PASS
- Data/auth: owned ephemeral PostgreSQL; synthetic profile, doctor and admin only; normal first-login Admin TOTP enrollment and verification; no 2FA bypass.
- Secret handling: report excludes credentials, access/enrollment tokens, TOTP seed/backup codes and generated public address code.
- Frontend provenance: launcher reports served_revision_verified=false; this PR changes no frontend runtime. No frontend revision claim is made.
- Scope: T10-specific authenticated API acceptance only. Full STAGING_VALIDATION.md, T18 and browser/UI suites remain NOT_RUN.

| Scenario | Result | Evidence |
|---|---|---|
| owned project identity | PASS | exact task-owned Compose project |
| staging backend health | PASS | HTTP 200 |
| synthetic Admin password step | PASS | HTTP 200 |
| Admin password authentication | PASS | HTTP 200; one-time enrollment required before a business token |
| normal TOTP enrollment | PASS | HTTP 200; secret returned in memory only |
| normal Admin TOTP verification | PASS | HTTP 200; session token issued only after verification |
| Admin 2FA status | PASS | HTTP 200; enabled/totp_enabled/totp_verified=True/True/True |
| create synthetic profile 3a981f562d | PASS | HTTP 200 |
| fixture profile key distinct from routing tags | PASS | profile key is absent from its cardinality-one routing tag list |
| synthetic doctor-backed daily queue seed | PASS | one active DailyQueue uses queue_tag=profile.key while profile.queue_tags=[cardiology]; zero patient entries |
| profile-key daily queue impact preview | PASS | HTTP 200; daily_queues=1; can_update=False |
| used profile binding PUT refusal | PASS | HTTP 409; profile routing binding remains protected |
| used profile presentation-only update | PASS | HTTP 200 |
| binding unchanged after rejected PUT | PASS | HTTP 200; original routing tags preserved |
| profile with historical/current queue cannot be deleted | PASS | HTTP 409 |
| create synthetic profile 3a981f562d | PASS | HTTP 200 |
| staging PostgreSQL race barrier | PASS | provision queued first; DELETE queued second on the same QueueProfile lock |
| concurrent public-address provision | PASS | HTTP 200; created=true |
| concurrent QueueProfile DELETE | PASS | HTTP 409; mutation refused after rechecking committed address |
| address remains attached after concurrent DELETE refusal | PASS | HTTP 200; active_public_addresses=1; concurrent DELETE HTTP 409 |
| profile with permanent public address cannot be deleted | PASS | HTTP 409 |
| create synthetic single department | PASS | HTTP 201 |
| provision address for synthetic single-delete department | PASS | HTTP 200; created=True |
| single department address link before delete | PASS | HTTP 200; active_public_addresses=1 |
| single department delete refused with active public address | PASS | HTTP 409; active_public_addresses=1 |
| single blocked department remains present | PASS | HTTP 200 |
| single department address remains linked after refusal | PASS | HTTP 200; active_public_addresses=1 |
| create synthetic bulkblock department | PASS | HTTP 201 |
| create synthetic bulkclean department | PASS | HTTP 201 |
| provision address for synthetic bulk-delete department | PASS | HTTP 200; created=True |
| bulk department delete refused atomically with active public address | PASS | HTTP 409; active_public_addresses=1 |
| bulk delete leaves blocked department present | PASS | HTTP 200 |
| bulk delete leaves unblocked department present | PASS | HTTP 200 |
| bulk department address remains linked after refusal | PASS | HTTP 200; active_public_addresses=1 |
| environment limitations | NOT_RUN | frontend UI/browser E2E and all ten full pre-deploy staging checks are outside this backend-only T10 slice |

No patient or production data was used.
