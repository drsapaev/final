# W2D board_state replacement readiness

## Verdict

`BLOCKED_BY_PARITY_GAPS`

## Why

The parity harness proves that:

- queue-state parity is good
- compatibility-field parity is good

But mounted replacement is still blocked because the legacy route and the live
UI do not want the same thing from `board_state`.

Current mounted contract:

- OnlineDay-backed counters

Current live UI expectation:

- board/display metadata
- display-config-like fields
- adapter-style composition rather than legacy counter payload

## Evidence

- [W2D_BOARD_STATE_PARITY_RESULTS.md](C:/final/docs/architecture/W2D_BOARD_STATE_PARITY_RESULTS.md)
- [board_state_parity_harness.py](C:/final/backend/app/services/board_state_parity_harness.py)
- [test_board_state_parity_harness.py](C:/final/backend/tests/characterization/test_board_state_parity_harness.py)

## What is ready

- internal adapter comparison
- strict queue-state parity
- compatibility parity for `is_open` / `start_number`

## What is not ready

- metadata parity against a legacy surface that never exposed metadata
- replacement without resolving route/consumer contract mismatch
- replacement while `logo`, `is_paused`, `is_closed`, `contrast_default`, and
  `kiosk_default` still lack confirmed mounted ownership
