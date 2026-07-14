# Frontend-Backend Parity Report

Generated at: 2026-07-14T07:44:26.746325+00:00

## Summary

- Backend operations total: **1142**
- Frontend calls total: **167**
- Implemented matches: **154**
- Partial (unresolved frontend calls): **13**
- Missing in frontend: **996**
- Frontend orphan calls: **0**
- Coverage: **13.49%**

## Critical Missing (auth/queue/billing/emr)

- `/api/v1/auth`: **21** missing operations
- `/api/v1/queue`: **31** missing operations
- `/api/v1/billing`: **16** missing operations
- `/api/v1/emr`: **62** missing operations

## Critical Flows

- Passed: **4** / **4**

- `registrar_queue` (Registrar Queue): **pass** (5/5)
- `doctor_emr_rw` (Doctor EMR Read/Write): **pass** (5/5)
- `cashier_payment` (Cashier Payment Status/Receipt): **pass** (5/5)
- `admin_settings` (Admin Settings): **pass** (8/8)

## RBAC Alignment

- Status: **pass**
- Frontend-only roles: **0**
- Backend-only roles: **0**
- Route mismatches: **0**

## Partial Preview (first 40)

- `GET` `url` (frontend/src/api/mcpClient.js:45) reason=`unresolved_expression`
- `POST` `url` (frontend/src/api/mcpClient.js:48) reason=`unresolved_expression`
- `PUT` `url` (frontend/src/api/mcpClient.js:51) reason=`unresolved_expression`
- `PATCH` `url` (frontend/src/api/mcpClient.js:54) reason=`unresolved_expression`
- `DELETE` `url` (frontend/src/api/mcpClient.js:57) reason=`unresolved_expression`
- `GET` `cacheKey` (frontend/src/api/messages.js:81) reason=`unresolved_expression`
- `GET` `cacheKey` (frontend/src/api/messages.js:125) reason=`unresolved_expression`
- `GET` `cacheKey` (frontend/src/api/services.js:75) reason=`unresolved_expression`
- `GET` `cleanUrl` (frontend/src/hooks/useAdminData.js:45) reason=`unresolved_expression`
- `GET` `endpoint` (frontend/src/hooks/useApi.js:79) reason=`unresolved_expression`
- `POST` `endpoint` (frontend/src/hooks/useApi.js:217) reason=`unresolved_expression`
- `GET` `endpoint` (frontend/src/hooks/useUserPreferences.js:77) reason=`unresolved_expression`
- `PUT` `endpoint` (frontend/src/hooks/useUserPreferences.js:128) reason=`unresolved_expression`

## Frontend Orphan Preview (first 40)

