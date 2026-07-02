# Master Checklist: Local-Only Clinic Package + Pilot + Safe Updates

Use this as the single execution checklist for the current track.

Rule for marking items:
- mark `[x]` only when the item is fully done and backed by code, docs, or evidence
- keep `[ ]` for anything still partial or not yet operationally proven

## 1. Target model and architecture
- [x] Formalize `one clinic = one isolated deployment` in project SSOT docs
- [x] Formalize universal package model in project SSOT docs
- [x] Formalize `/setup` as in-instance first-run orchestration over existing SSOT entities
- [x] Formalize install-time per-clinic technical config as external to the package
- [x] Explicitly formalize `host machine / admin user / workstation user` as a tracked project rule
- [x] Explicitly formalize `browser/LAN first` as the default workstation access model
- [x] Formalize installer auto-detect/confirm behavior for host and LAN URL candidates
- [x] Formalize `localhost` as internal health/backend checks only, not the official clinic URL

## 2. Package and install boundaries
- [x] Keep backend/frontend/migrations/helpers/runbooks/sample env inside one common package model
- [x] Keep `DATABASE_URL`, host/url values, secrets, and storage paths outside the package
- [x] Keep clinic/business identity inside `/setup`
- [x] Define the final approved release artifact format for delivery
- [x] Define offline delivery path for the same approved artifact
- [x] Define exact packaging workflow for producing the clinic-deliverable bundle

## 3. Setup and local-only behavior
- [x] Implement `/setup` without introducing a second SSOT
- [x] Ensure initialized state is inferred from real SSOT entities
- [x] Ensure `/setup` cannot be replayed successfully on an already initialized instance
- [x] Keep landing out of the operational bootstrap path
- [x] Explicitly document offline-friendly external services policy
- [x] Explicitly document configure-later policy for optional integrations
- [x] Explicitly document which features are unsupported in local-only mode until configured

## 4. Frontend transport model
- [x] Move frontend to `same-origin first`
- [x] Centralize API/WS resolution through runtime logic
- [x] Add smoke proof for `CURRENT_ORIGIN`, `RESOLVED_API_ORIGIN`, `RESOLVED_WS_ORIGIN`
- [x] Update operator/evidence docs to require origin proof
- [x] Verify no remaining non-runtime transport assumptions in non-core docs and operator guidance

## 5. Host lifecycle tooling
- [x] Add `backup_db`
- [x] Add `restore_db`
- [x] Add `deploy_release`
- [x] Add `run_migrations`
- [x] Add `health_check`
- [x] Add `smoke_fresh_install`
- [x] Add `smoke_post_update`
- [x] Add `rollback_release`
- [x] Add `run_update_rehearsal`
- [x] Add `run_backup_restore_rehearsal`
- [x] Make helpers env/config-driven and fail-fast
- [x] Make rehearsal wrappers return PASS/FAIL
- [x] Add approved release artifact build/import helpers

## 6. Runbooks and operator flow
- [x] Create clinic-host install runbook
- [x] Create update rehearsal runbook
- [x] Create backup/restore rehearsal runbook
- [x] Create state separation audit
- [x] Create one-page operator checklist
- [x] Create evidence pack template
- [x] Create controlled pilot gate checklist
- [x] Create quick pilot gate checklist
- [x] Update operational docs to use approved-release-artifact and offline-capable update terminology

## 7. Workstation model
- [x] Define and document `Host Install`
- [x] Define and document `Workstation Access`
- [x] State clearly that workstations do not run their own backend/DB
- [x] State clearly that workstation default is browser/LAN access without separate installation
- [x] Keep thin launcher support optional only

## 8. Safe update model
- [x] Enforce backup-before-update as the standard path
- [x] Enforce migrate + health + smoke after update
- [x] Enforce rollback path after failed update
- [x] Ensure update smoke checks initialized deployments and blocks setup reappearance
- [x] Replace or extend Git ref language with approved release artifact language everywhere relevant in operational docs
- [x] Support update delivery from GitHub/release source
- [x] Support update delivery from offline update package
- [x] Define release approval source of truth for clinic updates

## 9. Operational proof and pilot readiness
- [x] Capture local operational proof with evidence artifacts
- [x] Capture fresh install evidence
- [x] Capture backup/restore evidence
- [x] Capture update rehearsal evidence
- [x] Create operational proof packet
- [x] Re-run lifecycle proof on Linux/VPS transport
- [x] Re-run update proof on a real release delta
- [x] Re-run update/rollback proof on clinic-like initialized data
- [x] Complete the controlled pilot gate with all three final proofs green

## 10. Controlled pilot launch
- [x] Create pilot launch pack
- [x] Create pilot start checklist
- [x] Create pilot incident note template
- [x] Create pilot 7-day evidence pack
- [x] Create clinic pilot contour template
- [x] Prepare one real clinic pilot contour
- [x] Limit first pilot to small user group and narrow workflow scope
- [x] Define incident note template and escalation owner
- [x] Run pilot only through backup/update/rehearsal discipline
- [x] Decide go/no-go rule for continuing pilot after first live cycle

## Completion Criteria

Mark the whole plan complete only when all of these are `[x]`:
- universal package exists as the official delivery model
- host vs workstation model is explicit and documented
- local-only clinic can install and initialize without mandatory internet services
- approved release artifact model is defined for both online and offline delivery
- install/update/restore/rollback path is proven on Linux/VPS with clinic-like initialized data
- controlled pilot gate is fully passed
