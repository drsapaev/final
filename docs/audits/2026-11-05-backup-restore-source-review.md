# Backup / Restore Source Review — 2026-11-05

## Status and boundary

- **Type:** read-only source audit. SOURCE-OBSERVED findings; runtime reproductions pending. This document is **not a fix** and does not certify production backup health.
- **Repository/base:** `drsapaev/final`, `main` at `503cc1e28797b18ec95a772699c5c16749fdb364`.
- **Execution mode:** `direct_execute` for a single, documentation-only finding ledger. No behavior, security policy, database, credentials, or deployment configuration changed. A repair affecting production backup/restore requires the mandatory `AGENTS.md` gate.
- **Allowed:** this audit document only. **Denied:** `ops/**`, `backend/**`, `frontend/**`, production files, database access, runtime changes, migrations, and merge/deploy.
- **Skills consulted:** `.agents/skills/code-security/SKILL.md` and `.agents/skills/python-testing-patterns/SKILL.md`; canonical source is the actual Python script and operator runbook.
- **Scoped workflows:** VPS lifecycle scripts; this follow-up also inspects the distinct backend DR drill and its GitHub Actions synthetic fixture. The encrypted local-to-R2 flow remains separate. Do not infer any workflow's production schedule from another.

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

### BR-011 — P1 candidate — Non-transactional `pg_restore --clean` can leave a partly modified target

- **Source:** `ops/vps/scripts/restore_db.py:121–136` runs `pg_restore -c --if-exists <archive>` against the selected database, without `--single-transaction` or explicit atomicity requirements. The script raises on a nonzero process status, but that does **not** undo SQL changes already committed before the error.
- **Failure precondition:** a PostgreSQL restore can drop/recreate some objects and then fail restoring later objects, leaving the target database in a mixed state. This is especially consequential if an operator intentionally selected an existing/live DB; the usual separate-target guard remains a partial defense.
- **Test first:** use a disposable PostgreSQL target and synthetic archive with an intentional later restore error; record schema/data checksums before and after the failed restore and assert the target is unchanged after a transactional repair. Never use real patient data or a live DB.
- **Suggested fix:** prefer a fresh, isolated target database and a verified promotion/swap protocol; for supported archives and sizes consider `pg_restore --single-transaction --exit-on-error`. PostgreSQL documentation states `--single-transaction` gives all-or-nothing behavior and implies `--exit-on-error`: https://www.postgresql.org/docs/18/app-pgrestore.html . Validate scale/lock constraints separately.

### BR-012 — P1, conditional high-impact — DR drill can drop the source database if the target name is misconfigured

- **Source:** `backend/app/scripts/dr_drill.py`: `main()` calls `parse_source_db_url()` but stores the source DB name only in `_source_db` and never compares it with `DRILL_DB_NAME`; `drop_and_create_drill_db()` executes `DROP DATABASE IF EXISTS "<DRILL_DB_NAME>";` on the *same PostgreSQL host* using the configured source credentials. `DRILL_DB_NAME` is read from an environment variable without an allowlisted identifier check.
- **Failure precondition:** a manually configured `DRILL_DB_NAME` equal to the source database can cause the drill to drop the source database. The checked-in GitHub Actions job sets an isolated synthetic source `clinicdb` and drill target `clinic_dr_drill`; this finding is **not** an assertion that the scheduled CI workflow currently drops production.
- **Test first:** with all PostgreSQL calls mocked, configure source and drill DB names identically and assert the drill exits *before any* `psql`, `DROP`, `CREATE`, or `pg_restore` command is issued; also reject names containing SQL identifier delimiters. Do not attempt a destructive integration reproduction.
- **Suggested fix:** fail closed on same-database identity (including network aliases), require a strictly validated scratch database name and a privileged/isolated drill target that cannot access production records. Quote SQL identifiers with a proper PostgreSQL adapter rather than interpolating environment text.

### BR-013 — P1 candidate — DR drill ignores command exit statuses and may certify stale data

