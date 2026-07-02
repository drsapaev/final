# Local-Only External Services Policy

## Purpose
- Define how the system behaves when a clinic chooses not to use internet services.
- Keep local-only deployment compatible with the same package and setup model.

## Default Rule

For a local-only clinic, all external integrations are **disabled by default**.

That includes:
- AI/cloud providers
- Telegram
- SMS gateways
- FCM/push providers
- external payment providers
- public webhooks

## Setup Rule

`/setup` must not require any external internet service.

Setup is allowed to collect only clinic business identity:
- clinic name
- first branch
- first admin
- optional activation or license key when policy requires it

It must not block completion because Telegram, AI, SMS, FCM, or cloud services are absent.

## Configure Later Rule

Every optional external integration must support a clear **configure later** path:
- clinic install may complete with the integration unset
- core workflows must continue to work
- the integration may be enabled later from admin/ops configuration

## Supported Local-Only Core

A local-only clinic is expected to support:
- host-based deployment
- PostgreSQL on the clinic host
- backend/frontend on the clinic host
- browser/LAN access for workstations
- `/setup`
- login and role-based access
- registrar, queue, doctor, cashier, and core patient workflows
- backup, restore, update, and rollback tooling

## Unsupported Until Configured

These functions are not expected to work in local-only mode until configured explicitly:
- Telegram notifications and bot flows
- SMS delivery through external providers
- FCM/mobile push
- cloud AI functions
- public webhooks
- internet-facing payment provider callbacks

If one of these is needed later, it must be enabled as a separate explicit integration step.

## Host, Admin, And Workstation Roles

- **Host machine**
  - where backend, PostgreSQL, storage, backup, and update tooling run
- **Admin user**
  - who manages the system by role inside the application
- **Workstation user**
  - who signs in from a browser or LAN workstation using their own account

Authority comes from RBAC, not from which machine a person uses.

## Acceptance Criteria
- Local-only clinics can complete install and setup without mandatory internet services.
- Disabled integrations do not block core clinical work.
- The system leaves room to enable optional integrations later without reinstalling the clinic.
