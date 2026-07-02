# Pilot Launch Pack

## Purpose
- Define the smallest safe clinic pilot before going wider.
- Keep the pilot limited, observable, and easy to stop.
- Reuse the existing backup, update, restore, and rehearsal discipline.

## Pilot Contour

- One clinic only.
- One host machine only.
- One live database only.
- Browser/LAN access only for workstations by default.
- No second server install for staff machines.

## Pilot Scope

Start with only the workflows needed for the first real clinic cycle:
- login
- registrar
- queue
- doctor core workflow
- cashier core workflow
- patient record lookup and update

Leave these outside the first wave unless they are already proven and explicitly approved:
- advanced automation
- optional external integrations
- broad UI refactors
- large workflow expansion

## Pilot Group

Use a small and known pilot group:
- clinic owner or sponsor
- one admin user
- one registrar user
- one doctor user
- one cashier user

Add more users only after the first live cycle is stable.

## Daily Discipline

- Take a backup every day.
- Run updates only through the approved release artifact and rehearsal path.
- Save evidence for each change window.
- Treat every red smoke as a stop condition.

## Incident Rules

Log an incident note immediately if any of these happen:
- login failure
- setup reappears on an initialized instance
- restore failure
- rollback ambiguity
- data loss or data mismatch
- unresolved origin mismatch

Each incident note should record:
- date and time
- host/env
- what failed
- first failing signal
- backup or release ref involved
- action taken

Use the one-screen incident note template:
- [Pilot Incident Note Template](./PILOT_INCIDENT_NOTE_TEMPLATE.md)

Use the 7-day evidence pack for live pilot tracking:
- [Pilot 7-Day Evidence Pack](./PILOT_7_DAY_EVIDENCE_PACK.md)

## Go / No-Go Rule

Continue the pilot only if all of these remain true:
- backups succeed
- updates succeed through the rehearse-and-rollback path
- restore succeeds to a separate target
- no setup reappearance occurs
- core workflows remain usable for the pilot group

Stop or pause the pilot if:
- any red smoke appears
- any restore failure appears
- rollback is unclear
- the clinic cannot complete its day-to-day core workflow

## Acceptance Criteria
- The pilot group and scope are explicitly limited.
- The incident note process is known before the first live cycle.
- The go/no-go rule is clear before changes start.
