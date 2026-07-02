# Controlled Pilot Gate Checklist

## Goal
Move from `PASS WITH RESTRICTIONS` to `READY FOR CONTROLLED PILOT` only after these three final proofs are complete.

## Gate 1: Linux / VPS Transport Proof
- Run the same lifecycle packet on a Linux clinic-host or VPS.
- Use the real transport path: `deploy_host.sh`, `systemd`, `nginx`.
- Confirm fresh install, backup/restore, update, and rollback all pass on Linux.
- Fail the gate if the proof depends on Windows-only execution or local dev transport.

## Gate 2: Real Release Delta
- Re-run update rehearsal on a non-marker release change.
- Use a release ref that contains a real product delta, not just a proof marker commit.
- Confirm pre-update backup, migrations, post-update smoke, and rollback still pass.
- Fail the gate if the update proof only exercises checkout/rollback without a real release change.

## Gate 3: Clinic-Like Initialized Dataset
- Seed or import a small but realistic clinic dataset before update proof.
- Include enough patients, visits, branches, and users to resemble a real clinic contour.
- Re-run post-update and rollback smoke on that initialized dataset.
- Fail the gate if the proof only uses the minimal `/setup` bootstrap dataset.

## Required Signals
- `PASS: health_check completed successfully`
- `PASS: frontend_runtime_probe completed successfully`
- `PASS: smoke_fresh_install completed successfully`
- `PASS: smoke_post_update completed successfully`
- `PASS: run_update_rehearsal completed successfully`
- `PASS: rollback_release restored ...`

## Stop Conditions
- Any red smoke
- Any restore failure
- Any setup reappearance on an initialized instance
- Any rollback ambiguity
- Any mismatch between expected and resolved API/WS origins

## Final Verdict Rule
- If all three gates pass, the status becomes `READY FOR CONTROLLED PILOT`.
- If one or more gates are still missing, keep the status at `PASS WITH RESTRICTIONS`.
