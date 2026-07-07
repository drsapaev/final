# Data Retention Policy

## HIPAA §164.530(j) — Retention Requirements

### Audit Logs
- **Retention**: 6 years (HIPAA minimum)
- **Tables**: audit_logs, security_events, user_activities
- **Action**: Auto-delete records older than 6 years via scheduled job

### Medical Records (EMR)
- **Retention**: Lifetime of patient + 10 years (medical record retention)
- **Tables**: emr_records, emr_versions, lab_report_instances
- **Action**: Archive to cold storage after 10 years

### Chat Messages
- **Retention**: 1 year
- **Tables**: messages, ai_chat_messages
- **Action**: Auto-delete messages older than 1 year (configurable)

### Payment Records
- **Retention**: 7 years (tax/financial record retention)
- **Tables**: payments, payment_invoices, refund_requests
- **Action**: Archive to cold storage after 7 years

### Notification History
- **Retention**: 90 days
- **Tables**: notification_deliveries, notification_events
- **Action**: Auto-delete after 90 days

### Telegram Messages
- **Retention**: 6 months
- **Tables**: telegram_messages
- **Action**: Auto-delete after 6 months

### File Attachments
- **Retention**: Lifetime of associated record
- **Tables**: files, file_versions
- **Action**: Delete physical files when associated record is deleted

### Login Attempts
- **Retention**: 90 days
- **Tables**: login_attempts
- **Action**: Auto-delete after 90 days (already implemented in CRUD)

## Secret Rotation Procedure

### SECRET_KEY (JWT signing)
- **Rotation period**: 90 days
- **Procedure**:
  1. Generate new key: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
  2. Update SECRET_KEY env var
  3. Deploy — old tokens become invalid (users must re-login)
  4. Alternatively: use key rotation with `jwt.decode(key=old_key)` fallback for 24h

### ENCRYPTION_KEY (Fernet — bot tokens, API keys)
- **Rotation period**: 180 days
- **Procedure**:
  1. Generate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  2. Run migration script to re-encrypt all data with new key
  3. Update ENCRYPTION_KEY env var
  4. Deploy

### Provider API Keys (OpenAI, Gemini, DeepSeek, Click, PayMe, Kaspi)
- **Rotation period**: 90 days
- **Procedure**:
  1. Generate new API key via provider dashboard
  2. Update via admin UI (Settings → AI Providers / Payment Providers)
  3. Verify new key works via test endpoint
  4. Revoke old key via provider dashboard

### Telegram Bot Token
- **Rotation period**: 180 days
- **Procedure**:
  1. Create new bot via @BotFather
  2. Update via admin UI (Settings → Telegram)
  3. Re-register webhook with new token
  4. Revoke old bot via @BotFather
