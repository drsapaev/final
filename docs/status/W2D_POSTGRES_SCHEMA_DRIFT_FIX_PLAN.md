## Scope

- Target mismatch: `doctor_treatment_templates.doctor_id -> users.id`
- Narrow fix only for the invalid FK/type combination surfaced by the Postgres pilot harness

## Observed mismatch

- Current ORM model in [doctor_templates.py](C:/final/backend/app/models/doctor_templates.py) defines:
  - `doctor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)`
- Current referenced PK in [user.py](C:/final/backend/app/models/user.py) defines:
  - `User.id: Integer`
- Postgres rejects this foreign key during `Base.metadata.create_all(...)` with `DatatypeMismatch`

## Intended target relation

- The intended ownership is `doctor_treatment_templates.doctor_id -> users.id`
- Evidence:
  - relationship is `DoctorTreatmentTemplate.doctor -> User`
  - reciprocal relationship is `User.treatment_templates -> DoctorTreatmentTemplate`
  - API layer passes `current_user.id`
  - service layer writes and queries by the authenticated user id, not `doctors.id`
- `doctors.id` is a different entity in [clinic.py](C:/final/backend/app/models/clinic.py) and is not the current owner for this feature

## Chosen narrow fix

- Change `DoctorTreatmentTemplate.doctor_id` from `String(36)` to `Integer`
- Keep the FK target as `users.id`
- Remove local `str(doctor_id)` casts in the treatment-template services so runtime usage matches the corrected schema

## Why this is the narrowest correct fix

- It preserves the already-established domain owner (`User`)
- It fixes the concrete Postgres-invalid schema instead of hiding it
- It avoids a broader redesign of doctor/user ownership across the app

## Explicitly out of scope

- Broad doctor/user schema refactor
- Reworking other doctor-related tables
- Full Alembic migration coverage for this feature family
- Broad Postgres test-stack migration
- Any queue/runtime behavior changes outside the pilot harness
