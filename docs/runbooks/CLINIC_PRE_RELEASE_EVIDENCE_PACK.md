# Clinic Pre-Release Evidence Pack

[← Previous Page](CLINIC_RELEASE_CANDIDATE_SUMMARY.md) · [Back to README](../README.md) · [Next Page →](LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md)

## Purpose
- Capture the evidence that supports the current clinic release candidate.
- Use this pack alongside the pre-release checklist and the release candidate summary.
- Keep the release candidate traceable to concrete build and proof artifacts.

## Release Candidate
- Release ref: `main`
- Commit SHA: `923010c00bf307fdf8bdc7cacc4e593a01d1f60f`
- Approved release artifact: `output/release-artifacts/clinic-release-923010c00bf3.zip`

## Evidence Rows

| Date | Host / env | Release artifact / ref | Command | Outcome | Backup artifact | Migration result | Health result | Smoke result | Current origin | Resolved API origin | Resolved WS origin | Rollback result | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-05 | `c:\final` / local release-prep host | `output/release-artifacts/clinic-release-923010c00bf3.zip` / `HEAD` | `python ops/vps/scripts/build_release_artifact.py --ref HEAD --output-dir output/release-artifacts` | PASS | `output/operational-proof/20260404_controlled_pilot_gate/EVIDENCE_BACKUP_RESTORE_LINUX.md` | PASS | PASS | PASS | `http://127.0.0.1:18080` | `http://127.0.0.1:18080` | PASS | Release candidate summary and pilot evidence are linked below. |

## Linked Proofs
- [Controlled Pilot Gate Result](CONTROLLED_PILOT_GATE_RESULT.md)
- [Release Candidate Summary](CLINIC_RELEASE_CANDIDATE_SUMMARY.md)
- [Fresh Install Evidence](../../output/operational-proof/20260404_controlled_pilot_gate/EVIDENCE_FRESH_INSTALL_LINUX.md)
- [Backup/Restore Evidence](../../output/operational-proof/20260404_controlled_pilot_gate/EVIDENCE_BACKUP_RESTORE_LINUX.md)
- [Update Rehearsal Evidence](../../output/operational-proof/20260404_controlled_pilot_gate/EVIDENCE_UPDATE_REHEARSAL_LINUX.md)

## Evidence Rules
- Record the exact command that was run.
- Record the exact approved release artifact or imported release ref that was deployed.
- Copy the exact PASS/FAIL line from the script output.
- Save backup filenames as emitted by `BACKUP_FILE=...`.
- Save `CURRENT_ORIGIN=...`, `RESOLVED_API_ORIGIN=...`, and `RESOLVED_WS_ORIGIN=...` exactly as emitted by the smoke output.
- If a rehearsal fails, include the first `FAIL:` line that stopped it.

## See Also
- [Clinic Pre-Release Checklist](CLINIC_PRE_RELEASE_CHECKLIST.md)
- [Clinic Release Candidate Summary](CLINIC_RELEASE_CANDIDATE_SUMMARY.md)
- [Clinic Release Artifact Policy](CLINIC_RELEASE_ARTIFACT_POLICY.md)
