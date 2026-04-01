# Recovery Final Verdict

## What To Recover
- Only the dependency-maintenance refs are safe enough to recover first.
- Keep the set intentionally small: `checkout-6`, `setup-node-6`, `setup-python-6`, the `upload-artifact-7` / `build-push-action-7` refs, and the five backend dependency bumps.

## What To Reimplement
- The w2a service/repository ideas.
- The w2c queue-architecture, phase, confirmation, registrar-batch, registrar-wizard, safe-caller, and wizard-boundary ideas.
- The notification-adapter precursor branch.
- The post-w2c queue-statistics and parity-harness ideas.

## What To Drop
- `123`
- `feat/macos-ui-refactor`

## What To Keep As Docs Or Evidence Only
- `codex/startup-operator-first-hardening`
- `origin/codex/post-w2c-next-legacy-slice-review`
- The older queue / notification architecture docs that are now superseded by current main.

## Safest Next Step
- Do not merge anything else yet.
- If the recovery phase moves to execution, start with one dependency ref at a time and validate after each.
- After that, port only the narrow slices that still add value from the stale wave branches.
