# DISPLAYBOOT-FE-001 — scoped design: provisioning of credentials for public TV boards

**Status:** APPROVED — Variant A, per owner decision. Implementation includes backend device provisioning, board-bound 60-minute JWTs, revocation, and the kiosk setup flow.
**Source:** finding `DISPLAYBOOT-FE-001` (P1/P2), audit dossier `docs/audits/2026-11-09-queue-position-notifications-source-review.md` (round 32, draft PR #3961), re-verified against `main` @ `233b38cd5992` (2026-11-12).
**Decision record:** Variant A; 60-minute device JWTs; rotation on request; the existing public aggregate endpoint remains unchanged; credentials are stored in the kiosk profile's localStorage; backend and frontend land together.

## 1. Problem (re-verified against the current main)

The public routes `/display-board` and `/display-board/:role` (`frontend/src/routing/routeRegistry.ts`, entries `display-board` / `display-board-role`) render `DisplayBoardUnified` without a login interface — a TV set-top box in a waiting room physically cannot pass an interactive login.

At the same time:

- The WS client sends the subprotocol `bearer.<jwt>` only if `tokenManager.getAccessToken()` is non-empty (`frontend/src/api/ws.ts`), and with `VITE_ENABLE_WS` unset the opener is a no-op by default.
- The backend display WebSocket **requires** a token and closes the connection with `1008` in its absence (`backend/app/api/v1/endpoints/display_websocket.py`, QUEUE-AUDIT-28 P0-2) — anonymous WS was removed deliberately: the snapshot contains patient names (format per the board's `show_patient_names` policy), tickets, doctors, and offices.
- The public `GET /board/state` returns only aggregate statistics, without queue rows or current calls.

The result: a TV that is not provisioned with credentials receives a "gray" board without live rows — while looking outwardly operational. A staff user with a token works; deployments may configure a kiosk session separately — but the system has no product mechanism for such provisioning at all: neither an interface, nor a role, nor a principal type.

**Hard constraint from the finding:** PHI-bearing WS must not be made anonymous. Any solution must keep authorization, but add a *device* principal.

## 2. Variants

### A. Board-scoped kiosk device credentials — RECOMMENDED

The admin provisions a **device identity per board**; the TV exchanges it for a short-lived board-scoped JWT.

Backend:

1. New table `display_board_devices`: `id`, `board_id` (FK → `display_boards`), `device_name`, `secret_hash` (argon2/bcrypt, the secret itself is not stored), `status` (`active` / `revoked`), `last_connected_at`, `created_by`, `created_at`, `rotated_at`. There is no secret in the DB — only the hash.
2. Endpoints (Admin role):
   - `POST /api/v1/admin/display/boards/{board_id}/devices` — creates a device, returns the secret **once** (for scanning/copying into the kiosk); response is not logged.
   - `GET /api/v1/admin/display/boards/{board_id}/devices` — lists metadata only; never returns secret material.
   - `DELETE /api/v1/admin/display/devices/{device_id}` — revocation (`status=revoked`).
   - `POST /api/v1/admin/display/boards/{board_id}/devices/{device_id}/rotate` — rotation with a new one-time secret.
3. Exchange `POST /api/v1/display/devices/token` (device_id + secret): on success issues a short-lived JWT with `typ=display_device`, `board_id=<bound board>`, `jti` (blacklist-compatible, the same `TokenBlacklist` as for humans), TTL 60 min. Rate limiting on this endpoint is mandatory (protection against brute-force of the secret).
4. Display-WS authorization: a separate `display_device` principal is allowed **only** for the board bound by the claim, **only** when `DisplayBoard.active=True` and the device is active; it updates `last_connected_at`. Existing connections re-check the token, device version, and board/device status every 15 seconds, so revocation, rotation, or board deactivation closes the socket within 30 seconds.
5. Name masking is unchanged: the device principal receives the same snapshot as the staff for this board — the privacy policy is governed by the board, not by the principal type.

Frontend (kiosk boot-flow):

- No staff token and no device credential → an honest **provisioning screen** ("The board is not configured. Ask the administrator to provision a device") — this is exactly the "explicit protected-setup/credential-required state" required by the fail-first from the finding, instead of a fake-empty board.
- With a credential → silent exchange → WS connection; the secret is stored in `localStorage` of the kiosk profile; a URL parameter like `?forget-device=1` clears it.
- The staff token takes precedence (a TV logged in under a staff account behaves as it does today).

### B. Interactive login under a dedicated "Display" account

A staff account is created for the TV (a new `Display` role or reusing an existing one), a one-time interactive login is done on the TV.

- Pros: almost zero backend changes.
- Cons: a shared "human" credential on a public device; the token covers **all** boards (no board scoping); rotation = manual re-login; the audit log shows an impersonal account; password entry on a TV remote control is painful. Weak from the security standpoint for a public device.

### C. Static device tokens from configuration

Ops generates a token per board, placed in env/localStorage of the kiosk.

- Pros: no DB migration.
- Cons: rotation = redeploy/config change; no revocation semantics; secret sprawl; no `jti`/blacklist. Fails the verifiability bar adopted in this repo.

### D. Anonymous WS without PHI — REJECTED

Directly prohibited by the finding: rows contain tickets, doctors, offices, and patient names, and the masking policy is governed by the board (including `full`). An anonymous channel would make the privacy policy a client-side wish, not an authorization boundary.

## 3. RBAC matrix (variant A)

| Principal | Resources | Actions |
| --- | --- | --- |
| Admin | `/display/boards/*/devices*`, `/display/devices/*` | create / revoke / rotate devices |
| display_device (JWT) | its own board: `WS /ws/board/{board}` with claim==board, `GET /board/state` (aggregate) | read-only; denied: any other board (1008), any PHI REST, admin endpoints, exchange after revocation |
| staff (existing) | as today | no changes |
| anonymous | public aggregate `/board/state` | as today, without WS rows |

## 4. Fail-first tests (synthetic, without real PHI)

1. Public route without a token and without a credential → the provisioning screen is rendered, WS is not opened, the board is not represented as "live and empty".
2. Provisioned device: exchange → WS → only its board is received; a snapshot with masking per the board's policy.
3. Cross-board: a device token for `waiting_room_1` against `WS /ws/board/main_board` → `1008` before subscribing to the room.
4. Revocation: `status=revoked` / `DisplayBoard.active=False` → the exchange fails; the next WS reconnect is closed with `1008` (repeats the recovery honesty semantics from #4012/#4039).
5. TTL: expiration of the display-device JWT → reconnect requires a new exchange; `jti` goes through `TokenBlacklist` (repeats the DISPLAYAUTH-BE-001 contract).
6. Rate limit: N failed exchanges from one IP → 429; the secret is never returned again after creation (only the hash).

## 5. Risks and limitations

- A new table + 3–4 endpoints + a kiosk boot-flow — the largest implementation scope among the variants, but everything is additive, without migrations of existing tables (a new table, a new principal type — a backward-compatible extension of `_is_display_staff`).
- The secret in the TV's `localStorage` — an XSS on the public route would gain access to the device secret; the blast radius is limited (one board, read-only, revocable); the TV does not store user PHI.
- The exchange endpoint becomes the target of brute force — mandatory rate limiting + a secret of sufficient entropy (≥32 bytes base64url).
- The audit of device connections is kept minimal (last_connected_at); a full connection log is possible as a follow-up.

## 6. Decision details

- Token lifetime is 60 minutes. The kiosk silently exchanges its stored device credential whenever it opens or reconnects its WebSocket.
- Rotation is available to an administrator on request; no forced rotation interval was selected.
- The device principal receives no added REST access. The existing public `GET /board/state` remains aggregate-only and unchanged.
- The kiosk profile stores the per-board device id and one-time secret in localStorage. `?forget-device=1` clears that board's saved credential.
- Backend provisioning and the kiosk flow are implemented together so public boards do not ship in an unconfigured, blank-live state.
