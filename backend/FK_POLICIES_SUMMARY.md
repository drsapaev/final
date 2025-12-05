# Foreign Key Policies Summary

This document lists all FK constraints and their `ondelete` policies after the hardening update.

## Policy Types

- **CASCADE**: Child records are deleted when parent is deleted
- **SET NULL**: Child records are preserved, FK set to NULL when parent is deleted
- **RESTRICT**: Parent deletion is blocked if child records exist

## FK Policies by Model

### Authentication Data (CASCADE)

All authentication-related data is deleted when user is deleted:

- `refresh_tokens.user_id` → CASCADE
- `user_sessions.user_id` → CASCADE
- `password_reset_tokens.user_id` → CASCADE
- `email_verification_tokens.user_id` → CASCADE
- `user_activities.user_id` → CASCADE
- `two_factor_auth.user_id` → CASCADE
- `two_factor_sessions.user_id` → CASCADE
- `two_factor_devices.user_id` → CASCADE
- `two_factor_backup_codes.two_factor_auth_id` → CASCADE
- `two_factor_recovery.two_factor_auth_id` → CASCADE

### User Profile Data (CASCADE)

Profile data is deleted with user:

- `user_profiles.user_id` → CASCADE
- `user_preferences.user_id` → CASCADE
- `user_notification_settings.user_id` → CASCADE
- `user_audit_logs.user_id` → CASCADE
- `user_permission_overrides.user_id` → CASCADE
- `user_permission_overrides.permission_id` → CASCADE

### Medical Records (SET NULL)

Medical records are preserved for audit and legal compliance:

- `emr.appointment_id` → SET NULL
- `prescriptions.appointment_id` → SET NULL
- `prescriptions.emr_id` → SET NULL
- `dermatology_photos.patient_id` → SET NULL (with archiving option)
- `lab_orders.visit_id` → SET NULL
- `lab_orders.patient_id` → SET NULL

### Files (SET NULL)

Files are preserved when owners/patients are deleted:

- `files.owner_id` → SET NULL
- `files.patient_id` → SET NULL
- `files.appointment_id` → SET NULL
- `files.emr_id` → SET NULL
- `files.folder_id` → SET NULL
- `file_folders.parent_id` → SET NULL
- `file_folders.owner_id` → SET NULL
- `file_versions.created_by` → SET NULL
- `file_shares.shared_with_user_id` → SET NULL
- `file_shares.created_by` → SET NULL
- `file_access_logs.file_id` → SET NULL
- `file_access_logs.user_id` → SET NULL

### File Children (CASCADE)

File versions and shares are deleted with file:

- `file_versions.file_id` → CASCADE
- `file_shares.file_id` → CASCADE

### Payment Records (RESTRICT / SET NULL)

Financial integrity is critical:

- `payments.visit_id` → RESTRICT (prevents visit deletion if payment exists)
- `payment_visits.visit_id` → SET NULL (preserve visit record)
- `payment_transactions.payment_id` → SET NULL (preserve for audit)
- `payment_transactions.webhook_id` → SET NULL (preserve for audit)
- `payment_webhooks.payment_id` → SET NULL (preserve for audit)

### Queue Records (SET NULL)

Queue history is preserved for analytics:

- `queue_entries.patient_id` → SET NULL
- `queue_entries.visit_id` → SET NULL
- `queue_tokens.specialist_id` → SET NULL
- `queue_tokens.generated_by_user_id` → SET NULL
- `queue_join_sessions.qr_token` → SET NULL
- `queue_join_sessions.queue_entry_id` → SET NULL

### Queue Children (CASCADE)

Queue entries are deleted with queue:

- `queue_entries.queue_id` → CASCADE

### Appointments (SET NULL)

Appointment history is preserved:

- `appointments.patient_id` → SET NULL (patient can be anonymized)
- `appointments.doctor_id` → SET NULL
- `appointments.department_id` → SET NULL

### Visits (RESTRICT / SET NULL)

Visit integrity is critical:

- `visits.patient_id` → RESTRICT (prevents patient deletion if visits exist)
- `visits.doctor_id` → SET NULL
- `visits.department_id` → SET NULL

### Patients (SET NULL)

Patients can exist without user accounts:

