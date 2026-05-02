Date: 2026-04-03 22:53:52 +05:00
Host / env: Windows local proof host / proof
Command: python ops/vps/scripts/smoke_fresh_install.py
Outcome: PASS
Backup artifact: N/A
Migration result: PASS (pre-run on clinic_proof_src)
Health result: PASS
Smoke result: PASS: smoke_fresh_install completed successfully
Current origin: http://127.0.0.1:18080
Resolved API origin: http://127.0.0.1:18080
Resolved WS origin: ws://127.0.0.1:18080
Rollback result: N/A
Notes: Initialized fresh source DB clinic_proof_src via /setup; branch_id=1; admin_user_id=1; activation_applied=False. Helper false negatives were fixed during proof: health payload accepted {ok:true} and frontend root check now uses browser-style Accept header.
