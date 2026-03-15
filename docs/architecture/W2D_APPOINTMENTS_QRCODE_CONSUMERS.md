# W2D Appointments QRCode Consumers

Date: 2026-03-11
Mode: docs-only review

## Consumer audit summary

Confirmed in-repo consumer evidence for `GET /api/v1/appointments/qrcode` was
not found.

## Findings

### Mounted route owner

- file: `backend/app/api/v1/endpoints/appointments.py`
- reference: `@router.get("/qrcode", name="qrcode_png")`
- consumer type: mounted route definition
- live/runtime: yes
- confidence: high

This confirms the route exists, but not that another in-repo caller uses it.

### Frontend QR constant points elsewhere

- file: `frontend/src/api/endpoints.js`
- reference: `QUEUE.GENERATE_QR = '/queue/qrcode'`
- consumer type: adjacent frontend QR path
- live/runtime: likely
- confidence: high

This is evidence against `appointments/qrcode` being the active frontend QR
surface.

### Tests

No backend or frontend tests were found that directly target
`/appointments/qrcode`.

### Docs

Existing legacy-inventory docs already classify this route as support-only:

- `docs/status/W2C_ONLINEDAY_LIVE_DEAD_MAP.md`
- `docs/architecture/W2D_ONLINEDAY_CLEANUP_INVENTORY.md`

That classification matches the code evidence.

## Consumer verdict

Current in-repo evidence suggests:

- mounted route: yes
- confirmed live caller: no
- active frontend dependency: not found
- likely role: compatibility/support helper

External or manual use cannot be ruled out completely because the route remains
mounted, but the in-repo signal is weak.
