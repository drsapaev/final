# Windows Pilot Host Runbook

[← Previous Page](CLINIC_HOST_INSTALL_RUNBOOK.md) · [Back to README](../README.md) · [Next Page →](CLINIC_RELEASE_ARTIFACT_POLICY.md)

## Scope
- Short operator runbook for the real Windows pilot host on this machine.
- Use it for start, stop, status, backup, artifact import, safe update, smoke, and rollback.
- The pilot browser URL is `http://192.168.1.5:18080`.
- The backend URL is `http://127.0.0.1:18000`.
- The isolated restore rehearsal contour uses `http://127.0.0.1:18081` and `http://127.0.0.1:18001`.

## Verified Host Contour
| Item | Value |
|---|---|
| Host OS | Windows |
| App root | `C:\clinic` |
| Browser URL | `http://192.168.1.5:18080` |
| Backend URL | `http://127.0.0.1:18000` |
| Lifecycle config | `.env.clinic-lifecycle` |
| Wrapper | `ops/windows/clinic_host.ps1` |
| Backup dir | `C:\clinic\output\backups` |
| Log dir | `C:\clinic\output\logs` |
| Upload dir | `C:\clinic\storage\uploads` |
| Wrapper state | `output/windows/` |

## Start, Check, Stop

Start the host:

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 start
```

Check the host:

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 status
```

Expected status signals:
- backend listens on `18000`
- frontend listens on `18080`
- `PASS: health_check completed successfully`

Stop the host:

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 stop
```

## Backup Before Any Change

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 backup
```

Keep the latest backup file in `C:\clinic\output\backups`.

## Import an Approved Release

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 import-release -ArtifactFile C:\path\to\clinic-release.zip
```

Expected result:
- `IMPORTED_RELEASE_REF=...`
- `PASS: import_release_artifact completed successfully`

## Safe Update Flow

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 update -ArtifactFile C:\path\to\clinic-release.zip
```

The wrapper will:
- create a backup first
- import the release artifact
- stop the running host
- switch to the imported release ref
- start backend and frontend again
- run migrations unless skipped
- run health and post-update smoke checks
- roll back automatically if the update fails

## Backup / Restore Rehearsal

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 restore-rehearsal
```

The wrapper will:
- create a fresh live backup
- start an isolated local PostgreSQL restore instance on `127.0.0.1:55433`
- restore the backup into `clinicdb_restore`
- seed isolated restore login only on the restore target
- start restore backend on `18001`
- start restore frontend on `18081`
- run health and post-update smoke on the isolated contour
- stop the isolated restore contour after the proof completes

Expected proof lines:
- `RESTORE_BACKUP_FILE=...`
- `RESTORE_DATABASE_URL=postgresql+psycopg://clinic:<redacted>@127.0.0.1:55433/clinicdb_restore`
- `RESTORE_BACKEND_URL=http://127.0.0.1:18001`
- `RESTORE_PUBLIC_URL=http://127.0.0.1:18081`
- `PASS: restore_rehearsal completed successfully`

## Rollback

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 rollback -RollbackRef <baseline-ref>
```

Use rollback when:
- update fails
- smoke fails
- the new release does not pass health checks

## Stop Conditions
- backend port `18000` does not start listening
- frontend port `18080` does not start listening
- backup fails
- import does not print `IMPORTED_RELEASE_REF=...`
- update prints `FAIL:`
- the browser exposes `/setup` on an already initialized host

## Evidence To Save
- `status` output
- backup file path
- imported release ref
- update log
- post-update health check output

## See Also
- [Clinic Host Install Runbook](CLINIC_HOST_INSTALL_RUNBOOK.md)
- [Clinic Update Rehearsal Runbook](CLINIC_UPDATE_REHEARSAL_RUNBOOK.md)
- [Clinic Backup/Restore Rehearsal Runbook](CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md)
- [Clinic Pilot Contour: Windows Host](CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
