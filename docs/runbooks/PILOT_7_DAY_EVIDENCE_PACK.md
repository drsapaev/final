# Pilot 7-Day Evidence Pack

Use one row per pilot day for the first seven live days.

## Pilot Header
- Clinic:
- Host machine:
- Contour:
- Pilot start date:
- Pilot end date:
- Pilot owner:
- Escalation owner:

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
Date: 2026-04-04
Users active: admin, registrar, doctor, cashier
Scope used: login, registrar, queue, doctor, cashier, patient lookup/update
Backup result: PASS
Update result: N/A
Restore result: N/A
Health result: PASS
Smoke result: PASS
Current origin: https://clinic.example.com
Resolved API origin: https://clinic.example.com
Resolved WS origin: wss://clinic.example.com
Incident count: 0
Stop signal: None
Notes: first live day, no setup reappearance
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
