# Clinic Pilot Contour Template

## Purpose
- Define one real clinic contour before the first live pilot cycle.
- Keep the pilot intentionally small and observable.

## Contour

- Clinic name: Doktor KosMed clinic
- Host machine: this same computer
- Host machine candidate: auto-detected by installer and confirmed by operator
- Deployment type:
  - host install
  - VPS-hosted
- Domain or LAN URL: current LAN URL on this computer
- LAN URL candidate: auto-suggested by installer and confirmed by operator
- Production or pilot database: kosmed_clinic
- Backup location:
- Rollback ref:

## URL Rule

- `localhost` may be used for internal health/backend checks only.
- `localhost` is not the official clinic URL.
- The official clinic URL must be a confirmed LAN or host URL.

## Pilot Users

- Admin user: Dr. Sapaev (`admin`)
- Registrar user: Maftuna (`registrar`)
- Doctor user: Dr. Ahmad (`derma`)
- Cashier user: Shahlo (`cashier`)
- Cardiologist user: Dr. Sapaev (`cardio`)
- Dentist user: Dr. Hamidulla (`dentist`)
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
- patient lookup/update

## Disabled Or Deferred

- optional external integrations
- large UI changes
- broader automation
- non-essential modules not yet proven in rehearsal

## Readiness Notes

- First backup completed:
- Update rehearsal completed:
- Restore rehearsal completed:
- Controlled pilot gate status:

## Acceptance

This contour is ready only when:
- the host and users are named
- the scope is narrow
- the backup and rollback path is known
- the pilot group understands the go/no-go rule
