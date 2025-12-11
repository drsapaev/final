"""
Script to add ONDELETE clauses to all ForeignKey constraints
This is a documentation of how to properly handle FK cascades.

Run: python add_ondelete_to_fks.py
"""

# This script documents the recommended ONDELETE policies for each table

FK_ONDELETE_POLICIES = {
    # === MEDICAL DATA (NEVER CASCADE DELETE) ===
    # Medical data should never be deleted when parent records are deleted
    # to preserve audit trail and comply with medical record retention laws
    
    "emr.patient_id": "SET NULL",  # Preserve EMR even if patient deleted
    "emr.visit_id": "SET NULL",  # Preserve EMR even if visit deleted
    "emr.doctor_id": "SET NULL",  # Preserve EMR even if doctor deleted
    "emr.created_by": "SET NULL",
    
    "lab_results.patient_id": "SET NULL",  # Preserve lab results
    "lab_results.order_id": "SET NULL",
    "lab_results.created_by": "SET NULL",
    
    "lab_orders.doctor_id": "SET NULL",
    "lab_orders.patient_id": "SET NULL",
    "lab_orders.visit_id": "SET NULL",
    
    "files.patient_id": "SET NULL",  # Already has ondelete
    "files.owner_id": "RESTRICT",  # Files must have owner - already has
    "files.emr_id": "SET NULL",
    "files.appointment_id": "SET NULL",
    
    "medical_records.patient_id": "SET NULL",
    "medical_records.doctor_id": "SET NULL",
    
    "prescriptions.patient_id": "SET NULL",
    "prescriptions.doctor_id": "SET NULL",
    
    # === PATIENT DATA ===
    "patients.created_by": "SET NULL",
    
    # === APPOINTMENTS & VISITS ===
    "appointments.patient_id": "SET NULL",  # Preserve appointment history
    "appointments.doctor_id": "SET NULL",
    "appointments.created_by": "SET NULL",
    
    "visits.patient_id": "SET NULL",  # Preserve visit history
    "visits.doctor_id": "SET NULL",
    "visits.appointment_id": "SET NULL",
    
    # === PAYMENTS (AUDIT CRITICAL) ===
    # Payment data must NEVER be deleted for financial audit compliance
    
    "payments.patient_id": "RESTRICT",  # Cannot delete patient with payments
    "payments.visit_id": "SET NULL",  # Preserve payment even if visit deleted
    "payments.cashier_id": "SET NULL",
    
    "payment_transactions.payment_id": "SET NULL",  # Already has ondelete
    "payment_transactions.webhook_id": "SET NULL",  # Already has ondelete
    
    "invoices.patient_id": "RESTRICT",  # Cannot delete patient with invoices
    "invoices.visit_id": "SET NULL",
    "invoices.created_by": "SET NULL",
    
    "invoice_items.invoice_id": "CASCADE",  # Delete items with invoice
    "invoice_items.service_id": "SET NULL",
    
    # === QUEUE SYSTEM ===
    "queue_entries.queue_id": "CASCADE",  # Already has ondelete
    "queue_entries.patient_id": "SET NULL",  # Already has ondelete
    "queue_entries.visit_id": "SET NULL",  # Already has ondelete
    
    "daily_queues.specialist_id": "SET NULL",
    
    # === USER AUTHENTICATION (CASCADE OK) ===
    # Session and auth data can safely be deleted with user
    
    "refresh_tokens.user_id": "CASCADE",  # Already has ondelete
    "password_resets.user_id": "CASCADE",  # Already has ondelete
    "two_factor_auth.user_id": "CASCADE",  # Already has ondelete
    "login_history.user_id": "CASCADE",  # Already has ondelete
    "sessions.user_id": "CASCADE",  # Already has ondelete
    
    # === FILE SYSTEM ===
    "file_versions.file_id": "CASCADE",  # Already has ondelete
    "file_shares.file_id": "CASCADE",  # Already has ondelete
    "file_folders.parent_id": "SET NULL",
    
    # === NOTIFICATIONS ===
    "notifications.user_id": "CASCADE",
    "notifications.patient_id": "SET NULL",
    
    # === BILLING ===
    "billing.patient_id": "SET NULL",
    "billing.visit_id": "SET NULL",
    "billing.appointment_id": "SET NULL",
    "billing.created_by": "SET NULL",
    
    # === DISCOUNT/BENEFITS ===
    "discount_usages.discount_id": "CASCADE",
    "discount_usages.patient_id": "SET NULL",
    "discount_usages.visit_id": "SET NULL",
    
    "benefit_usages.benefit_id": "CASCADE",
    "benefit_usages.patient_id": "SET NULL",
    
    # === AI CONFIG ===
    "ai_model_configs.provider_id": "CASCADE",
    "ai_usage_logs.provider_id": "SET NULL",
    "ai_usage_logs.user_id": "SET NULL",
    
    # === DERMATOLOGY ===
    "dermatology_photos.patient_id": "RESTRICT",  # Already has ondelete
    "dermatology_photos.uploaded_by": "SET NULL",
    
    # === DEPARTMENTS ===
    "department_services.department_id": "CASCADE",  # Already has ondelete
    "department_services.service_id": "CASCADE",  # Already has ondelete
    
    # === EQUIPMENT ===
    "equipment_maintenance.equipment_id": "CASCADE",  # Already has ondelete
    "equipment_usage.equipment_id": "CASCADE",
    
    # === LICENSES ===
    "license_history.license_id": "CASCADE",  # Already has ondelete
    
    # === SCHEDULES ===
    "schedules.doctor_id": "CASCADE",
    "schedule_exceptions.schedule_id": "CASCADE",
    
    # === SALARY ===
    "salary_history.user_id": "SET NULL",  # Preserve salary history
    
    # === ODONTOGRAM ===
    "odontograms.patient_id": "SET NULL",  # Preserve dental records
    "odontogram_teeth.odontogram_id": "CASCADE",
    
    # === AUDIT ===
    "audit_logs.user_id": "SET NULL",  # Preserve audit logs
    
    # === MESSAGES ===
    "messages.sender_id": "SET NULL",  # Preserve messages
    "messages.recipient_id": "SET NULL",
    
    # === TELEGRAM ===
    "telegram_users.patient_id": "SET NULL",
    "telegram_users.user_id": "SET NULL",
}