- **Source:** `backend/app/scripts/dr_drill.py`: `drop_and_create_drill_db()` invokes `psql` with `check=False` and never checks either exit status. `restore_backup()` invokes `pg_restore` with `check=False` and ignores `result.returncode`, failing only when `stderr` contains a line with `ERROR:`. `smoke_test_drill_db()` only queries a small fixed set of existing tables/one admin, without binding the result to this drill's backup identifier.
- **Failure precondition:** if DB drop/create fails or `pg_restore` returns nonzero with a diagnostic not containing `ERROR:`, a preexisting drill database can survive and pass the generic smoke, falsely certifying the selected backup. PostgreSQL `pg_restore` can emit diagnostics with different formats; a nonzero exit must always be treated as failure.
- **Test first:** mock unsuccessful `DROP DATABASE`, `CREATE DATABASE` and `pg_restore` calls independently; assert each causes immediate nonzero exit, no positive PASS marker, and no stale-backup success. Use an isolated synthetic DB for any true end-to-end follow-up.
- **Suggested fix:** check subprocess return codes unconditionally; add `--exit-on-error` where applicable; assert target DB is newly created and validate restored backup-specific sentinel or manifest rather than a generic surviving schema.

### BR-014 — P2 scoped evidence gap — Scheduled DR workflow verifies its own synthetic CI backup, not production archives

- **Source:** `.github/workflows/dr-drill.yml` provisions a GitHub Actions `postgres:16-alpine` service, runs migrations, seeds development/demo rows, runs `pg_dump -F c -f backups/backup_ci_test.dump`, and calls `app.scripts.dr_drill` against that freshly created artifact.
- **Consequence:** a green scheduled `DR Drill (Backup Restore Test)` proves this synthetic pipeline under CI conditions, **not** that the encrypted local-to-R2 production backup can be decrypted, retrieved, restored, and matched with uploads. This is an evidence/coverage limitation rather than a broken CI test.
- **Test first:** retain CI synthetic smoke but add a separately authorized, isolated restore rehearsal of a sanitized or approved production-equivalent backup, with source identity and storage manifest assertions. Do not copy PHI into CI or expose R2 credentials in untrusted workflow contexts.
- **Suggested fix:** label CI as synthetic restore proof; monitor real backup-chain freshness/manifest and conduct separately controlled off-host recovery drills to validate end-to-end RPO/RTO.

### BR-015 — P2, privacy/cleanup — DR drill can report success while leaving an undeleted restore database

- **Source:** `backend/app/scripts/dr_drill.py:237–250` implements `cleanup_drill_db()` with `psql -c DROP DATABASE ...`, `check=False` and no `returncode` inspection. `main():266–276` calls `_exit(0, "DR drill PASSED ...")` before cleanup in `finally`; `DRILL_KEEP_DB=1` is a separate intentional opt-out and is not the defect.
- **Consequence:** if cleanup fails (e.g. PostgreSQL connections remain open or DROP lacks permission), the process still exits successfully, leaving the restored database on the target server. When the drill is manually run against a confidential backup, retained PHI/PII may outlive the intended test. The checked-in GitHub Actions workflow uses demo records; no claim is made that CI currently leaks production data.
- **Fail-first test:** mock a clean successful restore and smoke followed by an unsuccessful DROP. Require an explicit cleanup-failure status and an operator-visible leftover-database signal. Independently test that `DRILL_KEEP_DB=1` deliberately preserves the scratch database with an unambiguous retained-state verdict.
- **Suggested fix:** inspect cleanup subprocess status, verify the database was removed (or explicitly retained by policy), and reflect failures in overall drill status. Use isolation and a bounded cleanup/connection termination policy; never silently drop a live database.

### BR-016 — P1 candidate, archive integrity/privacy — Gzip drill extraction overwrites an adjacent archive and leaves plaintext behind

- **Source:** `backend/app/scripts/dr_drill.py:152–158`: for a `*.gz` backup, `actual_path = backup_path.with_suffix("")` is written with `open(actual_path, "wb")` in the **backup's own directory**, without checking for an existing same-stem archive or creating a private temporary file. No later `finally` removes the extracted `actual_path`.
- **Failure precondition:** a directory contains `backup_a.dump.gz` and an independently valid `backup_a.dump`; running the drill against the compressed archive truncates and replaces the existing uncompressed file. Even if no collision exists, an unencrypted copy can remain after the DR test; malformed gzip streams can leave partial bytes there.
- **Fail-first test:** in a temporary synthetic directory create a `.dump` sentinel and a separate `.dump.gz` fixture with differing bytes, mock `pg_restore`, and assert the original sentinel remains identical. Repeat with truncated gzip and assert no extracted plaintext or partial file is left after failure. No real backup material.
- **Suggested fix:** decompress to a securely created private temporary artifact outside the backup directory, with restricted permissions and guaranteed `finally` cleanup, and never allow extraction to overwrite existing backup files. Keep the source archive immutable.

