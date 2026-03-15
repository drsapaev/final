# W2D Post-W2C Next Track Decision

## Verdict

`NEXT_TRACK_OPERATIONAL_ENDPOINTS`

## Why This Track Has The Highest Architectural Leverage

The main queue allocator architecture is already complete. The largest remaining architectural uncertainty is no longer queue allocation; it is the set of live OnlineDay-backed operational admin routes that still mutate legacy state:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`
- `POST /api/v1/queues/next-ticket`

These routes matter more than the remaining board tail because:

1. They are still live mutating surfaces.
2. They determine whether the OnlineDay island can be reduced further.
3. They define whether the legacy island remains a temporary compatibility shell or a longer-lived operational admin subsystem.

## Why Other Tracks Are Not Chosen Yet

### `NEXT_TRACK_BOARD_FINALIZATION`

Not chosen because the remaining board blockers (`is_paused`, `is_closed`) are already isolated to a narrow semantic tail and are blocked by product meaning, not by missing architecture.

### `NEXT_TRACK_ONLINEDAY_DEPRECATION`

Not chosen because full OnlineDay deprecation is still downstream of the live operational admin route decisions.

### `NEXT_TRACK_LEGACY_CLEANUP`

Not chosen because support-only/dead cleanup is lower-value than clarifying the remaining live admin surfaces.

### `NEXT_TRACK_PRODUCT_DECISIONS_FIRST`

Not chosen because product semantics are currently blocking only a very narrow board tail, while the operational endpoint question has broader architectural leverage.
