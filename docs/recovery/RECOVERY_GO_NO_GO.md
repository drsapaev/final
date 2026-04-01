# Recovery Go / No-Go

## Do Not Transfer
- `123`
- `feat/macos-ui-refactor`
- `codex/startup-operator-first-hardening` as a whole branch
- Whole `w2c` / `post-w2c` / `wip-jules` families as branches
- Stale notification and queue architecture docs as code sources
- The three superseded dependabot refs already covered by current `main`:
  - `dependabot/github_actions/actions/checkout-6`
  - `dependabot/github_actions/actions/setup-node-6`
  - `dependabot/github_actions/actions/setup-python-6`

## Manual Only
- `w2a` service/repository ideas
- `w2c` queue boundary / confirmation / registrar / wizard ideas
- `codex/post-w2c-queues-stats-parity-harness`
- The notification-adapter precursor branch

## Rebuild From Current Main
- The queue architecture and boundary ideas
- The post-w2c stats replacement idea
- The notification precursor idea, because current main already has a stronger notifications stack

## Safe Cherry-Pick Candidate Right Now
- No remaining safe cherry-pick candidates inside the current recovery packet.
- Stage 2 exhausted the proven dependabot shortlist:
  - `7` items were executed via minimal manual reapply
  - `3` items were dropped as already superseded by current `main`

## Safest Next Step
- Open `codex/recovery-main-execution` for review with the recovery packet, docs reconciliation, dependabot triage, and validation evidence attached.
- Let normal code review plus remote CI confirm the workflow bumps and dependency-range changes before any merge to `main`.