# Priority rules for ondelete:
# 1. RESTRICT - Prevents deletion of parent record (use for critical relationships)
#    - Patient with unpaid invoices
#    - Patient with medical records that must be retained
#
# 2. SET NULL - Allows deletion, sets FK to NULL (use for most cases)
#    - Audit trails (created_by, updated_by)
#    - Historical references (doctor who was deleted)
#    - Medical records (preserve even if linked record deleted)
#
# 3. CASCADE - Deletes child records when parent deleted (use carefully)
#    - Session tokens when user deleted
#    - Invoice items when invoice deleted
#    - File versions when file deleted
#
# 4. NO ACTION - Database default, may cause FK constraint errors

def print_migration_code():
    """Generate Alembic migration code for FK updates"""
    
    print("""
# Migration to add ONDELETE clauses to ForeignKey constraints
# IMPORTANT: This is a destructive migration - backup database first!

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Example migration for a single FK:
    # op.drop_constraint('fk_table_column', 'table', type_='foreignkey')
    # op.create_foreign_key(
    #     'fk_table_column', 'table', 'parent_table',
    #     ['column'], ['id'], ondelete='SET NULL'
    # )
    pass

def downgrade():
    pass
""")

if __name__ == "__main__":
    print("FK ONDELETE Policy Documentation")
    print("=" * 50)
    
    # Group by table
    tables = {}
    for fk, policy in FK_ONDELETE_POLICIES.items():
        table, column = fk.split(".")
        if table not in tables:
            tables[table] = []
        tables[table].append((column, policy))
    
    for table in sorted(tables.keys()):
        print(f"\n{table}:")
        for column, policy in tables[table]:
            print(f"  {column}: {policy}")
    
    print("\n" + "=" * 50)
    print("Total FKs documented:", len(FK_ONDELETE_POLICIES))
