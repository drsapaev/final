# Next Execution Unit After OnlineDay Support Cleanup

Date: 2026-03-09
Recommended next step: `A) live mounted OnlineDay endpoint replacement prep`

## Why this is next

- dead/disabled OnlineDay surfaces were already cleaned where safe
- support-only cleanup is now mostly exhausted
- the remaining retained support artifact (`appointments_api_service.py`) is
  blocked by architecture/test ownership rather than live runtime imports
- the next meaningful reduction of OnlineDay legacy risk must happen at the
  live mounted surface level: `open_day`, `close_day`, `stats`, `next_ticket`,
  and `board_state`

## Why not another support-only cleanup slice

- the obvious support-only mirrors are already removed
- another cleanup-only pass would risk drifting into live legacy surfaces or
  test-boundary artifacts without first defining replacement/retirement owners

## Execution shape

- preparation-first
- no runtime removal yet
- characterize and map replacement owners for mounted legacy endpoints
