Date: 2026-04-04
Gate: Controlled Pilot Gate / update rehearsal
First failing signal: post-deploy health gate

Expected behavior:
- After `python3 ops/vps/scripts/deploy_release.py` and `python3 ops/vps/scripts/run_migrations.py`,
  the updated release should reach a ready state on `http://127.0.0.1:18000`.
- `python3 ops/vps/scripts/health_check.py` should return `PASS: health_check completed successfully`.
- If update handling fails later, rollback must be unambiguous and executable through the formal wrapper.

Actual behavior:
- The first failing signal was:
  `FAIL (Failed to reach http://127.0.0.1:18000/api/v1/health: [Errno 111] Connection refused)`
- This happened immediately after deploy+migrations during the formal update rehearsal on
  baseline `8fa30e68` -> release `31379956`.
- The formal rollback path then also failed with:
  `PermissionError: [Errno 13] Permission denied: '/root/clinic/ops/vps/scripts/deploy_release.py'`

Classification:
- Primary classification: transport
- Secondary classification: release helper / rollback execution path

Grounded corrective action:
- Add bounded backend readiness wait before the formal update health gate.
- Invoke rollback helper scripts via the Python interpreter instead of relying on exec bits.
