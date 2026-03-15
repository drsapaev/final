# Settings Contract Restoration

`settings` was no longer a safe cleanup candidate because the frontend
`/settings` page was still live while the backend route owner was not mounted.
This slice restored the narrow live contract and removed only proven orphan
residue around that surface.

Verified facts:
- `frontend/src/pages/Settings.jsx` actively called `GET /settings` and
  `PUT /settings`
- `backend/app/api/v1/endpoints/settings.py` existed but was not mounted from
  `backend/app/api/v1/api.py`
- `backend/openapi.json` did not publish `/api/v1/settings`
- auth and permission middleware already reserved `/api/v1/settings` for
  Admin-only access
- `backend/app/services/settings_api_service.py`,
  `backend/app/repositories/settings_api_repository.py`,
  `frontend/src/api/setting.js`, `frontend/src/api/services.js` settings block,
  and `frontend/src/api/endpoints.js` settings block had no live imports after
  review

Contract restoration performed:
- mounted `backend/app/api/v1/endpoints/settings.py` in
  `backend/app/api/v1/api.py`
- expanded the live owner to publish:
  - `GET /api/v1/settings?category=...&limit=...&offset=...`
  - `PUT /api/v1/settings`
- extended the live singular setting service/repository pair to support
  list-with-pagination and single-row upsert
- fixed `frontend/src/pages/Settings.jsx` to send the correct PUT payload shape
  for direct axios usage

Orphan cleanup performed:
- removed detached backend residue:
  - `backend/app/services/settings_api_service.py`
  - `backend/app/repositories/settings_api_repository.py`
- removed orphan frontend residue:
  - `frontend/src/api/setting.js`
  - stale settings block from `frontend/src/api/services.js`
  - stale settings block from `frontend/src/api/endpoints.js`

Documentation and contract sync:
- updated `backend/app/api/v1/endpoints/docs.py`
- updated `docs/API_REFERENCE.md`
- regenerated `backend/openapi.json`
- updated `docs/architecture/W2D_REMAINING_RESIDUE_STRATEGIC_AUDIT.md` to move
  `settings` out of the mixed-risk residue bucket

Effect:
- the live `/settings` surface is restored instead of silently orphaned
- the active Admin settings page no longer depends on an unmounted backend
  contract
- stale detached residue around the settings surface is reduced without
  entering protected auth/payment/queue/EMR work
