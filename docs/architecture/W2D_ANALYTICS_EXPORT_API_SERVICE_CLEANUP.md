# Analytics Export API Service Cleanup

`backend/app/services/analytics_export_api_service.py` was a detached
router-style duplicate of the mounted analytics export endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/analytics_export.py` with
  `prefix="/analytics/export"`
- `backend/openapi.json` exposes the live
  `/api/v1/analytics/export/formats`,
  `/api/v1/analytics/export/kpi/export/{format}`,
  `/api/v1/analytics/export/comprehensive/export/{format}`,
  `/api/v1/analytics/export/doctors/performance/export/{format}`,
  `/api/v1/analytics/export/revenue/export/{format}`, and
  `/api/v1/analytics/export/health` routes owned by the mounted endpoint file
- no live source imports of
  `backend/app/services/analytics_export_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/analytics_export_api_service.py` duplicated the router
  logic already owned by
  `backend/app/api/v1/endpoints/analytics_export.py`, with only typing/import
  drift

Cleanup performed:
- removed `backend/app/services/analytics_export_api_service.py`

Effect:
- no mounted runtime route was removed
- live analytics export route ownership remains unchanged
- one more dead router-style service duplicate is gone
