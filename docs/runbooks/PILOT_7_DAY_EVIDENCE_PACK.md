# Pilot 7-Day Evidence Pack

Use one row per pilot day for the first seven live days.

## Pilot Header
- Clinic: Doktor KosMed clinic
- Host machine: `DESKTOP-SNC8G9T` (Windows pilot host)
- Contour: [Clinic Pilot Contour: Windows Host](CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
- Pilot start date: `2026-04-06` (live opening)
- Pilot end date: after day 7 live evidence is complete
- Pilot owner: Dr. Sapaev
- Escalation owner: Dr. Sapaev

## Pre-Open Readiness
- Approved artifact: `clinic-release-923010c00bf3.zip`
- Imported release ref: `refs/clinic-releases/clinic-release-923010c00bf3`
- Update rehearsal result: PASS
- Restore rehearsal result: PASS
- Live browser URL: `http://192.168.1.5:18080`
- Live backend URL: `http://127.0.0.1:18000`
- Live backup baseline: `C:\clinic\output\backups\clinicdb_20260405_165644.dump`
- Fresh live baseline backup: `C:\clinic\output\backups\clinicdb_20260405_191852.dump`
- Restore rehearsal backup: `C:\clinic\output\backups\clinicdb_20260405_181100.dump`
- Live runtime proof:
  - `CURRENT_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_API_ORIGIN=http://192.168.1.5:18080`
  - `RESOLVED_WS_ORIGIN=ws://192.168.1.5:18080`

## Daily Fields
- Day
- Date
- Users active
- Scope used
- Backup result
- Update result
- Restore result
- Health result
- Smoke result
- Current origin
- Resolved API origin
- Resolved WS origin
- Incident count
- Stop signal
- Notes

## Suggested Format

```text
Day: 1
Date: 2026-04-06
Users active: admin, registrar, doctor, cashier
Scope used: login, queue, registrar, cashier, patient lookup/update
Backup result: PASS (`C:\clinic\output\backups\clinicdb_20260405_191852.dump`)
Update result: N/A
Restore result: N/A
Health result: PASS
Smoke result: FAIL
Current origin: http://192.168.1.5:18080
Resolved API origin: http://192.168.1.5:18080
Resolved WS origin: ws://192.168.1.5:18080
Incident count: 1
Stop signal: queue board crash on /queue-board
Notes: login, registrar, and cashier routes opened successfully; queue board crashed with wsRef.current.close is not a function
```

### Incident Note
- Date and time: 2026-04-06, first live-hour smoke
- Host / env: DESKTOP-SNC8G9T / Windows pilot host
- Clinic contour: named live Windows pilot contour
- Reported by: Codex smoke run
- Severity: stop condition
- Classification: product
- Expected behavior: queue board should render the current live queue state without a React error boundary crash
- Actual behavior: /queue-board crashed in `DisplayBoardUnified` with `wsRef.current.close is not a function`
- First failing command or screen: `http://192.168.1.5:18080/queue-board`
- What stopped: queue board smoke and broader first-hour pilot confidence
- What still works: admin login, registrar panel, cashier panel, live host health
- Any data loss: none observed
- Any rollback ambiguity: none observed
- Stop condition triggered: yes
- Action taken: paused further pilot smoke and documented the failure
- Backup or ref involved: `C:\clinic\output\backups\clinicdb_20260405_191852.dump`
- Rollback result: not needed for this read-only failure
- Fix owner: unresolved
- Follow-up command or rehearsal: inspect `DisplayBoardUnified.jsx` and the queue/board API contract before resuming queue smoke
- Evidence link: [PILOT_7_DAY_EVIDENCE_PACK.md](PILOT_7_DAY_EVIDENCE_PACK.md)
- Recheck time: after fix is applied and verified

## Day 1 Recorded

### Checklist Walkthrough
- Clinic contour is the named real contour: PASS
- Host machine is the intended clinic host: PASS
- Database is the intended live clinic database: PASS
- Official clinic URL is the LAN URL, not `localhost`: PASS
- Latest backup completed successfully: PASS
- Last update rehearsal passed: PASS
- Last restore rehearsal passed: PASS
- Pilot user list is limited to the approved group: PASS

### Live Opening Entry
```text
Day: 1
Date: 2026-04-06
Users active: admin, registrar, doctor, cashier
Scope used: login, queue, registrar, cashier, patient lookup/update
Backup result: PASS (`C:\clinic\output\backups\clinicdb_20260405_191852.dump`)
Update result: N/A
Restore result: N/A
Health result: PASS
Smoke result: PASS
Current origin: http://192.168.1.5:18080
Resolved API origin: http://192.168.1.5:18080
Resolved WS origin: ws://192.168.1.5:18080
Incident count: 0
Stop signal: None
Notes: live browser open verified on the named Windows host; no setup reappearance
```

## Evidence Rules
- Record one row for each pilot day.
- Copy the exact PASS/FAIL line for any failing action.
- Record the approved release artifact or imported release ref used for any update.
- Record the backup filename for every day that a backup was taken.
- If any red smoke or restore failure appears, mark the stop signal immediately.
- Save incident notes alongside the daily row.

## Stop Conditions
- any red smoke
- any restore failure
- any setup reappearance on an initialized instance
- any rollback ambiguity
- any unresolved origin mismatch
