# Backup / Restore Source Review — 2026-11-05

## Status and boundary

- **Type:** read-only source audit. SOURCE-OBSERVED findings; runtime reproductions pending. This document is **not a fix** and does not certify production backup health.
- **Repository/base:** `drsapaev/final`, `main` at `503cc1e28797b18ec95a772699c5c16749fdb364`.
- **Execution mode:** `direct_execute` for a single, documentation-only finding ledger. No behavior, security policy, database, credentials, or deployment configuration changed. A repair affecting production backup/restore requires the mandatory `AGENTS.md` gate.
- **Allowed:** this audit document only. **Denied:** `ops/**`, `backend/**`, `frontend/**`, production files, database access, runtime changes, migrations, and merge/deploy.
- **Skills consulted:** `.agents/skills/code-security/SKILL.md` and `.agents/skills/python-testing-patterns/SKILL.md`; canonical source is the actual Python script and operator runbook.
- **Scoped workflows:** VPS lifecycle scripts, separate from the local encrypted `ops/scripts/backup_local_to_r2.py` flow. Do not infer either flow's production schedule from the other.

## Findings

### BR-001 — P1 — SQL restore can succeed despite failed statements

- **Source:** `ops/vps/scripts/restore_db.py:107–119` runs `psql -f <archive>` with no `ON_ERROR_STOP=1`; `ops/vps/scripts/clinic_lifecycle_common.py:247–277` checks the **process** return code.
- **Failure:** default `psql` keeps processing after SQL errors and can exit normally. The wrapper then prints a success marker, despite incomplete schema/data. This affects `.sql` and `.sql.gz`; the custom-format `pg_restore` path is separate.
- **Test first:** on a disposable PostgreSQL target use a synthetic `.sql` with one invalid statement between valid statements; assert the current restore CLI can emit success, then require nonzero exit, no success marker and intact target after repair.
- **Suggested fix:** `psql -X -v ON_ERROR_STOP=1` with a considered transaction strategy, and a regression test. `pg_restore -e --single-transaction` is a separate integrity improvement subject to compatibility with supported archives.

### BR-002 — P1 candidate — Destructive rehearsal target identity is only partly checked

- **Source:** `ops/vps/scripts/run_backup_restore_rehearsal.py:77–78` compares raw `DATABASE_URL` strings; `ops/vps/scripts/restore_db.py:44–67` compares `host.lower(), port, name` and allows `CONFIRM_RESTORE_DB=1` bypass.
- **Failure precondition:** two distinct DSNs may resolve to the same PostgreSQL database (e.g. `localhost` versus `127.0.0.1`, or DNS aliases). Raw-string/host-name comparisons do not prove isolation. If the confirmation flag is inherited, the second check is bypassed.
- **Test first:** use mocked subprocess and synthetic URL variants to establish whether a restore command is reached for the same target via aliases and with inherited confirmation; then test a safe, explicit target-identity proof.
- **Suggested fix:** fail closed unless target isolation is proven, with dedicated deliberate-live-restore workflow and confirmation not inherited by rehearsal. Do **not** test destructively against production. Priority is conditional until end-to-end reproduction.

### BR-003 — P1 candidate — HTTP smoke is not bound to the restored database

- **Source:** `ops/vps/scripts/run_backup_restore_rehearsal.py:80–104` passes arbitrary `RESTORE_BACKEND_URL` and `RESTORE_PUBLIC_URL`; `ops/vps/scripts/health_check.py:29–61` probes health/docs/frontend/setup; `ops/vps/scripts/smoke_post_update.py:108–112` probes health/origins/login.
- **Failure precondition:** if operator points `RESTORE_BACKEND_URL` at a healthy non-restored instance, these checks can succeed without demonstrating use of `RESTORE_DATABASE_URL`. The runbook requires a connected restore backend as a **precondition**, but the script does not verify the binding.
- **Test first:** synthetic isolated DB A, backend B bound to DB B; assert rehearsal must refuse to certify DB A after restore. Avoid production data.
- **Suggested fix:** establish a non-secret, verifiable identity binding or restore-specific sentinel validated through the actual backend; independently verify restored record invariants.

### BR-004 — P1 scoped gap — Rehearsal does not restore upload/attachment state

