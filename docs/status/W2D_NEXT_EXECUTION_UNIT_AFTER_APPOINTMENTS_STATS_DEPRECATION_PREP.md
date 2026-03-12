## W2D Next Execution Unit After appointments.stats Deprecation Prep

## Recommended next step

`return to legacy/deprecation review and choose the next actionable OnlineDay tail`

## Why this is the safest next step

- `appointments.stats()` now has explicit contract-level deprecation signaling
- the route remains safely mounted
- no further bounded engineering step on this exact route is clearly higher
  value than moving to the next actionable tail

## Why not remove the route immediately

- the route is still public
- no explicit external-usage disproof exists
- deprecation signaling should live for at least one phase before hard removal

## Suggested candidate for the next review

The next best candidate is:

- `queues.stats` compatibility-field tail (`is_open`, `start_number`)

because it is still technical, not product-blocked, and still belongs to the
OnlineDay legacy island.
