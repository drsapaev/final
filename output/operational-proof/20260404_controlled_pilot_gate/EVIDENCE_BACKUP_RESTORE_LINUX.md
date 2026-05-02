Date: 2026-04-04
Host / env: UbuntuProof / staging + restore target on 127.0.0.1:18001 / 127.0.0.1:18081
Command: python3 ops/vps/scripts/run_backup_restore_rehearsal.py
Outcome: PASS
Backup artifact: /root/clinic/output/backups/clinic_app_linux_20260404_024841.dump
Migration result: N/A
Health result: PASS (health_check completed successfully)
Smoke result: PASS (smoke_post_update completed successfully)
Current origin: http://127.0.0.1:18081
Resolved API origin: http://127.0.0.1:18081
Resolved WS origin: ws://127.0.0.1:18081
Rollback result: N/A
Notes: Separate restore target passed only after rebinding restore DB to the source schema owner role (clinic_app) while keeping a separate restore database (clinic_restore_linux). Initial restore attempt with clinic_restore role failed on pg_restore ownership SET ROLE errors.
