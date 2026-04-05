# Pilot Day-1 Go / No-Go: Windows Host

[← Previous Page](PILOT_START_CHECKLIST.md) · [Back to README](../README.md)

## Status
- `GO` for limited pilot opening on `2026-04-05`

## Checklist Result
- Named real contour: PASS
- Intended clinic host: PASS (`DESKTOP-SNC8G9T`)
- Intended live clinic database: PASS (`clinicdb` on `127.0.0.1:5432`)
- Official clinic URL is not localhost: PASS (`http://192.168.1.5:18080`)
- Latest backup completed successfully: PASS (`C:\clinic\output\backups\clinicdb_20260405_165644.dump`)
- Last update rehearsal passed: PASS
- Last restore rehearsal passed: PASS (`C:\clinic\output\backups\clinicdb_20260405_181100.dump`)
- Pilot user list is limited: PASS

## Opening Scope
- admin
- registrar
- queue
- doctor core workflow
- cashier core workflow
- patient lookup and update

## Runtime Proof
- Live contour:
  - `CURRENT_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_API_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_WS_ORIGIN=ws://192.168.1.5:18080`
- Restore contour:
  - `CURRENT_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_API_ORIGIN=http://127.0.0.1:18081`
  - `RESOLVED_WS_ORIGIN=ws://127.0.0.1:18081`

## Operator Rule
- Open the clinic only through the named contour.
- Treat any red smoke, restore failure, rollback ambiguity, or setup reappearance as immediate `NO-GO`.
- Record day-1 evidence in [PILOT_7_DAY_EVIDENCE_PACK.md](PILOT_7_DAY_EVIDENCE_PACK.md).
