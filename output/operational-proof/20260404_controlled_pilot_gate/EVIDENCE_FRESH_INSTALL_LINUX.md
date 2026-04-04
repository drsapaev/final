Date: 2026-04-04
Host / env: UbuntuProof / staging
Command: python3 ops/vps/scripts/run_migrations.py && python3 ops/vps/scripts/smoke_fresh_install.py
Outcome: PASS
Backup artifact: N/A
Migration result: PASS (0021_printing_tables (head))
Health result: PASS (health_check completed successfully)
Smoke result: PASS (smoke_fresh_install completed successfully)
Current origin: http://127.0.0.1
Resolved API origin: http://127.0.0.1
Resolved WS origin: ws://127.0.0.1
Rollback result: N/A
Notes: Linux transport proof passed after target-level fixes for nginx access to frontend dist, backend migration application, Playwright browser install, Playwright system deps, and valid setup admin email. SETUP_BRANCH_ID=1, SETUP_ADMIN_USER_ID=1, SETUP_ACTIVATION_APPLIED=False.
