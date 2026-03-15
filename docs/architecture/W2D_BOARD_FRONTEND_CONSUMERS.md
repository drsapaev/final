## Purpose

This document inventories frontend consumers that either:

- read legacy `GET /api/v1/board/state`
- are adjacent to board/display runtime state and therefore matter for staged migration
- produce board/display metadata that the future adapter-backed endpoint will expose

The current goal is migration preparation only. Legacy `/api/v1/board/state` remains mounted and unchanged.

## Consumer Inventory

| File | Role | Current endpoint/path | Fields or concerns used | Live | Migration priority | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `frontend/src/pages/DisplayBoardUnified.jsx` | Main display-board runtime consumer | `GET /board/state`, `GET /queues/stats`, `GET /queue/queue/status`, `openDisplayBoardWS(boardId, ...)` | Board metadata, queue counters, windows/cabinet data, websocket call stream | Yes | Highest | High |
| `frontend/src/api/ws.js` | Adjacent realtime display transport | `/api/v1/display/ws/board/{boardId}` | Live queue entries/current call/announcements stream | Yes | Not a board-state migration target | Medium |
| `frontend/src/components/admin/DisplayBoardSettings.jsx` | Admin producer/config editor | `/api/v1/admin/display/boards/*`, `/api/v1/admin/display/stats` | Display board settings, themes, tests, announcements | Yes | Later, producer-side only | Low |
| `frontend/src/components/display/DisplayContentManager.jsx` | Admin content producer | `/api/v1/admin/display-boards/{boardId}/content` | Banners, announcements, videos, themes | Yes | Later, producer-side only | Low |
| `frontend/src/pages/Settings.jsx` | Settings producer for legacy display_board kv store | `GET/PUT /settings?category=display_board` | `brand`, `logo`, `announcement_*`, color fields, `contrast_default`, `kiosk_default`, `sound_default` | Yes | Producer-side compatibility surface | Medium |
| `frontend/src/api/services.js` | Generic API wrapper layer | No dedicated board-display reader yet | No runtime board-state ownership | Indirect | High value prep surface | Medium |
| `frontend/src/api/endpoints.js` | Endpoint constants | No new board-display constant yet | Existing queue endpoint drift remains | Indirect | High value prep surface | Medium |

## Confirmed Live Runtime Consumer

`frontend/src/pages/DisplayBoardUnified.jsx` is the only confirmed live frontend consumer of legacy `/board/state`.

It currently:

- calls `api.get('/board/state')` without `department` or `date`
- normalizes the legacy payload into local board state
- falls back to `localStorage['board.state']` and then hardcoded defaults on fetch failure
- reads counters from `/queues/stats` separately
- reads additional queue status from `/queue/queue/status`
- receives live updates through `openDisplayBoardWS(currentBoardId, ...)`

This means the first frontend migration should target `DisplayBoardUnified` only, not the broader display/admin ecosystem.

## Adjacent but Not Initial Migration Targets

These files are important, but they are not first-switch consumers of the new board-display endpoint:

- `frontend/src/api/ws.js`
  - live websocket transport, but not a `/board/state` reader
- `frontend/src/components/admin/DisplayBoardSettings.jsx`
  - admin-side producer/configuration UI
- `frontend/src/components/display/DisplayContentManager.jsx`
  - content-management producer UI
- `frontend/src/pages/Settings.jsx`
  - legacy producer/configuration surface for display-board kv data

## Practical Migration Scope

The narrow first frontend migration should only replace the metadata fetch path inside `DisplayBoardUnified.jsx`.

It should not, in the same slice:

- change websocket behavior
- change `/queues/stats` usage
- change `/queue/queue/status` usage
- change admin/config producer surfaces
- remove legacy `/board/state`