- **Source:** `ops/vps/scripts/run_backup_restore_rehearsal.py:69–105` only invokes DB dump/restore and HTTP smoke. `docs/runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md` acceptance checks DB and service only. `docs/runbooks/CLINIC_STATE_SEPARATION_AUDIT.md` lists uploads as a separate mutable bucket.
- **Consequence:** a green rehearsal does **not** establish that EMR/lab attachments or uploaded media can be recovered, or that restored database references resolve to restored files. A separate manual uploads example exists in `docs/BACKUP_RESTORE_PROCEDURE.md`, but is not covered by this wrapper.
- **Test first:** use synthetic DB metadata referring to a synthetic file, restore DB+storage to separate roots and verify byte/checksum and reference integrity; delete one synthetic object and require failure.
- **Suggested fix:** coordinated DB/storage backup manifest, independent restore target, consistency readback, and evidence for both. This finding is scoped to this VPS rehearsal; it is **not** a claim that no other storage backup exists.

### BR-005 — P2 — Public URL auto-detection can defeat restore-scoped URL selection

- **Source:** `ops/vps/scripts/run_backup_restore_rehearsal.py:87–103` sets `PUBLIC_URL=RESTORE_PUBLIC_URL`; `ops/vps/scripts/clinic_lifecycle_common.py:227–235` defaults `CLINIC_AUTO_DETECT_PUBLIC_URL` to true and returns an auto-detected LAN address instead of the supplied `PUBLIC_URL`.
- **Consequence:** public-site health may probe the wrong frontend. This further weakens BR-003's evidence; it does not by itself prove that production traffic is affected.
- **Test first:** explicitly set `PUBLIC_URL` to a synthetic restore URL and leave auto-detect unset. Assert the restore health probe targets that URL, not the auto-detected LAN endpoint.
- **Suggested fix:** force explicit restore-scoped origin resolution during rehearsal, or fail if auto-detect would override an explicit restore URL.

### BR-006 — P2, conditional — VPS DB backup artifacts lack explicit at-rest protection contract

- **Source:** `ops/vps/scripts/backup_db.py:41–72` writes a plain custom-format `.dump` via `pg_dump -F c -f` to a configurable path. This script does not encrypt, set restrictive file permissions, or assert backup file ownership/mode.
- **Consequence:** depending on deployment filesystem and umask, an artifact holding confidential records may be accessible beyond its intended operators. The **separate** local-to-R2 script uses Fernet encryption, so this is not a global assertion about every backup path.
- **Test first:** on a disposable host with representative umask verify artifact permission/owner, destination and access by a different unprivileged account; assess encryption-at-rest and documented key recovery.
- **Suggested fix:** define/enforce restrictive permissions and directory policy, and choose encryption with separately backed-up keys where required. Avoid accidental disclosure of plaintext archives during testing.

### BR-007 — P2 — Failed gzip expansion can leave plaintext temporary archive

- **Source:** `ops/vps/scripts/restore_db.py:69–78` creates an uncompressed temporary file; `main():103` calls the helper **before** entering the `try/finally` at lines 105–139.
- **Failure:** malformed or truncated `.gz` may raise during decompression after temporary file creation, skipping the cleanup `finally` in `main`. An incomplete, potentially sensitive plaintext file can remain in the OS temp directory.
- **Test first:** use a deliberately truncated synthetic compressed SQL archive; monkeypatch temporary-directory selection; assert no leftover file on failure, and no restore invocation.
- **Suggested fix:** own creation/decompression and restore inside the same `try/finally`, with restrictive tempfile permissions.

### BR-008 — P1 — Backend-readiness timeout escapes rollback handler

- **Source:** `ops/vps/scripts/run_update_rehearsal.py:42–62` ends `_wait_for_backend_ready()` by calling `fail(...)` after timeout, after deployment/migration at lines 87–89; `ops/vps/scripts/clinic_lifecycle_common.py:45–47` implements `fail()` with `raise SystemExit(code)`. The handler at `run_update_rehearsal.py:92–103` catches only `Exception`.
- **Failure:** `SystemExit` is a `BaseException`, not an `Exception`; therefore a timeout after release deployment/migration bypasses the `except Exception` rollback block entirely. No automatic release rollback occurs on this path despite the runbook's general rollback assertion.
- **Test first:** with synthetic subprocess/mocked health responses, force `_wait_for_backend_ready` to reach its timeout after a successful fake migration; assert the pre-fix behavior skips `rollback_release.py`; require a bounded, explicitly handled failure and one rollback invocation after repair. Do not use live deployment.
- **Suggested fix:** make the readiness helper signal the same ordinary lifecycle exception handled by the rollback supervisor (do **not** broadly swallow `KeyboardInterrupt` / `SystemExit`), and verify rollback errors remain visible.