### BR-017 — P1 candidate, destructive cleanup — DR drill drops a database not created by this run

- **Source:** `backend/app/scripts/dr_drill.py:132–145` lets `DRILL_DB_DROP_ON_START=0` skip initial removal, but still calls `CREATE DATABASE` with `check=False`. `main():266–276` always invokes `cleanup_drill_db()` in `finally`; that function executes `DROP DATABASE IF EXISTS "<DRILL_DB_NAME>"` regardless of whether the current run created the database.
- **Failure precondition:** an existing non-source database is named as `DRILL_DB_NAME` while `DRILL_DB_DROP_ON_START=0`; the `CREATE` fails because it exists, but the run can later delete that preexisting DB in `finally`. BR-012 covers accidental source-DB collision; this distinct finding covers **ownership of a non-source preexisting target**. PostgreSQL privileges and active connections determine whether the DROP completes.
- **Fail-first test:** mock command execution with `DRILL_DB_DROP_ON_START=0` and an existing synthetic target; assert no destructive cleanup is issued when the current run did not create that target. Also test explicit `DRILL_KEEP_DB` behavior.
- **Suggested fix:** track a verified, per-run scratch DB identity and creation success; only drop a DB owned by this run and never treat `check=False` failure as ownership proof. Fail closed before restore if target provisioning fails.

### BR-018 — P1 candidate, cross-run file corruption — Failed backup deletes other workers' `*.tmp` files

- **Source:** `backend/app/services/backup_service.py:209,329–336` writes the current `backup_<type>_<timestamp>.db.tmp` and on **any** exception loops over `self.backup_dir.glob("*.tmp")` deleting every match. `backend/app/services/scheduled_backup.py` starts backups in a daemon job; `backend/app/api/v1/endpoints/backup_management.py` independently allows an Admin to request another backup.
- **Failure precondition:** two backup writers share the directory; job A fails while job B is writing its own `.tmp`. A's handler can unlink B's live temporary archive, causing B to fail or lose its output. Existing `backend/tests/unit/test_backup_atomic_and_retention.py:41–61` verifies that one failed attempt leaves no temp file but does **not** protect another worker's file.
- **Fail-first test:** use two synthetic uniquely named temporary backup files in a temporary directory; trigger A's failure with mocked `pg_dump`; assert B's bytes and path remain unchanged, and only A's own temp file is removed.
- **Suggested fix:** use an exclusive per-operation temporary filename and remove only that operation's file; add a same-directory concurrent writer regression and collision-safe final publication. Do not broaden this into deleting user-owned or other sessions' artifacts.

### BR-019 — P1 candidate, verify contract — PostgreSQL `.db[.gz]` backups are interpreted as SQLite

- **Source:** `backend/app/services/backup_service.py:206,246–262` writes PostgreSQL **custom-format** archives (`pg_dump -F c`) with `.db` filename, commonly gzip-compressed to `.db.gz`. In `verify_backup():531–557` both suffixes enter a **SQLite** verification path (`sqlite3.connect(...); PRAGMA integrity_check`) without inspecting `DATABASE_URL` or the archive magic.
- **Consequence:** valid PostgreSQL custom-format dumps typically return `{"valid": false}` with SQLite's `file is not a database`, even though an actual `pg_restore --list` could read the archive. The Admin `GET /backup/verify/{backup_filename}` consumer thus gives a misleading recovery-readiness verdict. Other formats only receive a nonzero-size test.
- **Fail-first test:** create a tiny **synthetic** PostgreSQL custom archive in disposable PostgreSQL and verify that `verify_backup` reports valid without SQLite; separately verify a corrupted PGDMP and an actual SQLite archive both take their correct format-specific paths. No real patient backups.
- **Suggested fix:** distinguish formats via verified file signature and declared provenance, use `pg_restore --list` for PostgreSQL custom archives, SQLite `PRAGMA integrity_check` only for SQLite, and ensure integrity/listability is not misrepresented as a full restore proof.

