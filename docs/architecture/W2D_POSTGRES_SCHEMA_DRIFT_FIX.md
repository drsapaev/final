## Wave 2D Postgres Schema Drift Fix

Date: 2026-03-10  
Branch: `codex/post-w2c-postgres-schema-drift-fix`

## Exact mismatch fixed

The Postgres pilot originally failed during `Base.metadata.create_all(...)`
because:

- `doctor_treatment_templates.doctor_id` was declared as `String(36)`
- it referenced `users.id`
- `users.id` is `Integer`

SQLite tolerated this mismatch, but Postgres rejected it with
`DatatypeMismatch`.

## Intended FK ownership

The intended relation is:

- `doctor_treatment_templates.doctor_id -> users.id`

This is supported by:

- the ORM relationship in [doctor_templates.py](C:/final/backend/app/models/doctor_templates.py)
- the reciprocal relationship in [user.py](C:/final/backend/app/models/user.py)
- API usage through authenticated `current_user.id`
- service-layer reads/writes that conceptually use the user account as the
  owner of the doctor treatment memory

This feature does **not** currently target `doctors.id`.

## Narrow fix applied

- Changed `DoctorTreatmentTemplate.doctor_id` from `String(36)` to `Integer`
- kept the foreign key target as `users.id`
- removed `str(doctor_id)` casts in:
  - [doctor_templates_service.py](C:/final/backend/app/services/doctor_templates_service.py)
  - [emr_v2_service.py](C:/final/backend/app/services/emr_v2_service.py)
- added a narrow schema guard test:
  - [test_doctor_treatment_template_schema.py](C:/final/backend/tests/unit/test_doctor_treatment_template_schema.py)

## Result

This fixed the original Postgres schema-bootstrap blocker.

The Postgres pilot now proceeds past metadata creation and reaches allocator
test execution, where new issues are surfaced honestly.

## Newly surfaced follow-on drift

After this fix, the pilot exposed additional SQLite-vs-Postgres differences:

1. `DailyQueue.specialist_id` foreign key enforcement now fails in one pilot
   characterization path because the test data passes a user id where the
   schema expects a `doctors.id`.
2. `queue_entries.source` currently uses `String(20)`, but the
   `force_majeure_transfer` source value exceeds that length under Postgres.
3. One concurrency pilot case now shows a session/refresh issue under the
   Postgres lane.

These are separate issues from the original `doctor_treatment_templates`
mismatch and should be handled as follow-on pilot work, not folded into this
fix.

## Out of scope

- broad schema redesign
- broad fixture rewrite
- full test-stack migration to Postgres
- unrelated queue behavior changes
