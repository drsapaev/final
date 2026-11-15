# Continued Code Review — group 90: merged display kiosk bootstrap negative-path verification

**Date:** 2026-11-15 (Asia/Tashkent). **Mode:** source-backed read-only review; this Markdown report is the only changed file. **Current main reviewed:** [`052be9d3842f3e8baf68cb849b90aeefde2fd70b`](https://github.com/drsapaev/final/commit/052be9d3842f3e8baf68cb849b90aeefde2fd70b), newly including merged [fix #4057](https://github.com/drsapaev/final/pull/4057). **Same audit:** Draft [#4059](https://github.com/drsapaev/final/pull/4059), following group89 and preserving groups47–89. **Owner tracker:** [#4063](https://github.com/drsapaev/final/issues/4063).

Reviewed original round32 [`DISPLAYBOOT-FE-001` observation](https://github.com/drsapaev/final/pull/3961#issuecomment-6757546793), later [kiosk design/fail-first follow-up](https://github.com/drsapaev/final/pull/3961#issuecomment-6800151014), current main code for backend device-scoped JWT/cookie/session/credential-version enforcement, frontend device provisioning, board state UX, and merged tests:
- `backend/app/services/display_device_credentials.py`
- `backend/app/api/v1/endpoints/display_websocket.py`
- `backend/app/models/display_config.py`
- `frontend/src/api/displayDeviceAuth.ts`
- `frontend/src/api/ws.ts`
- `frontend/src/pages/DisplayBoardUnified.tsx`
- `frontend/src/pages/__tests__/DisplayBoardUnified.deviceProvisioning.test.tsx`
- `frontend/src/api/__tests__/ws.displayboard.reconnect.test.ts`

Repo security skill `.agents/skills/code-security/SKILL.md` and root `AGENTS.md` are applicable. This is static code and existing test coverage review; no local tests/PowerShell gate/staging, live data, production or credential exchange executed.

## Real improvement merged in #4057 — but not yet a kiosk operational proof

The prior public kiosk lacked a permitted way to join the authenticated display WS as a non-staff client. #4057 now adds:
- Explicitly board-scoped `display_device` JWTs, one-time secret exchange with an atomic verifier replacement, 60-minute access TTL, a renewable 30-day HttpOnly board-scoped cookie.
- Backend token decoding, board membership/activity check, device `status`/credential version revalidation and staff role controls, 15-second WS reauthorization, administrative rotate/revoke endpoints, RLS migration.
- Frontend setup form for HTTP 401, session renewal on reconnect, no one-time secret persistence in localStorage; focused integration/unit tests.
- The PR's own record reports targeted 133 backend and 10 frontend tests, plus exact-head successful CI. These are **existing PR-reported results**, not tests rerun in group90.

## Residual A — P2 conditional: disabled WS can be interpreted as ready kiosk without live queue

1. [`frontend/src/api/ws.ts:7–11`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/api/ws.ts#L7-L11) defaults the `VITE_ENABLE_WS` flag to `0`, while [`openDisplayBoardWS:59–69`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/api/ws.ts#L59-L69) calls `tokenProvider` and **opens no socket** if disabled.
2. [`DisplayBoardUnified.tsx:441–451`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/pages/DisplayBoardUnified.tsx#L441-L451) can set `displayDeviceState='ready'` on successful device session check regardless of transport flag. The disconnected icon remains visible, but the board displays its regular content and lacks an explicit *first-connect* live-unavailable warning.
3. [`ws.displayboard.reconnect.test.ts`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/api/__tests__/ws.displayboard.reconnect.test.ts) explicitly tests that with flag `0` the provider is consulted, zero WS instances created and `onConnect` never fired. It does **not** assert a corresponding user-visible warning on the board.
4. **User impact (conditional):** an incorrectly built/deployed board with flag disabled has no live ticket/call feed even if authorized. This is not a data breach, and the UI does not falsely show the green *connected* label: it shows disconnected, but the state is insufficiently explicit for a public operational kiosk.

**Acceptance:** For a production/pilot kiosk require WS enabled in deployment smoke/config gate; or show an explicit first-connect "live queue unavailable/disabled" state while preserving authenticated-only WS. Test flag disabled + successful device session, assert no live rows claim and unambiguous failure state. Assign as residual of existing [`DISPLAYBOOT-FE-001`](https://github.com/drsapaev/final/issues/4063), no new checkbox.

## Residual B — P2 conditional: initial network outage has no prominent stale banner

1. [`DisplayBoardUnified.tsx:1157–1164`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/pages/DisplayBoardUnified.tsx#L1157-L1164) shows the stale WS banner only if `!connected && wsEverConnected`. On fresh mount with failed first token request or WS handshake, `wsEverConnected=false`, so banner is absent; disconnected icon is visible.
2. [`DisplayBoardUnified.tsx:441–459`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/pages/DisplayBoardUnified.tsx#L441-L459) sets `unconfigured` only for `DisplayDeviceProvisioningRequiredError` (401), whereas a network failure keeps `displayDeviceState` as `connecting`.
3. [`ws.ts:181–206`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/api/ws.ts#L181-L206) retries a transient credential request, but it does not inform the parent of the distinction between *never connected* and *temporarily disconnected*; [`DisplayBoardUnified.deviceProvisioning.test.tsx`](https://github.com/drsapaev/final/blob/052be9d3842f3e8baf68cb849b90aeefde2fd70b/frontend/src/pages/__tests__/DisplayBoardUnified.deviceProvisioning.test.tsx) mocks 401 and success, not persistent initial transport failure.
4. **Impact:** a TV may show REST-only aggregate board stats with no live queue feed and only a small disconnected indicator. A repeated outage does not trigger the already-implemented prominent stale warning because it is gated on a successful historical connection.

**Acceptance:** Add fail-first public-board tests for initial network-offline token exchange and first WebSocket handshake that never opens. Assert a prominent "live queue unavailable/connecting failed" state after failure, no anonymous bypass, and clean automatic recovery after a valid device session reconnects. Treat as residual of existing `DISPLAYERROR-FE-001` and `DISPLAYBOOT-FE-001`, not new current-main ID.

**Direct review action:** [post-merge detailed comment on merged #4057](https://github.com/drsapaev/final/pull/4057#issuecomment-6888447790). A comment on a **merged** PR is a request for a *new separate gated fix*, not an edit to the merged branch.

## Group90 ledger and safety boundary

| Metric | Before | Group90 | After |
| --- | ---: | ---: | ---: |
| Unique #4063 audit IDs | 404 | +0 | 404 |
| Historically checked verified source fixes | 38 | +0 | 38 |
| Unchecked, pending individual review | 366 | +0 | 366 |
| New merged #4057 source capabilities | 0 reported by this audit | merge independently observed | yes, but **not pilot E2E** |
| New operational residuals within existing IDs | — | 2 | 2 |
| Group90 source modifications | — | 0 | 0 |

Do **not** mark `DISPLAYBOOT-FE-001` fixed on the sole basis of merged source tests; the original end-to-end public-kiosk purpose still needs correct `VITE_ENABLE_WS` and initial-outage behavior verified. However the feature is substantively implemented: avoid saying "no kiosk auth exists" (obsolete since #4057).

Separate open source fix [#4076](https://github.com/drsapaev/final/pull/4076) is unchanged and remains open/unmerged with the group88–89 blockers; it is not related to this group90 main-merge change.

**Fixing-agent handoff:** new narrowly scoped fix for public-board initial connectivity warning and disabled flag policy, using mandatory `ai/langgraph/scripts/run_agent_gate.ps1` due public clinical display/route state. No protected-source or runtime edits by this auditor; no gate or new tests executed. After every fixing action, post a fresh top-level progress comment in existing #4059 and reconcile #4063 and #4064 truthfully. 