### BR-020 — P1 candidate, production integrity — Admin backup restore runs nontransactional `pg_restore -c` against the active DB

- **Source:** `backend/app/api/v1/endpoints/backup_management.py:64–82` exposes an Admin-only `POST /backup/restore/{backup_filename}`. `backend/app/services/backup_service.py:419–502` first attempts a safety backup, but then invokes `pg_restore -d <DATABASE_URL db> -c <archive>` directly, without a maintenance/quiescence gate, isolated database target, explicit all-or-nothing transaction, or postrestore identity/consistency proof.
- **Failure precondition:** live connections, archive errors, or mismatched schema/owners trigger some SQL errors after earlier objects were dropped/recreated. Checking `returncode` and having a safety backup are useful defenses, but **do not revert partially committed restore statements**. This is a separate Admin API pathway from BR-011's VPS restore script, sharing the underlying atomicity problem.
- **Fail-first test:** use only a disposable PG instance with a synthetic pre-restore dataset and intentionally incompatible restore object; assert failure leaves the original database intact and never emits success. Verify Admin RBAC positive and denied-role negative cases independently.
- **Suggested fix:** use a controlled maintenance workflow with verified source backup, isolated target, compatibility check and explicit swap/promotion; use transactional restore semantics where supported. Do not invoke on a live clinic database in a test or to collect review evidence.


### BR-021 — Withdrawn as P2; P3 log-only duplicate unlink (corrected after negative-path review)

- **Source:** `backend/app/services/backup_service.py:356–385`. The cleanup sorts archives by descending `mtime`, unlinks expired archives, then loops over `backups[self.max_backups:]` from the original snapshot. A previously removed expired file can be unlinked again, raising `FileNotFoundError` and producing an error log.
- **Correction (2026-11-05):** the original claim that this leaves **younger excess archives** and violates `MAX_BACKUPS` was **not supported**. With stable file mtimes, all expired entries are a suffix of the sorted list, so younger count-excess entries are processed **before** the repeated unlink raises. An isolated three-file synthetic reproduction confirmed the duplicate exception **and** that the configured count limit was still satisfied. Withdraw BR-021 as a retention-safety/P2 defect; at most treat it as a P3 idempotence/logging cleanup, unless new independent evidence of retention violations appears.
- **Optional regression:** create two fresh and one expired synthetic archive with `max_backups=1`; assert one file survives and avoid misleading `Error cleaning up backups` log by applying a filtered survivor list. Do not prioritize ahead of data-integrity P1 work.

### BR-022 — P2 — Interrupted compression leaves a partial published-looking `.db.gz` artifact

- **Source:** `backend/app/services/backup_service.py:340–354`: `_compress_backup()` uses `gzip.open(compressed_path, "wb")` on the final `.db.gz` path. Any exception is logged and returns `None` without removing the partly written gzip file. `create_backup():279–287` correctly retains the good uncompressed source when compression fails; however `list_backups():395–404` and `_cleanup_old_backups():359–362` also enumerate `backup_*.db*` without excluding a partial gzip.
- **Failure precondition:** compression fails after writing a gzip header or partial compressed bytes. The uncompressed backup may be good, but the invalid `.db.gz` remains visible as another backup, may count toward retention, or be selected as the latest by filename/time-based tools. The repository has no targeted compressor-failure cleanup regression found in `backend/tests/unit/test_backup_atomic_and_retention.py`.
- **Fail-first test:** inject an `OSError` after a few synthetic bytes during compression; require the source `.db` to remain intact, no visible `.db.gz` to remain on failure and no false extra list entry. Then verify success atomically publishes a complete gzip archive.
- **Suggested fix:** compress to a uniquely reserved private `.tmp`, validate successful close/size, publish without clobbering an existing archive, and delete **only** that run's partial temp file on exception.

### Regression-proof quality note — existing test does not exercise a failing dump writer

