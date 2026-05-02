# Controlled Pilot Gate Quick Copy

Use this only after `PASS WITH RESTRICTIONS`.

## Must-pass
- Linux/VPS transport proof on real `deploy_host.sh` + `systemd` + `nginx`
- Update rehearsal with a real release delta, not a marker commit
- Initialized dataset that looks like a small real clinic

## Required PASS signals
- `PASS: health_check completed successfully`
- `PASS: frontend_runtime_probe completed successfully`
- `PASS: smoke_fresh_install completed successfully`
- `PASS: run_update_rehearsal completed successfully`
- `PASS: smoke_post_update completed successfully`
- `PASS: rollback_release restored ...`

## Stop if
- any red smoke
- any restore failure
- any setup reappearance on initialized instance
- any rollback ambiguity
- any API/WS origin mismatch

## Final rule
- All 3 must-pass items green = `READY FOR CONTROLLED PILOT`
- Anything else = `PASS WITH RESTRICTIONS`
