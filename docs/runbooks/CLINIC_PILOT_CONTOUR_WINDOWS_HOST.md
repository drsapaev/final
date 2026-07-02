# Clinic Pilot Contour: Windows Host

[← Previous Page](CLINIC_RELEASE_CANDIDATE_SUMMARY.md) · [Back to README](../README.md) · [Next Page →](PILOT_START_CHECKLIST.md)

## Purpose
- Name the one real clinic contour that is allowed for the limited pilot.
- Keep the pilot intentionally narrow, observable, and reversible on this Windows host.

## Contour
- Clinic name: Doktor KosMed clinic
- Host machine: `DESKTOP-SNC8G9T` (this Windows pilot host)
- Deployment type: host install
- Official clinic URL: `http://192.168.1.5:18080`
- Backend URL: `http://127.0.0.1:18000`
- Live database: `clinicdb` on local PostgreSQL `127.0.0.1:5432`
- Approved release artifact: `clinic-release-923010c00bf3.zip`
- Approved imported ref: `refs/clinic-releases/clinic-release-923010c00bf3`
- Backup location: `C:\clinic\output\backups`
- Log location: `C:\clinic\output\logs`
- Upload location: `C:\clinic\storage\uploads`
- Rollback baseline: `refs/clinic-releases/clinic-release-923010c00bf3`

## URL Rule
- `localhost` may be used for backend health or isolated restore checks only.
- `localhost` is not the official clinic URL.
- The official clinic URL for the live pilot is `http://192.168.1.5:18080`.

## Pilot Users
- Admin user: Dr. Sapaev (`admin`)
- Registrar user: Maftuna (`registrar`)
- Doctor users:
  - Dr. Ahmad (`derma`)
  - Dr. Sapaev (`cardio`)
  - Dr. Hamidulla (`dentist`)
- Cashier user: Shahlo (`cashier`)
- Lab user: Muhayyo (`lab`)

## Enabled Scope
- login
- registrar
- queue
- cardiologist core workflow
- dermatologist core workflow
- dentist core workflow
- lab core workflow
- cashier core workflow
- patient lookup and update

## Disabled Or Deferred
- optional external integrations
- broad automation changes
- large UI or workflow expansion
- non-essential modules not already proven in rehearsal

## Readiness Notes
- Latest update-path backup completed: `C:\clinic\output\backups\clinicdb_20260405_165644.dump`
- Fresh live baseline backup completed: `C:\clinic\output\backups\clinicdb_20260405_191852.dump`
- Latest restore rehearsal backup completed: `C:\clinic\output\backups\clinicdb_20260405_181100.dump`
- Update rehearsal completed: PASS on `2026-04-05`
- Restore rehearsal completed: PASS on `2026-04-05`
- Live pilot opening confirmed: PASS on `2026-04-06`
- Post-update runtime proof:
  - `CURRENT_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_API_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_WS_ORIGIN=ws://192.168.1.5:18080`
- Restore runtime proof:
  - `CURRENT_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_API_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_WS_ORIGIN=ws://127.0.0.1:18081`
- Controlled pilot gate status: ready for limited pilot on the named Windows host contour

## Acceptance
This contour is ready only when:
- the host and clinic URL are named
- the scope and pilot group are explicitly limited
- the backup, update, and restore paths are proven
- the rollback baseline is known
- the operator follows [Pilot Start Checklist](PILOT_START_CHECKLIST.md) before opening day 1
