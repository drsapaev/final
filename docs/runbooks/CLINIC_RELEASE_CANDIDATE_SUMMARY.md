# Clinic Release Candidate Summary

[← Previous Page](CLINIC_PRE_RELEASE_EVIDENCE_PACK.md) · [Back to README](../README.md) · [Next Page →](PILOT_START_CHECKLIST.md)

## Release Candidate
- Approved artifact: `clinic-release-923010c00bf3.zip`
- Imported ref: `refs/clinic-releases/clinic-release-923010c00bf3`
- Target contour: real Windows pilot host on this machine
- Pilot browser URL: `http://192.168.1.5:18080`

## What Was Proven
- Artifact import succeeds on the pilot host
- Update path succeeds on the pilot host
- Post-update smoke succeeds on the initialized host
- Backup/restore rehearsal succeeds on an isolated restore target on the same Windows host
- Frontend runtime remains same-origin on the pilot contour:
  - `CURRENT_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_API_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_WS_ORIGIN=ws://192.168.1.5:18080`
- Frontend runtime remains same-origin on the isolated restore contour:
  - `CURRENT_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_API_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_WS_ORIGIN=ws://127.0.0.1:18081`

## Operational Notes
- Latest successful pre-update backup: `C:\clinic\output\backups\clinicdb_20260405_165644.dump`
- Latest successful restore rehearsal backup: `C:\clinic\output\backups\clinicdb_20260405_181100.dump`
- Windows PostgreSQL executable support is host-install compatibility only
- The compatibility work stays in ops/wrapper and lifecycle tooling, not in business logic
- Restore rehearsal uses an isolated local PostgreSQL instance on `127.0.0.1:55433`

## Current Status
- Release candidate is tied to the tested artifact, not to generic `main`
- Evidence is recorded in [CLINIC_PRE_RELEASE_EVIDENCE_PACK.md](CLINIC_PRE_RELEASE_EVIDENCE_PACK.md)
- Named pilot contour is recorded in [CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md](CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
- Next execution step is [PILOT_START_CHECKLIST.md](PILOT_START_CHECKLIST.md) followed by day-1 evidence in [PILOT_7_DAY_EVIDENCE_PACK.md](PILOT_7_DAY_EVIDENCE_PACK.md)

## See Also
- [Clinic Pre-Release Evidence Pack](CLINIC_PRE_RELEASE_EVIDENCE_PACK.md)
- [Clinic Pilot Contour: Windows Host](CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
- [Pilot Start Checklist](PILOT_START_CHECKLIST.md)
- [Pilot 7-Day Evidence Pack](PILOT_7_DAY_EVIDENCE_PACK.md)
