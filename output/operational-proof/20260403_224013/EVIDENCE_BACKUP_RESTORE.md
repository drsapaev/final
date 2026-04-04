Date: 2026-04-03 22:53:52 +05:00
Host / env: Windows local proof host / proof
Command: python ops/vps/scripts/backup_db.py -> python ops/vps/scripts/restore_db.py -> python ops/vps/scripts/health_check.py -> python ops/vps/scripts/smoke_post_update.py
Outcome: PASS
Backup artifact: C:\final\output\operational-proof\20260403_224013\rehearsal_repo\output\backups\clinic_proof_src_20260403_174749.dump
Migration result: N/A
Health result: PASS
Smoke result: PASS: smoke_post_update completed successfully
Current origin: http://127.0.0.1:18080
Resolved API origin: http://127.0.0.1:18080
Resolved WS origin: ws://127.0.0.1:18080
Rollback result: N/A
Notes: Backup restored into separate target DB clinic_proof_restore. Restore smoke was executed by restarting backend against restore DB on the same host and same frontend origin. Source DB was not overwritten.
