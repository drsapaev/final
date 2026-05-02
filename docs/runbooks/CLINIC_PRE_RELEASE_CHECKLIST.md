# Clinic Pre-Release Checklist

[← Previous Page](CLINIC_RELEASE_ARTIFACT_POLICY.md) · [Back to README](../README.md) · [Next Page →](LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md)

## Scope
- Use this checklist before promoting a clinic release, pilot patch set, or update bundle.
- Treat it as a final release-readiness gate, not as a deployment guide.
- Do not ship if any fail signal is present.

## 1) Release Candidate Readiness
- [ ] Working tree is clean except for intentionally staged release evidence.
- [ ] Current branch is the intended release branch.
- [ ] Approved release artifact has been built or imported from the approved release ref.
- [ ] Release ref and commit SHA are recorded in the evidence pack.
- [ ] Release notes or release summary are prepared.
- [ ] No unrelated local artifacts are staged for release.

## 2) Runtime And Data Safety
- [ ] Backup completed for the target clinic host.
- [ ] Backup artifact path is recorded and readable.
- [ ] Rollback ref is recorded and known-good.
- [ ] Update rehearsal passed for the current release delta.
- [ ] Restore rehearsal passed on a separate target when required.
- [ ] Health check passes on the target host.
- [ ] Smoke checks pass on the target host.
- [ ] Setup does not reappear on an initialized instance.

## 3) Local-Only And Access Model
- [ ] Host machine is confirmed and documented.
- [ ] Host install mode is confirmed when the clinic is self-hosted.
- [ ] Workstation access is browser/LAN first by default.
- [ ] `localhost` is used only for internal health/backend checks.
- [ ] Optional external services remain disabled unless explicitly approved.
- [ ] Any split-origin override is intentional and documented.

## 4) Evidence Pack
- [ ] Pre-release evidence pack is filled out.
- [ ] Fresh install, backup/restore, and update evidence are attached when applicable.
- [ ] Controlled pilot gate result is attached when the release is going to pilot.
- [ ] Any open incident notes are linked.
- [ ] Sign-off owner is recorded.

## PASS Signals
- `PASS: health_check completed successfully`
- `PASS: smoke_fresh_install completed successfully`
- `PASS: smoke_post_update completed successfully`
- `PASS: backup_db created ...`
- `PASS: restore_db completed successfully`
- `PASS: run_update_rehearsal completed successfully`
- `CURRENT_ORIGIN=...`
- `RESOLVED_API_ORIGIN=...`
- `RESOLVED_WS_ORIGIN=...`

## FAIL Signals That Stop Release
- Any line starting with `FAIL:`
- Missing or unreadable backup artifact
- Backup target does not match the intended clinic database
- Restore fails or restores to the wrong target
- Update rehearsal fails or rollback is ambiguous
- Smoke shows setup reappearing on an initialized instance
- Frontend runtime probe resolves API or WS to a stale build-time origin
- Unapproved release artifact or unapproved release ref is used

## Exit Criteria
- [ ] All checklist items above are complete or intentionally waived with a recorded reason.
- [ ] The evidence pack matches the release candidate.
- [ ] The release is safe to move into pilot, staging, or production rollout.

## See Also
- [Clinic Release Artifact Policy](CLINIC_RELEASE_ARTIFACT_POLICY.md)
- [Clinic Operator Checklist](CLINIC_OPERATOR_CHECKLIST.md)
- [Controlled Pilot Gate Checklist](CONTROLLED_PILOT_GATE_CHECKLIST.md)
