# Clinic Evidence Pack Template

Use one row per rehearsal or rollout stage.

## Fields
- Date
- Host / env
- Release artifact / ref
- Command
- Outcome
- Backup artifact
- Migration result
- Health result
- Smoke result
- Current origin
- Resolved API origin
- Resolved WS origin
- Rollback result
- Notes

## Suggested Format

```text
Date: 2026-04-03
Host / env: clinic-host-01 / production
Release artifact / ref: refs/clinic-releases/release-2026-04-04
Command: python3 ops/vps/scripts/run_update_rehearsal.py
Outcome: PASS
Backup artifact: /opt/clinic/output/backups/clinic_20260403_021500.dump
Migration result: PASS
Health result: PASS
Smoke result: PASS
Current origin: https://clinic.example.com
Resolved API origin: https://clinic.example.com
Resolved WS origin: wss://clinic.example.com
Rollback result: N/A
Notes: initialized deployment stayed on /setup=false after update
```

## Evidence Rules
- Record the exact command that was run.
- Record the exact approved release artifact or imported release ref that was deployed.
- Copy the exact PASS/FAIL line from the script output.
- Save backup filenames as emitted by `BACKUP_FILE=...`.
- Save `CURRENT_ORIGIN=...`, `RESOLVED_API_ORIGIN=...`, and `RESOLVED_WS_ORIGIN=...` exactly as emitted by the smoke output.
- Save the rollback ref when used.
- If a rehearsal fails, include the first `FAIL:` line that stopped it.
