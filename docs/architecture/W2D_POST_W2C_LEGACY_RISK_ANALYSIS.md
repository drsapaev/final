# W2D Post-W2C Legacy Risk Analysis

This analysis weighs each remaining legacy surface by architectural risk, product risk, migration complexity, and expected benefit if resolved.

## Risk / Value Matrix

| Surface | Architectural risk | Product risk | Migration complexity | Benefit if resolved | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v1/board/state` legacy route | Medium | Medium | Medium | Medium | The route is no longer the target contract, but it still acts as a compatibility fallback and rollback path. |
| `is_paused` / `is_closed` | Low technical / high semantic | High | Medium | Medium | This is the narrowest remaining board blocker, but it is blocked by semantics rather than engineering effort. |
| `is_open` / `start_number` in `GET /api/v1/queues/stats` | Low | Low | Medium | Low | The strict consumer-visible counters already moved. These fields are not the highest-value follow-up. |
| `POST /api/v1/queues/next-ticket` | High | Medium | High | High | Live mutating route, misleading name, no SSOT equivalent, unknown external usage. |
| `POST /api/v1/appointments/open-day` | High | Medium | High | High | Still owns legacy day-open behavior and queue broadcast side effects. |
| `POST /api/v1/appointments/close` | High | Medium | High | High | Still owns legacy day-close behavior and determines whether the OnlineDay island can shrink further. |
| `backend/app/services/online_queue.py` | High | Low | High | High | Central runtime owner, but not a good first refactor target until live mutating routes above are clarified. |
| `OnlineDay` model / legacy counter sidecar | High | Low | High | High | Important long-term deprecation target, but current leverage is indirect because live routes still sit on top of it. |
| Legacy websocket `queue.update` fragment | Medium | Medium | Medium | Medium | Likely external/manual compatibility path. Best addressed only after operational endpoints are clarified. |
| Support/test-only mirror residue | Low | Low | Low | Low to medium | Worth cleaning later, but not the highest-value architectural step now. |

## Summary

### Highest architectural value surfaces

- `open-day`
- `close-day`
- `next-ticket`

These are the remaining live OnlineDay write/admin actions. They determine whether the OnlineDay island can be reduced further or must remain as a stable operational compatibility layer.

### Highest semantic risk surface

- `is_paused` / `is_closed`

These two fields are the smallest legacy board tail, but they are blocked by product semantics rather than missing technical capability.

### Lowest-priority cleanup surfaces

- Support-only retained mirrors
- Compatibility-only `is_open` / `start_number`

These can safely wait while the higher-leverage live operational surfaces are clarified.
