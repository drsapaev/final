# W2D Legacy Re-entry Decision

## Verdict

`NEXT_TRACK_ONLINEDAY_DEPRECATION_CONTINUATION`

## Why this is now the best use of effort

The Postgres-sensitive regression guardrail is now in CI.

That changes the risk profile: we no longer need to spend the next slice on
test-infra proof. We can return to actual legacy reduction work.

Among the remaining tails, OnlineDay deprecation continuation has the highest
architectural leverage because it is the only actionable track that still
shrinks a live legacy runtime subsystem.

## Why other tracks are not chosen yet

### `NEXT_TRACK_RESIDUE_CLEANUP`

Not chosen because residue cleanup is lower-value. It does not significantly
reduce a live runtime surface.

### `NEXT_TRACK_DOCS_CONSOLIDATION`

Not chosen because documentation is already good enough to support execution.
Another docs-only pass would add less value than one more bounded legacy slice.

### `NEXT_TRACK_PAUSE_POINT_FORMALIZATION`

Not chosen because the project already has a strong pause-point record:

- Postgres alignment review
- marker-layer docs
- CI guardrail docs

### `NEXT_TRACK_WAIT_ON_BLOCKERS`

Not chosen because not all remaining tails are blocked. There is still
actionable engineering work available inside the OnlineDay continuation track.
