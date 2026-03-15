# W2D board metadata extension status

## Result

`SUCCESS`

## Fields moved to the new board-display endpoint

- `logo`
- `contrast_default`
- `kiosk_default`

## Fields retained on compatibility fallback

- `is_paused`
- `is_closed`

## Verification

Backend:

- `pytest tests/integration/test_board_new_endpoint_contract.py -q`
- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`

Frontend:

- `npm run test:run -- src/api/__tests__/boardDisplay.test.js`
- `npm run test:run -- src/pages/__tests__/DisplayBoardUnified.switch.test.jsx`
- `npm run test:run`

## Outcome summary

- new endpoint remains additive and metadata-only
- legacy `/api/v1/board/state` remains unchanged
- `DisplayBoardUnified.jsx` now depends on legacy board metadata only for
  `is_paused` and `is_closed` during normal operation
- queue counters and websocket flow remain untouched
