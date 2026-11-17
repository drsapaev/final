# Telegram patient Mini App sessions

The Mini App exchanges fresh signed Telegram initData for a patient JWT and
a rotating signed refresh token. Staff authentication and patient portal
web authentication use their existing authorities.

## Contract

- Access JWT: 15 minutes, dedicated issuer and audience, namespaced subject,
  and a server session id. Every patient JWT request checks server expiry,
  revocation, the current active/unblocked Telegram link and patient state.
  Its stored link-generation snapshot must equal the current
  `TelegramUser.patient_link_epoch`; restoring an old link or consent state
  cannot revive previously issued credentials.
- Session/refresh lifetime: seven days from login. Refresh does not extend it.
  Only SHA-256 digests of refresh tokens are stored. Reusing a previously
  rotated, validly signed refresh token revokes that session family.
- Signed initData can create one session, atomically enforced by a unique
  digest in PostgreSQL. Reordering its fields cannot create another session.
  Once exchanged, that initData cannot access the legacy patient routes.
  A new Telegram launch is required after logout or loss of tab credentials.
- Session list returns coarse device labels, timestamps and the current
  session marker. It does not return raw IP, User-Agent or credentials.
- All device operations require the patient Bearer JWT. A bad JWT never
  falls back to initData or an entry link. Entry links keep their existing
  section scope and expiry and cannot manage JWT sessions.
- Mini App credentials use a dedicated sessionStorage namespace and HTTP
  client. They cannot overwrite, refresh or clear a staff login. The client
  retains the existing CSRF cookie/header protection.
- Revoke-one and revoke-others require confirmation in the UI. The existing
  `POST /telegram/mini-app/sessions/revoke-all` route revokes **other**
  sessions and preserves the current one. Explicit logout terminates the
  current access and refresh credentials.
- Reads, successful logins, refreshes and revocations use the patient access
  audit service. Credentials and initData are scrubbed from diagnostics.

## Review and validation

Use the repository Python/pytest wrappers. Focused backend tests:

```text
tests/unit/test_telegram_mini_app_jwt.py
tests/unit/test_telegram_mini_app_sessions_api.py
tests/unit/test_telegram_webhook_security.py
tests/test_openapi_contract.py
```

`tests/integration/test_telegram_mini_app_sessions_pg.py` requires an explicit
local-only `TG_SESSION_PG_ADMIN_URL`. It creates a randomly named database,
upgrades through the parent revision and head, checks RLS/FKs/model parity,
exercises concurrent exchange/refresh/revoke, and drops only the database
it created. A skipped test is not PostgreSQL evidence.

Frontend checks cover the isolated API client, the devices screen, existing
Mini App booking flow and privacy scrubber. Regenerate OpenAPI and generated
API types whenever the explicit credential/session DTOs change.

## Staging and rollout

The patient route must await the official Telegram Web App SDK before reading
launch credentials. Keep SDK loading local to the Mini App; ordinary clinic
screens must not load it. A delayed/failed SDK must not start unauthenticated
patient requests or replace signed server verification. Scoped entry-link
fallbacks remain independent of SDK availability outside Telegram.
The Docker nginx policies allow the exact official SDK script path only for
the original `/telegram/mini-app/patient` request (including its query).
Use the original request URI when selecting that policy: SPA fallback changes
the internal URI to `/index.html`. Other pages retain self-only scripts.
The SDK loads with anonymous CORS and no referrer; retain `require-corp` and
the other security headers. Test a real SDK request instead of injecting
`window.Telegram` when validating these headers.

Before release, complete `STAGING_VALIDATION.md` and record each result.
With synthetic patient data, check two Telegram launches/devices: current
marker, refresh, revoke-one, revoke-others preserving the caller, and logout.
Confirm revoked JWTs and consumed initData are refused; confirm a staff login
in the browser remains intact. Check unknown-user onboarding and scoped
entry links separately.

For real CSRF acceptance, set `CSRF_ENABLED=1` in the owned ephemeral staging
environment before startup. Compose forwards it only to the API; the default
remains `0`. Assert missing/mismatched cookie/header rejection before a signed
launch is consumed, then test successful exchange and the client's bounded
bootstrap/retry. A bootstrap response alone does not prove enforcement.
Verify staff continuity with a real synthetic Admin login and mandatory TOTP
enrollment, not fabricated storage values or directly minted staff credentials.

Browser shims do not prove Telegram WebView behavior. An existing bot can send
one private inline `web_app` button to a verified operator test chat pointing
to an independently owned HTTPS synthetic environment, without changing its
webhook or global menu. Record the separate ingress/credential/message scope
and cleanup before that operation. Never copy Production patients into staging
or start polling/getUpdates as part of this check.

Production deployment uses a clean synced main tree and
`scripts/deploy_restart.ps1`; migration 0103 must precede serving this code.
Do not enable this flow from an unmigrated feature checkout.

If rollout fails, stop release and retain evidence. An application rollback
must retain migration 0103 and its digests: dropping the table loses
revocation/replay history. Reverting to an older initData-only release
restores that release's older authorization behavior and requires a separate
security decision. Never perform a production downgrade as a routine rollback.
