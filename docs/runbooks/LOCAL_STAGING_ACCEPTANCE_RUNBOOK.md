# Local Staging Acceptance Runbook

## Purpose

Use the isolated Linux staging environment in WSL2 Ubuntu 24.04 Docker on this Windows host for role-by-role acceptance. It is separate from Windows production and may be stopped between test runs. See `docs/runbooks/AGENT_SESSION_WORKTREES.md` for isolation and startup preflight.

Current local staging contour (verify the active Compose project and port overrides before use):
- backend: `http://127.0.0.1:18001`
- frontend: `http://127.0.0.1:18080`
- staging Postgres: `127.0.0.1:55432`
- Windows production backend: `:18000` — never bind staging to this port
- LAN access: configure and verify it explicitly if testing a tablet; do not assume the old host IP is current

## Pre-Flight

- Confirm staging backend is healthy: `GET /api/v1/health`
- Confirm the Compose project points to the intended source worktree and `STAGING_BACKEND_PORT` differs from production `18000`
- Confirm frontend root loads without blocking console/network errors
- Confirm staging Postgres is running and the staging app points to its own DSN and synthetic fixtures, not production data
- Confirm latest EMR cutover verification is green before manual checks:
  - `passed == true`
  - `failed == 0`
  - `duplicate_visit_records == 0`
  - `missing_specialty == 0`
  - `missing_specialty_data == 0`
  - `prescriptions_missing_canonical_refs == 0`
  - `files_missing_canonical_refs == 0`

## Role Acceptance Sweep

### Admin
- Login succeeds
- Settings and reference data screens open without permission errors
- Department/pricing/config changes save and reload correctly
- No obvious RBAC mismatch between visible UI and backend permission response

### Registrar
- Patient search works
- New patient registration works
- Appointment/visit creation works
- Queue-related registrar actions do not regress after Postgres migration

### Cashier
- Visit/payment status loads
- Payment creation/update path works
- Receipt or payment confirmation flow still completes

### Lab
- Lab-facing pages load under the staging role
- Lab results remain source-of-truth in the lab domain
- EMR only reflects clinician interpretation/references and does not duplicate raw lab ownership
- For P6, lab is treated as outside EMR parity temporarily; it remains a separate lab-domain workflow, not a blocker for EMR v2 acceptance

### Specialists
- Cardiology, dermatology, and dentistry open the v2 EMR path only
- New EMR records initialize with canonical `visit_id`
- `data.specialty` is normalized and specialist sections render correctly
- Save, autosave, sign, amend, and history flows behave correctly

## EMR Cutover Checks

- Legacy appointment-based EMR routes behave as delegation shims only
- Doctor-history filtering differs correctly by specialty when underlying data differs
- Prescription eligibility depends on canonical EMR v2 state
- Complete-visit/status flows use canonical visit resolution and do not depend on legacy EMR persistence
- Files and attachments remain reachable through canonical refs

## Data Closure

- Queue-domain legacy gap: archive legacy queue data explicitly as non-canonical. Do not keep a hidden dual source of truth.
- Review remaining skipped legacy rows:
  - appointments with missing patient refs
  - orphan message refs
  - source-only legacy tables
- Record each unresolved item as either:
  - fixed,
  - intentionally archived,
  - or explicitly accepted with rationale

## Config Hygiene

- Verify committed docs do not depend on machine-specific secrets
- Keep local/staging env files out of tracked state when they contain secrets
- Recheck staging startup scripts after any runtime/env change

## Exit Criteria

- Manual smoke pack is green for admin, registrar, cashier, lab, and specialist doctor flows
- EMR v2 specialist behavior is confirmed on the local staging contour
- Queue-domain archival decision is documented
- No new local/staging config drift is introduced

## Stop/Go To VPS

Do not start VPS rollout until:
- local acceptance is green,
- queue-domain closure is documented,
- and the rollout kit in `ops/vps/` still matches the active deployment path.