- `patients.user_id` → SET NULL

### Doctors and Clinic (SET NULL)

Doctor/clinic records are preserved:

- `doctors.user_id` → SET NULL
- `doctors.department_id` → SET NULL
- `branches.manager_id` → SET NULL
- `clinic_settings.updated_by` → SET NULL
- `license_activations.activated_by` → SET NULL
- `backups.created_by` → SET NULL

### Doctor Children (CASCADE)

Schedules are deleted with doctor:

- `schedules.doctor_id` → CASCADE

### Services (SET NULL)

Services are preserved:

- `services.department_id` → SET NULL
- `services.category_id` → SET NULL
- `services.doctor_id` → SET NULL

### Schedule Templates (SET NULL)

Schedule templates are preserved:

- `schedule_templates.department_id` → SET NULL
- `schedule_templates.doctor_id` → SET NULL

### Doctor Price Overrides (SET NULL)

Price override records are preserved:

- `doctor_price_overrides.visit_id` → SET NULL
- `doctor_price_overrides.doctor_id` → SET NULL
- `doctor_price_overrides.service_id` → SET NULL
- `doctor_price_overrides.approved_by` → SET NULL

### Role/Permission Audit (SET NULL)

Audit trails are preserved:

- `permission_audit_log.user_id` → SET NULL
- `role_hierarchy.created_by` → SET NULL
- `user_roles.assigned_by` → SET NULL (in M2M table)
- `role_permissions.granted_by` → SET NULL (in M2M table)
- `user_groups_members.added_by` → SET NULL (in M2M table)
- `group_roles.assigned_by` → SET NULL (in M2M table)
- `user_permission_overrides.granted_by` → SET NULL

### Role/Permission M2M (CASCADE)

M2M relationships are deleted with parent:

- `user_roles.user_id` → CASCADE (in M2M table)
- `user_roles.role_id` → CASCADE (in M2M table)
- `role_permissions.role_id` → CASCADE (in M2M table)
- `role_permissions.permission_id` → CASCADE (in M2M table)
- `user_groups_members.user_id` → CASCADE (in M2M table)
- `user_groups_members.group_id` → CASCADE (in M2M table)
- `group_roles.group_id` → CASCADE (in M2M table)
- `group_roles.role_id` → CASCADE (in M2M table)

### Security Events (SET NULL)

Security events are preserved for audit:

- `login_attempts.user_id` → SET NULL
- `security_events.user_id` → SET NULL
- `security_events.resolved_by` → SET NULL

### Telegram (SET NULL)

Telegram links are preserved:

- `telegram_users.user_id` → SET NULL
- `telegram_users.patient_id` → SET NULL
- `telegram_messages.sent_by_user_id` → SET NULL

### Visit Children (CASCADE)

Visit services are deleted with visit:

- `visit_services.visit_id` → CASCADE
- `payment_visits.visit_id` → CASCADE (junction table, but visit preserved)
- `payment_invoice_visits.visit_id` → SET NULL (preserve visit)

### Payment Children (CASCADE)

Payment visits are deleted with payment:

- `payment_visits.payment_id` → CASCADE
- `payment_invoice_visits.invoice_id` → CASCADE

### Equipment and Licenses (CASCADE)

- `equipment_maintenance.equipment_id` → CASCADE
- `license_activations.license_id` → CASCADE

## Summary Statistics

- **Total FK constraints updated**: 140+
- **CASCADE policies**: ~45 (authentication, profiles, M2M tables, children)
- **SET NULL policies**: ~90 (medical records, files, payments, audit trails)
- **RESTRICT policies**: 2 (visits.patient_id, payments.visit_id)

## Verification

After database reset, verify:

1. Run `python backend/verify_fk_enforcement.py` - must show FK enforcement enabled
2. Run `python backend/validate_fk_policies.py` - must show all FKs validated
3. Run `python backend/app/scripts/audit_foreign_keys.py` - must show 0 orphaned records

## Database Reset

To apply these changes:

```powershell
cd backend
.\reset_database.ps1
```

This will:
1. Backup existing database
2. Delete all database files
3. Run `alembic upgrade head` to create fresh schema
4. Verify FK enforcement
5. Check for orphaned records

