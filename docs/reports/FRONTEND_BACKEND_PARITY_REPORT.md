# Frontend-Backend Parity Report

Generated at: 2026-03-06T07:40:50.334373+00:00

## Summary

- Backend operations total: **1112**
- Frontend calls total: **222**
- Implemented matches: **128**
- Partial (unresolved frontend calls): **6**
- Missing in frontend: **990**
- Frontend orphan calls: **88**
- Coverage: **11.51%**

## Critical Missing (auth/queue/billing/emr)

- `/api/v1/auth`: **24** missing operations
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

- `GET` `cleanUrl` (frontend/src/hooks/useAdminData.js:45) reason=`unresolved_expression`
- `GET` `endpoint` (frontend/src/hooks/useApi.js:79) reason=`unresolved_expression`
- `POST` `endpoint` (frontend/src/hooks/useApi.js:217) reason=`unresolved_expression`
- `POST` `userCreateUrl` (frontend/src/hooks/useDoctors.js:55) reason=`unresolved_expression`
- `GET` `endpoint` (frontend/src/hooks/useUserPreferences.js:76) reason=`unresolved_expression`
- `PUT` `endpoint` (frontend/src/hooks/useUserPreferences.js:125) reason=`unresolved_expression`

## Frontend Orphan Preview (first 40)

- `GET` `/api/v1/visits` (frontend/src/api/client.js:214)
- `POST` `/api/v1/auth/logout` (frontend/src/api/services.js:31)
- `POST` `/api/v1/auth/refresh` (frontend/src/api/services.js:38)
- `GET` `/api/v1/users` (frontend/src/api/services.js:51)
- `GET` `/api/v1/users/{id}` (frontend/src/api/services.js:58)
- `POST` `/api/v1/users` (frontend/src/api/services.js:65)
- `PUT` `/api/v1/users/{id}` (frontend/src/api/services.js:74)
- `DELETE` `/api/v1/users/{id}` (frontend/src/api/services.js:83)
- `GET` `/api/v1/users/roles` (frontend/src/api/services.js:90)
- `GET` `/api/v1/users/permissions` (frontend/src/api/services.js:97)
- `GET` `/api/v1/patients/stats` (frontend/src/api/services.js:159)
- `GET` `/api/v1/doctors` (frontend/src/api/services.js:172)
- `GET` `/api/v1/doctors/{id}` (frontend/src/api/services.js:179)
- `POST` `/api/v1/doctors` (frontend/src/api/services.js:186)
- `PUT` `/api/v1/doctors/{id}` (frontend/src/api/services.js:195)
- `DELETE` `/api/v1/doctors/{id}` (frontend/src/api/services.js:204)
- `GET` `/api/v1/doctors/specializations` (frontend/src/api/services.js:211)
- `GET` `/api/v1/doctors/departments` (frontend/src/api/services.js:218)
- `GET` `/api/v1/doctors/{id}/schedule` (frontend/src/api/services.js:226)
- `GET` `/api/v1/doctors/{id}/availability` (frontend/src/api/services.js:234)
- `GET` `/api/v1/appointments/patient/{patientId}` (frontend/src/api/services.js:295)
- `GET` `/api/v1/appointments/doctor/{doctorId}` (frontend/src/api/services.js:303)
- `GET` `/api/v1/appointments/by-date` (frontend/src/api/services.js:312)
- `POST` `/api/v1/appointments/{id}/cancel` (frontend/src/api/services.js:319)
- `POST` `/api/v1/appointments/{id}/confirm` (frontend/src/api/services.js:326)
- `GET` `/api/v1/queue` (frontend/src/api/services.js:339)
- `GET` `/api/v1/queue/{id}` (frontend/src/api/services.js:346)
- `POST` `/api/v1/queue` (frontend/src/api/services.js:353)
- `PUT` `/api/v1/queue/{id}` (frontend/src/api/services.js:362)
- `DELETE` `/api/v1/queue/{id}` (frontend/src/api/services.js:371)
- `GET` `/api/v1/queue/stats` (frontend/src/api/services.js:379)
- `GET` `/api/v1/queue/by-department` (frontend/src/api/services.js:388)
- `POST` `/api/v1/queue/call-next` (frontend/src/api/services.js:395)
- `POST` `/api/v1/queue/{id}/skip` (frontend/src/api/services.js:404)
- `POST` `/api/v1/queue/{id}/complete` (frontend/src/api/services.js:411)
- `GET` `/api/v1/services/by-department` (frontend/src/api/services.js:465)
- `GET` `/api/v1/services/pricing` (frontend/src/api/services.js:473)
- `GET` `/api/v1/analytics/revenue` (frontend/src/api/services.js:502)
- `GET` `/api/v1/analytics/patients` (frontend/src/api/services.js:510)
- `GET` `/api/v1/analytics/appointments` (frontend/src/api/services.js:518)
