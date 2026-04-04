Date: 2026-04-04
Host / env: UbuntuProof / staging
Command: python3 ops/vps/scripts/run_update_rehearsal.py
Outcome: PASS
Backup artifact: /root/clinic/output/backups/clinic_app_linux_20260404_035926.dump
Migration result: PASS (run_migrations completed successfully)
Health result: PASS (health_check completed successfully)
Smoke result: PASS (smoke_post_update completed successfully)
Current origin: http://127.0.0.1
Resolved API origin: http://127.0.0.1
Resolved WS origin: ws://127.0.0.1
Rollback result: N/A
Notes: Re-ran only the failed gate condition after two helper-level corrections grounded by the first failed rehearsal: a bounded backend readiness wait in run_update_rehearsal and Python-interpreter invocation inside rollback_release to remove exec-bit ambiguity. Formal update gate then passed on a clinic-like initialized dataset from patched baseline 30162d46 to patched release 6b663320 on the Linux proof target.
