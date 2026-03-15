# W2D next_ticket Consumers

## Confirmed direct mounted surface

- `POST /api/v1/queues/next-ticket`
  - file: `backend/app/api/v1/endpoints/queues.py`
  - live: yes
  - mounted: yes
  - current runtime owner: `issue_next_ticket()`

## Confirmed in-repo direct callers

No confirmed direct frontend or backend caller of `/api/v1/queues/next-ticket` was found in the current repository.

Checked surfaces:

- `frontend/src/**/*`
- `backend/app/**/*`
- `backend/tests/**/*`

## Near-by but different callers

These are related queue actions, but they do not call `POST /api/v1/queues/next-ticket`:

- `frontend/src/api/services.js::queueService.callNext()`
  - points to `/queue/call-next`
  - not the same route
- `frontend/src/services/queue.js::callNextWaiting()`
  - uses `/doctor/{specialty}/queue/today` and `/doctor/queue/{id}/call`
  - modern doctor-facing flow, not legacy counter issuance
- `frontend/src/api/queue.js::callNextQueuePatient()`
  - uses `/queue/{specialist_id}/call-next`
  - modern specialist queue flow

## Indirect downstream observers

While no direct caller is confirmed, this route still mutates legacy counters later observed by:

- `frontend/src/pages/DisplayBoardUnified.jsx`
  - indirectly through `GET /api/v1/queues/stats`
- `GET /api/v1/board/state`
  - legacy read surface over the same OnlineDay counters
- legacy queue websocket room payloads
  - `queue.update` emitted from `app/services/online_queue.py`

## Legacy websocket consumers

Legacy queue websocket utilities still exist:

- `frontend/src/api/ws.js::openQueueWS()`
- `frontend/src/utils/websocketAuth.js::createQueueWebSocket()`

But no current live page was confirmed to use them for `next_ticket`.

## Consumer risk assessment

Current migration risk is unusual:

- direct in-repo consumer risk appears low
- external/manual/admin usage risk is unresolved because the route is still mounted and present in OpenAPI
- downstream stats/display drift risk remains real because the route mutates board-visible counters

## Practical conclusion

`next_ticket` should currently be treated as:

- live mounted legacy surface
- no confirmed in-repo direct consumer
- possible external/manual operational action
- indirect producer of legacy board/stats state