- **Source:** `backend/tests/unit/test_backup_atomic_and_retention.py:41–63`, `test_failed_dump_leaves_no_zero_byte_artifact`, monkeypatches `_get_database_url` to throw `ValueError("boom")` before a dump file is opened. Thus its passing assertion that no `*.tmp` exists does **not** exercise a subprocess that starts writing and then fails. It also cannot detect BR-018, because there is no unrelated in-flight writer.
- **Improve:** use monkeypatched `subprocess.run` to create a small synthetic partial temp archive and return a failing process status; require cleanup of that file **only**, retention of an unrelated temp file, preservation of any existing good final archive, and no success/reporting/upload. This is a test-quality limitation, not a separately numbered runtime vulnerability.

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
6. **Transactional restore and DR safety:** BR-011–013. Fail closed before any destructive operation, require a fresh target, and use synthetic negative paths for subprocess exit status.
7. **Production-backup evidence gap:** BR-014. Keep synthetic CI smoke separate from a controlled restore proof of the actual protected backup chain.
8. **DR leftover state and gzip archive safety:** BR-015–017. Preserve backup artifacts, enforce per-run database and temporary-file ownership, and report failed test DB removal.
9. **Service backup concurrency and format correctness:** BR-018–019. Protect other writers' temp files and verify PostgreSQL archives using PostgreSQL tools.
10. **Admin restore safety:** BR-020. Require isolated synthetic full-restore proof and explicit clinical maintenance/rollback policy before repairing live-restore behavior.
11. **Archive visibility:** BR-022 needs atomic compression/cleanup; BR-021 is withdrawn as P2 after an isolated counterexample check (only optional P3 logging/idempotence hygiene).

## Isolated negative-path reproductions (2026-11-05)

- **Evidence type:** controlled Python 3.13 source-**excerpt** harness, with PostgreSQL subprocesses replaced by mocks, using only synthetic files in `tempfile.TemporaryDirectory`. The harness transcribed the relevant function bodies from inspected GitHub source; it did **not** import the full repository, launch PostgreSQL, use secrets, or execute a real `DROP DATABASE`. It is **not** CI, a product-level regression suite, or proof of a corrected implementation.
- **BR-012:** with synthetic source/target name `source_clinic`, `drop_and_create_drill_db()` reaches construction of `DROP DATABASE` despite the source identity collision.
- **BR-013:** `pg_restore` stub returns `returncode=1`, stderr `pg_restore: connection interrupted` (no `ERROR:` token); `restore_backup()` still reaches completion.
- **BR-016:** with two synthetic adjacent `synthetic.dump` and `synthetic.dump.gz` files, gzip extraction overwrites the original `.dump` bytes.
- **BR-017:** with `DRILL_DB_DROP_ON_START=0` and failed stubbed `CREATE DATABASE`, cleanup still issues a `DROP DATABASE` for that same target.
- **BR-018:** the exact `for stray in backup_dir.glob("*.tmp"): stray.unlink()` cleanup pattern deletes a synthetic other-writer file.
- **BR-008:** `fail()` signals `SystemExit`; the update supervisor's `except Exception` does not catch it, so rollback is skipped.
- **BR-021 correction:** the duplicate unlink raises `FileNotFoundError`, but the synthetic sorted case still satisfies the archive count limit; prior priority/consequence overstated.
- **Output:** 7/7 **behavior scenarios observed** (six vulnerability behaviors + one corrective falsification). The harness passes only because it asserts the **current undesirable behavior**, not because a fix is present. Future real repository tests must assert the opposite (fail-first before fix, green after).
- **Limitations:** no exact repo code was executed as an installed module, no actual database changes, no true process concurrency, no genuine archive/restore E2E and no production exposure or impact verified. Reproduce in an isolated worktree and disposable PostgreSQL before shipping a source fix.

## Verification and rollback

- **Performed:** read exact GitHub `main` sources and runbooks; checked scopes, existing explicit restore guard, encrypted backup alternative, backend DR drill including cleanup/gzip, scheduled and Admin backup writers, service verification/restore, age/count retention and partial-compression unit-test coverage, and the synthetic GitHub Actions workflow; consulted repo security/testing skills. Existing source hashes for these paths were unchanged at review time; original base was `503cc1e`.
- **Not performed:** local repository `git status`, gate execution, `git diff --check`, pytest, real PostgreSQL commands, real archive creation/restore, E2E smoke, source fixes, production actions. The separately described excerpt/mocks run is not a substitute for these.
- **Stop condition:** no source repair, rollout, restore, or merge until safe isolation and mandatory gate evidence are available.
- **Rollback for this document only:** close its Draft PR or revert this one docs-only commit; no deployed behavior changes.
