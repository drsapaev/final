# W2D API Reference New Modules Links Verification

## Summary

This was a bounded docs-vs-code verification pass for the remaining footer
sections in `docs/API_REFERENCE.md`.

The goal was to correct high-confidence drift in `New Modules` and `Links`
without turning the file into a generated route dump or changing runtime
behavior.

## Findings

### The old `New Modules` block mixed real families with non-published routes

- the previous footer still advertised:
  - `/cardio/ecg/upload`
  - `/cardio/ecg/{id}/interpret`
  - `/dental/odontogram*`
  - `/messages/audio`
- those routes are not present in the current generated contract
- the live mounted families are broader and different:
  - cardio publishes `/cardio/ecg`, `/cardio/blood-tests`, and
    `/cardio/risk-assessment`
  - dental publishes `examinations`, `treatments`, `prosthetics`, `xray`, and
    the price-override flow
  - messaging publishes `send`, `upload`, `send-voice`,
    `voice/{message_id}/stream`, and conversation helpers
  - monitoring publishes `health`, `metrics`, `history`, `summary`, `alerts`,
    `thresholds`, and `collect`

### The old `Links` block was partly correct and partly misleading

- `/docs`, `/redoc`, and `/openapi.json` are still canonical generated-doc
  entrypoints
- the old external `wss://api.clinic.example.com/ws/` example was a placeholder
  and not a trustworthy runtime link
- live custom documentation helpers also exist under `/api/v1/docs/*`
- websocket entrypoints are real, but they are not part of OpenAPI and should
  be described as route families, not as one fake canonical URL

## What changed

- reframed `New Modules` as a curated pointer map instead of a stale versioned
  release-note block
- replaced the non-published ECG, odontogram, and generic audio claims with
  current cardio, dental, messaging, and monitoring families
- added the specific drift note that AI ECG interpretation now lives under the
  AI route families rather than under `/cardio/ecg/{id}/interpret`
- updated `Links` to distinguish canonical generated docs from custom
  `/api/v1/docs/*` helpers
- replaced the placeholder websocket host with current mounted websocket family
  guidance

## Evidence used

- `backend/openapi.json`
- `backend/app/main.py`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/cardio.py`
- `backend/app/api/v1/endpoints/dental.py`
- `backend/app/api/v1/endpoints/messages.py`
- `backend/app/api/v1/endpoints/system_management.py`
- `backend/app/api/v1/endpoints/docs.py`
- websocket owners under `backend/app/ws/*`

## Recommended next step

The bounded `API_REFERENCE.md` footer/reference track is now effectively
exhausted.

The next honest low-risk move is a custom docs audit for the mounted
`/api/v1/docs/*` pages, because `backend/app/api/v1/endpoints/docs.py` still
contains stale embedded examples and counts even after the curated
`API_REFERENCE.md` footer was corrected.
