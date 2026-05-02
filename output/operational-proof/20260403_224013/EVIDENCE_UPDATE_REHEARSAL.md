Date: 2026-04-03 22:53:52 +05:00
Host / env: Windows local proof host / proof
Command: backup_db -> git checkout a34c713f888ceeaf1829a39d6cca01a289b583c7 -> run_migrations.py -> health_check.py -> smoke_post_update.py -> git checkout 8fa30e68523b8e61d02760ef07225f0f163a23c4 -> health_check.py -> smoke_post_update.py
Outcome: PASS
Backup artifact: C:\final\output\operational-proof\20260403_224013\rehearsal_repo\output\backups\clinic_proof_src_20260403_175140.dump
Migration result: PASS: run_migrations completed successfully
Health result: PASS (post-update and post-rollback)
Smoke result: PASS: smoke_post_update completed successfully
Current origin: http://127.0.0.1:18080
Resolved API origin: http://127.0.0.1:18080
Resolved WS origin: ws://127.0.0.1:18080
Rollback result: PASS (baseline ref 8fa30e68523b8e61d02760ef07225f0f163a23c4 restored and smoke passed)
Notes: Update proof used isolated proof-repo refs: baseline=8fa30e68523b8e61d02760ef07225f0f163a23c4, update=a34c713f888ceeaf1829a39d6cca01a289b583c7. This exercised checkout, migration, post-update smoke, and rollback on an initialized DB. Limitation: Windows local proof did not exercise Linux deploy_host.sh/systemd/nginx transport; update ref was a harmless proof marker commit, not a feature-heavy release delta.