### BR-009 — P1 candidate — Release rollback can report success with a migrated database

- **Source:** `ops/vps/scripts/run_update_rehearsal.py:77–103` creates a pre-update backup, upgrades release and database, then on caught errors runs `rollback_release.py` **without** restoring the backup. `ops/vps/scripts/rollback_release.py:24–34` rolls back the code and optionally calls `run_migrations.py`. `ops/vps/scripts/run_migrations.py` runs `alembic upgrade head`, not a migration downgrade.
- **Failure precondition:** after an incompatible forward migration, restoring only an older code checkout can leave an older application running against a newer schema. The wrapper may print `rolled back` although database compatibility was not established. The update runbook separately instructs **manual** backup restoration for migrations that are not backward-safe; the automatic script does not implement that conditional step.
- **Test first:** isolated synthetic PostgreSQL with a deliberately non-backward-compatible sample migration; simulate smoke failure and assert no `rollback complete` verdict until schema compatibility or a verified restore is proven. No production DB copies in test/staging.
- **Suggested fix:** distinguish `code rollback` from `full DB-compatible rollback` in output; require an explicit operator-safe schema rollback/restore protocol, including snapshot protection and consistency checks. Never auto-restore a live database merely because smoke failed.

### BR-010 — P1 candidate — Backup filename reuse can destroy an earlier good archive

- **Source:** `ops/vps/scripts/backup_db.py:44–50` accepts a caller-supplied `BACKUP_FILE` without checking whether it already exists. Its autogenerated name has only **second-level** precision; `backup_db.py:52–69` runs `pg_dump -F c -f <path>` without an atomic temporary artifact or non-clobber reservation.
- **Failure precondition:** a reused `BACKUP_FILE` or two concurrent calls within one second can point to the same path. A later failed dump may truncate/replace the previous good archive before the caller learns of failure. For default filenames, demonstrate same-second collision without running real dumps; for file truncation, use a mocked failing writer with a synthetic previous archive.
- **Test first:** identical timestamp and database name on two invocations; explicit existing backup file; simulate failing writer and assert original bytes/checksum remain untouched. Validate success path publishes an independent new filename after archive verification.
- **Suggested fix:** write to a uniquely reserved private temporary path and atomically publish to a non-existing final name; include high-resolution timestamp/random suffix, collision-safe create, fail-closed validation, and no deletion/overwrite of good backup on error.

## Existing defenses / limits

- `restore_db.py` already has a safety check for matching normalized host/port/database; BR-002 addresses aliases and the explicit bypass, not an absent check.
- `run_command()` uses `subprocess.run(args)` with argument arrays and tests the return code. No shell command injection is alleged.
- The encrypted local-to-R2 database backup and its remote-verification manifest are a **different** workflow; do not replace its verified behavior based on this review.
- `pg_restore` normally returns a nonzero status if errors occurred even when configured to continue; BR-001 specifically concerns `psql`.
- No real patient data, database snapshots, secrets, or production hosts were accessed.

## Proposed repair sequence (separate gated fix PRs)

1. **Fail-closed correctness:** BR-001, BR-007 and BR-010, with synthetic SQL/gzip/collision cases. Verify direct helper behavior and negative cases before repair.
2. **Restore isolation/identity:** BR-002, BR-003, BR-005. Require mandatory production/security gate and a clean disposable PostgreSQL integration test.
3. **Full clinic recovery:** BR-004, with synthetic upload roots and DB/file consistency evidence; define storage ownership and failure semantics first.
4. **Artifact confidentiality:** BR-006 after confirming actual deployment permissions and encrypted backup/key-recovery requirements.
5. **Update rollback supervision:** BR-008 and BR-009, with synthetic readiness timeout, rollback verification and schema compatibility gates; never restore a production DB automatically.

## Verification and rollback

- **Performed:** read exact GitHub `main` sources and runbooks; checked scopes, existing explicit restore guard and alternate encrypted backup workflow; confirmed PostgreSQL `psql` error-handling contract from official docs. Source anchors refer to main `503cc1e`.
- **Not performed:** local `git status`, gate execution, `git diff --check`, pytest, PostgreSQL commands, archive creation, real restore, E2E smoke, CI, protected source changes, production actions.
- **Stop condition:** no source repair, rollout, restore, or merge until safe isolation and mandatory gate evidence are available.
- **Rollback for this document only:** close its Draft PR or revert this one docs-only commit; no deployed behavior changes.
