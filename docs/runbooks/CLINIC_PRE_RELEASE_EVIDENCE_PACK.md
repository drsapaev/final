# Clinic Pre-Release Evidence Pack

[← Previous Page](CLINIC_RELEASE_ARTIFACT_POLICY.md) · [Back to README](../README.md) · [Next Page →](CLINIC_RELEASE_CANDIDATE_SUMMARY.md)

## Scope
- Pre-release evidence for the real Windows pilot host rehearsal on this machine.
- This page records the exact approved artifact that was imported, updated, and smoke-validated before pilot execution.

## Candidate
| Item | Value |
|---|---|
| Artifact | `clinic-release-923010c00bf3.zip` |
| Imported ref | `refs/clinic-releases/clinic-release-923010c00bf3` |
| Host OS | Windows |
| Pilot browser URL | `http://192.168.1.5:18080` |
| Backend URL | `http://127.0.0.1:18000` |
| Database URL | `postgresql+psycopg://clinic:<redacted>@127.0.0.1:5432/clinicdb` |
| Backup dir | `C:\clinic\output\backups` |
| Latest successful pre-update backup | `C:\clinic\output\backups\clinicdb_20260405_165644.dump` |
| Latest successful restore rehearsal backup | `C:\clinic\output\backups\clinicdb_20260405_181100.dump` |

## Verified Rehearsal
- `import-release -ArtifactFile C:\final\output\release-artifacts\clinic-release-923010c00bf3.zip`
- `update -ArtifactFile C:\final\output\release-artifacts\clinic-release-923010c00bf3.zip`
- `smoke-post-update`
- `restore-rehearsal`

## Post-Update Runtime Proof
- `PASS: health_check completed successfully`
- `PASS: smoke_post_update completed successfully`
- `CURRENT_ORIGIN=http://192.168.1.5:18080`
- `RESOLVED_API_ORIGIN=http://192.168.1.5:18080`
- `RESOLVED_WS_ORIGIN=ws://192.168.1.5:18080`

## Restore Rehearsal Proof
- `PASS: restore_rehearsal completed successfully`
- Restore target database: `postgresql+psycopg://clinic:<redacted>@127.0.0.1:55433/clinicdb_restore`
- Restore backend URL: `http://127.0.0.1:18001`
- Restore public URL: `http://127.0.0.1:18081`
- Restore smoke result: `PASS: smoke_post_update completed successfully`
- Restore runtime proof:
  - `CURRENT_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_API_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_WS_ORIGIN=ws://127.0.0.1:18081`
- Restore login smoke: PASS using isolated restore admin seed on the restore-only database

## Host State After Rehearsal
- Backend is listening on `18000`
- Frontend is listening on `18080`
- `ops/windows/clinic_host.ps1 status` passes on the initialized host
- Same-origin frontend runtime was preserved on the pilot contour

## Pilot-Specific Compatibility Notes
- Windows PostgreSQL executable support is treated as host-install compatibility only
- Compatibility stays inside ops/lifecycle tooling, not business logic
- Relevant host-compat paths:
  - `ops/windows/clinic_host.ps1`
  - `ops/vps/scripts/clinic_lifecycle_common.py`
  - `ops/vps/scripts/backup_db.py`
  - `ops/vps/scripts/restore_db.py`

## Go/No-Go Readiness
- Approved artifact imported successfully
- Safe update path executed successfully on the real Windows pilot host
- Backup/restore path executed successfully to an isolated restore target on the same Windows host
- Post-update smoke passed on the initialized host
- Pilot can proceed to the day-1 checklist on the named Windows contour unless scope or contour changes

## See Also
- [Clinic Release Candidate Summary](CLINIC_RELEASE_CANDIDATE_SUMMARY.md)
- [Clinic Pilot Contour: Windows Host](CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
- [Clinic Windows Pilot Host Runbook](CLINIC_WINDOWS_PILOT_HOST_RUNBOOK.md)
- [Pilot Start Checklist](PILOT_START_CHECKLIST.md)
