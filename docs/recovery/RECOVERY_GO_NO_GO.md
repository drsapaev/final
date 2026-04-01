# Recovery Go / No-Go

## Do Not Transfer
- `123`
- `feat/macos-ui-refactor`
- `codex/startup-operator-first-hardening` as a whole branch
- Whole `w2c` / `post-w2c` / `wip-jules` families as branches
- Stale notification and queue architecture docs as code sources

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
- Yes: the 10 dependabot refs are safe enough to cherry-pick one at a time if dependency hygiene is still in scope.

## Safest Next Step
- Keep Stage 1 docs reconciliation as the immediate next action.
- If code execution is approved after that, start with `origin/dependabot/github_actions/docker/build-push-action-7` because it has the smallest diff surface.
