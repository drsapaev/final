# Operational Proof Packet

## Purpose
- Run the last three proofs needed before controlled pilot.
- Keep the packet small, repeatable, and evidence-driven.
- Reuse the existing helper scripts and runbooks only.

## Proof 1: Linux / VPS Transport

Goal:
- Prove the lifecycle packet works on a Linux clinic-host or VPS using the real transport path.

Run:
```bash
bash ops/vps/scripts/deploy_host.sh
python3 ops/vps/scripts/smoke_fresh_install.py
python3 ops/vps/scripts/backup_db.py
python3 ops/vps/scripts/restore_db.py
UPDATE_RELEASE_REF=<approved-release-ref-or-imported-artifact-ref> \
ROLLBACK_REF=<baseline-ref> \
python3 ops/vps/scripts/run_update_rehearsal.py
```

PASS signals:
- `PASS: health_check completed successfully`
- `PASS: frontend_runtime_probe completed successfully`
- `PASS: smoke_fresh_install completed successfully`
- `PASS: smoke_post_update completed successfully`
- `PASS: run_update_rehearsal completed successfully`
- `PASS: rollback_release restored ...`

## Proof 2: Real Release Delta

Goal:
- Re-run update rehearsal on a non-marker release change.

Rules:
- use an approved release artifact or imported ref that contains a real product delta
- do not use a proof-marker commit
- keep the pre-update backup and rollback ref available

Evidence to save:
- update command
- imported or approved release ref
- backup filename
- migration result
- health result
- smoke result
- rollback result if needed

## Proof 3: Clinic-Like Initialized Dataset

Goal:
- Re-run update and rollback smoke on a small but realistic clinic dataset.

Dataset should include:
- patients
- visits
- branches
- users

The dataset should be larger than the minimal `/setup` bootstrap state but still small enough to inspect manually.

## Evidence Pack

For each proof, save:
- date
- host / env
- release artifact / ref
- command
- outcome
- backup artifact
- migration result
- health result
- smoke result
- rollback result
- notes

## Stop Conditions
- any red smoke
- any restore failure
- any setup reappearance on an initialized instance
- any rollback ambiguity
- any API/WS origin mismatch

## Final Result
- If all three proofs are green, the controlled pilot gate may be re-evaluated.
- If one or more proofs fail, stop and fix only the failing condition.
