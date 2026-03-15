# W2D board_state contract options

## Option A — Keep legacy `/board/state` unchanged

### Summary

Do not replace `/board/state` now. Keep it as a legacy OnlineDay counter route
and leave the current UI on defaults/fallbacks or separate data sources.

### Advantages

- lowest immediate runtime risk
- no compatibility break for any unknown legacy consumers
- no mounted contract churn

### Risks

- preserves the current route-name confusion
- leaves the live board UI without a real backend contract for metadata
- encourages continued fallback/default behavior

### Migration complexity

- low now
- high later, because the mismatch remains unresolved

### Backward compatibility

- strongest

### UI impact

- no immediate impact
- no real improvement

### Rollout risk

- low

## Option B — Replace `/board/state` in place later

### Summary

Keep the route path, but later replace the payload with an adapter-backed
display-oriented contract.

### Advantages

- no extra endpoint to support
- eventual route naming simplicity if the change succeeds

### Risks

- high breakage risk for any unknown existing consumer of the legacy counter
  contract
- request contract would change from `department/date` semantics to board-display
  semantics
- hard to stage safely because route meaning changes in place

### Migration complexity

- high

### Backward compatibility

- weak unless a heavy compatibility layer is retained

### UI impact

- potentially positive later
- risky during cutover

### Rollout risk

- high

## Option C — Introduce a new adapter-backed endpoint and migrate UI separately

### Summary

Keep legacy `/board/state` untouched. Add a new adapter-backed endpoint for the
real display-board contract and migrate the UI in a controlled step.

### Advantages

- preserves backward compatibility for legacy consumers
- lets the new contract reflect actual UI needs
- easier to test, compare, and roll back
- clean ownership: legacy OnlineDay route stays legacy, new route belongs to
  adapter/display domain

### Risks

- endpoint surface temporarily grows
- requires explicit frontend migration step later

### Migration complexity

- medium

### Backward compatibility

- strong

### UI impact

- positive and controlled

### Rollout risk

- low to medium

## Option D — Split responsibilities permanently

### Summary

Keep `/board/state` as a legacy counter route for compatibility and introduce a
separate metadata-first board-display endpoint as the long-term UI contract,
while counters continue coming from `/queues/stats`.

### Advantages

- matches the current real UI behavior most closely
- avoids forcing queue counters and display metadata into one route
- very clear ownership boundaries

### Risks

- the system keeps two board-adjacent read surfaces long-term
- docs and consumer guidance must stay disciplined

### Migration complexity

- medium

### Backward compatibility

- strongest among change options

### UI impact

- positive if documented clearly

### Rollout risk

- low

## Comparison summary

- safest short-term: `Option A`
- safest change strategy: `Option C`
- cleanest long-term domain separation: `Option D`
- riskiest strategy: `Option B`

For current production safety and bounded evolution, `Option C` is the best
default decision. It preserves the legacy route while allowing a new contract
that can later evolve toward `Option D` if keeping counters and metadata split
turns out to be the cleaner long-term shape.
