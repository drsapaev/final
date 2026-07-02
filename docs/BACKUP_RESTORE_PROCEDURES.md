# Backup and Restore Procedures

> **Version**: 1.0  
> **Last Updated**: December 2024  
> **Critical Level**: HIGH - Follow procedures exactly

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Database Backups](#database-backups)
4. [File System Backups](#file-system-backups)
5. [Automated Backup Scripts](#automated-backup-scripts)
6. [Restore Procedures](#restore-procedures)
7. [Disaster Recovery](#disaster-recovery)
8. [Backup Verification](#backup-verification)
9. [Retention Policy](#retention-policy)
10. [Monitoring & Alerts](#monitoring--alerts)

---

## Overview

### What Gets Backed Up

| Component | Backup Type | Frequency | Retention |
|-----------|-------------|-----------|-----------|
| PostgreSQL Database | Full + Incremental | Daily | 30 days |
| User Uploads | File sync | Hourly | 90 days |
| Application Config | Version control | On change | Permanent |
| SSL Certificates | File copy | Weekly | 4 weeks |
| Logs | Archive | Daily | 14 days |

### Backup Locations

| Type | Primary Location | Secondary Location |
|------|------------------|-------------------|
| Database | `/var/backups/clinic/db/` | S3/Cloud Storage |
| Files | `/var/backups/clinic/files/` | S3/Cloud Storage |
| Config | Git repository | Local copy |

---

## Backup Strategy

### 3-2-1 Backup Rule

We follow the industry-standard 3-2-1 backup strategy:

- **3 copies** of data (1 production + 2 backups)
- **2 different storage types** (local disk + cloud)
- **1 offsite location** (cloud storage in different region)

### Backup Schedule

```
Daily (01:00 UTC):
├── Full database backup
├── Incremental file backup
└── Log rotation & archive

Weekly (Sunday 02:00 UTC):
├── Full file system backup
├── SSL certificate backup
└── Configuration snapshot

Monthly (1st day 03:00 UTC):
├── Verification of all backups
├── Restore test to staging
└── Cleanup old backups
```

---

## Database Backups

### Manual Database Backup

```bash
#!/bin/bash
# Quick database backup

BACKUP_DIR="/var/backups/clinic/db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="clinic_db"
DB_USER="clinic_user"

# Create backup
pg_dump -U $DB_USER -h localhost -Fc $DB_NAME > \
    "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.dump"

# Verify backup
pg_restore --list "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.dump" > /dev/null

echo "Backup created: ${DB_NAME}_${TIMESTAMP}.dump"
```

### Backup Types

#### 1. Full Backup (pg_dump)

```bash
# Full custom format (recommended)
pg_dump -U clinic_user -h localhost -Fc clinic_db > backup.dump

# Full SQL format (readable)
pg_dump -U clinic_user -h localhost -Fp clinic_db > backup.sql

# Full directory format (parallel restore)
pg_dump -U clinic_user -h localhost -Fd -j 4 clinic_db -f backup_dir/
```

#### 2. Schema Only Backup

```bash
pg_dump -U clinic_user -h localhost --schema-only clinic_db > schema.sql
```

#### 3. Data Only Backup

```bash
pg_dump -U clinic_user -h localhost --data-only clinic_db > data.sql
```

#### 4. Specific Tables Backup

```bash
# Backup specific tables
pg_dump -U clinic_user -h localhost -t patients -t appointments clinic_db > tables.dump
```

### Point-in-Time Recovery (PITR)

For production environments, configure continuous archiving:

**postgresql.conf:**
```conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/backups/clinic/wal/%f'
```

**Create base backup:**
```bash
pg_basebackup -U replication_user -h localhost \
    -D /var/backups/clinic/basebackup \
    -Ft -z -Xs -P
```

---

## File System Backups

### User Uploads Backup

```bash
#!/bin/bash
# Backup user uploads

SOURCE_DIR="/var/www/clinic/uploads"
BACKUP_DIR="/var/backups/clinic/files"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create incremental backup using rsync
rsync -avz --delete \
    --backup --backup-dir="$BACKUP_DIR/incremental/$TIMESTAMP" \
    "$SOURCE_DIR/" "$BACKUP_DIR/current/"

# Create compressed archive
tar -czf "$BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz" \
    -C "$SOURCE_DIR" .

echo "Files backup completed: uploads_${TIMESTAMP}.tar.gz"
```

### Application Configuration Backup

```bash
#!/bin/bash
# Backup configuration files

BACKUP_DIR="/var/backups/clinic/config"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR/$TIMESTAMP"

# Backup .env (encrypted)
gpg --symmetric --cipher-algo AES256 \
    -o "$BACKUP_DIR/$TIMESTAMP/env.gpg" \
    /home/clinic/clinic/.env

# Backup nginx config
cp -r /etc/nginx/sites-available/clinic "$BACKUP_DIR/$TIMESTAMP/"

# Backup systemd services
cp /etc/systemd/system/clinic-*.service "$BACKUP_DIR/$TIMESTAMP/"

# Backup SSL certificates
cp -r /etc/letsencrypt/live/clinic.example.com "$BACKUP_DIR/$TIMESTAMP/ssl/"

tar -czf "$BACKUP_DIR/config_${TIMESTAMP}.tar.gz" \
    -C "$BACKUP_DIR" "$TIMESTAMP"
rm -rf "$BACKUP_DIR/$TIMESTAMP"

echo "Config backup completed"
```

---

## Automated Backup Scripts

### Complete Backup Script

Create `/home/clinic/scripts/backup.sh`:

```bash
#!/bin/bash
#
# Clinic Management System - Automated Backup Script
# Run via cron: 0 1 * * * /home/clinic/scripts/backup.sh
#

set -euo pipefail

# Configuration
BACKUP_ROOT="/var/backups/clinic"
LOG_FILE="/var/log/clinic/backup.log"
RETENTION_DAYS=30
S3_BUCKET="s3://clinic-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y-%m-%d)

# Database settings
DB_NAME="clinic_db"
DB_USER="clinic_user"
DB_HOST="localhost"

# Notification settings
ALERT_EMAIL="admin@example.com"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    echo "Backup failed: $1" | mail -s "ALERT: Clinic Backup Failed" "$ALERT_EMAIL"
    exit 1
}

# Create directories
mkdir -p "$BACKUP_ROOT"/{db,files,config,logs}

log "===== Starting backup ====="

# ==================
# 1. Database Backup
# ==================
log "Starting database backup..."

DB_BACKUP_FILE="$BACKUP_ROOT/db/${DB_NAME}_${TIMESTAMP}.dump"

pg_dump -U "$DB_USER" -h "$DB_HOST" -Fc "$DB_NAME" > "$DB_BACKUP_FILE" \
    || error_exit "Database backup failed"

# Verify backup
pg_restore --list "$DB_BACKUP_FILE" > /dev/null 2>&1 \
    || error_exit "Database backup verification failed"

# Compress if larger than 100MB
if [ $(stat -c%s "$DB_BACKUP_FILE") -gt 104857600 ]; then
    gzip "$DB_BACKUP_FILE"
    DB_BACKUP_FILE="${DB_BACKUP_FILE}.gz"
fi

DB_SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
log "Database backup completed: $DB_SIZE"

# ==================
# 2. Files Backup
# ==================
log "Starting files backup..."

FILES_BACKUP_FILE="$BACKUP_ROOT/files/uploads_${TIMESTAMP}.tar.gz"

tar -czf "$FILES_BACKUP_FILE" \
    -C /var/www/clinic uploads \
    || error_exit "Files backup failed"

FILES_SIZE=$(du -h "$FILES_BACKUP_FILE" | cut -f1)
log "Files backup completed: $FILES_SIZE"

# ==================
# 3. Config Backup
# ==================
log "Starting config backup..."

CONFIG_DIR="$BACKUP_ROOT/config/config_${TIMESTAMP}"
mkdir -p "$CONFIG_DIR"

# Backup .env (encrypted)
if command -v gpg &> /dev/null; then
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file /root/.backup-passphrase \
        -o "$CONFIG_DIR/env.gpg" \
        /home/clinic/clinic/.env 2>/dev/null || true
fi

# Backup other configs
cp /etc/nginx/sites-available/clinic "$CONFIG_DIR/" 2>/dev/null || true
cp /etc/systemd/system/clinic-*.service "$CONFIG_DIR/" 2>/dev/null || true

tar -czf "$BACKUP_ROOT/config/config_${TIMESTAMP}.tar.gz" \
    -C "$BACKUP_ROOT/config" "config_${TIMESTAMP}"
rm -rf "$CONFIG_DIR"

log "Config backup completed"

# ==================
# 4. Upload to S3
# ==================
if command -v aws &> /dev/null; then
    log "Uploading to S3..."
    
    aws s3 cp "$DB_BACKUP_FILE" "$S3_BUCKET/db/$DATE/" --quiet \
        || log "WARNING: S3 upload failed for database"
    
    aws s3 cp "$FILES_BACKUP_FILE" "$S3_BUCKET/files/$DATE/" --quiet \
        || log "WARNING: S3 upload failed for files"
    
    log "S3 upload completed"
else
    log "WARNING: AWS CLI not found, skipping S3 upload"
fi

# ==================
# 5. Cleanup Old Backups
# ==================
log "Cleaning up old backups..."

find "$BACKUP_ROOT/db" -name "*.dump*" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_ROOT/files" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_ROOT/config" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

log "Cleanup completed"

# ==================
# 6. Summary
# ==================
TOTAL_SIZE=$(du -sh "$BACKUP_ROOT" | cut -f1)
log "===== Backup completed ====="
log "Total backup size: $TOTAL_SIZE"
log "Database: $DB_SIZE"
log "Files: $FILES_SIZE"

# Send success notification (optional)
# echo "Backup completed successfully. Total size: $TOTAL_SIZE" | \
#     mail -s "Clinic Backup Success - $DATE" "$ALERT_EMAIL"

exit 0
```

### Setup Cron Jobs

```bash
# Edit crontab
sudo crontab -e

# Add backup jobs
# Daily database + files backup at 1:00 AM
0 1 * * * /home/clinic/scripts/backup.sh >> /var/log/clinic/backup.log 2>&1

# Weekly full verification on Sunday at 3:00 AM
0 3 * * 0 /home/clinic/scripts/verify-backups.sh >> /var/log/clinic/backup.log 2>&1

# Monthly restore test on 1st at 4:00 AM
0 4 1 * * /home/clinic/scripts/test-restore.sh >> /var/log/clinic/backup.log 2>&1
```

---

## Restore Procedures

### ⚠️ IMPORTANT: Pre-Restore Checklist

Before any restore operation:

1. [ ] Confirm the issue cannot be fixed without restore
2. [ ] Notify all users of planned downtime
3. [ ] Take a fresh backup of current state
4. [ ] Verify backup integrity
5. [ ] Have rollback plan ready

### Database Restore

#### Full Restore (Replace entire database)

```bash
#!/bin/bash
# restore-database.sh - Full database restore

BACKUP_FILE=$1
DB_NAME="clinic_db"
DB_USER="clinic_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.dump>"
    exit 1
fi

echo "WARNING: This will replace the entire database!"
read -p "Are you sure? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Stop application
sudo systemctl stop clinic-backend

# Create safety backup
pg_dump -U $DB_USER -h localhost -Fc $DB_NAME > \
    "/var/backups/clinic/db/pre_restore_$(date +%Y%m%d_%H%M%S).dump"

# Drop and recreate database
sudo -u postgres psql << EOF
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOF

# Restore
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | pg_restore -U $DB_USER -h localhost -d $DB_NAME
else
    pg_restore -U $DB_USER -h localhost -d $DB_NAME "$BACKUP_FILE"
fi

# Verify
psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM patients;"

# Restart application
sudo systemctl start clinic-backend

echo "Restore completed!"
```

#### Partial Restore (Specific tables)

```bash
#!/bin/bash
# Restore specific tables

BACKUP_FILE=$1
TABLE_NAME=$2
DB_NAME="clinic_db"
DB_USER="clinic_user"

# List available tables in backup
pg_restore --list "$BACKUP_FILE" | grep "TABLE DATA"

# Restore single table (append data)
pg_restore -U $DB_USER -d $DB_NAME \
    --data-only \
    -t "$TABLE_NAME" \
    "$BACKUP_FILE"

# Or restore with schema
pg_restore -U $DB_USER -d $DB_NAME \
    --clean \
    -t "$TABLE_NAME" \
    "$BACKUP_FILE"
```

### File System Restore

```bash
#!/bin/bash
# restore-files.sh

BACKUP_FILE=$1
RESTORE_PATH="/var/www/clinic/uploads"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

echo "Restoring files from $BACKUP_FILE..."

# Backup current files
mv "$RESTORE_PATH" "${RESTORE_PATH}_backup_$(date +%Y%m%d_%H%M%S)"

# Create directory
mkdir -p "$RESTORE_PATH"

# Extract backup
tar -xzf "$BACKUP_FILE" -C /var/www/clinic

# Fix permissions
chown -R www-data:www-data "$RESTORE_PATH"
chmod -R 755 "$RESTORE_PATH"

echo "Files restored successfully"
```

### Configuration Restore

```bash
#!/bin/bash
# restore-config.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <config_backup.tar.gz>"
    exit 1
fi

# Extract
TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Decrypt .env
gpg --decrypt --passphrase-file /root/.backup-passphrase \
    -o /home/clinic/clinic/.env \
    "$TEMP_DIR"/*/.env.gpg

# Restore nginx config
cp "$TEMP_DIR"/*/clinic /etc/nginx/sites-available/
nginx -t && systemctl reload nginx

# Restore services
cp "$TEMP_DIR"/*/clinic-*.service /etc/systemd/system/
systemctl daemon-reload

rm -rf "$TEMP_DIR"
echo "Configuration restored"
```

---

## Disaster Recovery

### Recovery Time Objectives (RTO/RPO)

| Scenario | RTO | RPO |
|----------|-----|-----|
| Database corruption | 1 hour | 24 hours |
| Server failure | 2 hours | 24 hours |
| Datacenter outage | 4 hours | 24 hours |
| Complete loss | 8 hours | 24 hours |

### Disaster Recovery Plan

#### Scenario 1: Database Corruption

```bash
# 1. Stop application immediately
sudo systemctl stop clinic-backend

# 2. Identify last known good backup
ls -la /var/backups/clinic/db/

# 3. Restore from backup
./restore-database.sh /var/backups/clinic/db/clinic_db_YYYYMMDD.dump

# 4. Verify data integrity
psql -U clinic_user -d clinic_db -c "
    SELECT 'patients' as tbl, COUNT(*) FROM patients
    UNION ALL
    SELECT 'appointments', COUNT(*) FROM appointments
    UNION ALL
    SELECT 'medical_records', COUNT(*) FROM medical_records;
"

# 5. Restart application
sudo systemctl start clinic-backend
```

#### Scenario 2: Complete Server Failure

```bash
# On new server:

# 1. Setup base system (see DEPLOYMENT_GUIDE.md)
# 2. Install application
# 3. Restore database
./restore-database.sh s3://clinic-backups/db/latest/clinic_db.dump

# 4. Restore files
./restore-files.sh s3://clinic-backups/files/latest/uploads.tar.gz

# 5. Restore configuration
./restore-config.sh s3://clinic-backups/config/latest/config.tar.gz

# 6. Update DNS to point to new server
# 7. Verify all services
```

#### Scenario 3: Ransomware/Security Breach

```bash
# 1. IMMEDIATELY isolate affected systems
# 2. Contact security team
# 3. Do NOT pay ransom
# 4. Assess scope of damage
# 5. Spin up clean infrastructure
# 6. Restore from verified clean backup
# 7. Change all credentials
# 8. Conduct security audit
```

---

## Backup Verification

### Automated Verification Script

Create `/home/clinic/scripts/verify-backups.sh`:

```bash
#!/bin/bash
#
# Verify backup integrity
#

BACKUP_DIR="/var/backups/clinic"
LOG_FILE="/var/log/clinic/backup-verify.log"
ALERT_EMAIL="admin@example.com"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

ERRORS=0

log "Starting backup verification..."

# 1. Check latest database backup exists and is valid
LATEST_DB=$(ls -t "$BACKUP_DIR/db/"*.dump* 2>/dev/null | head -1)
if [ -z "$LATEST_DB" ]; then
    log "ERROR: No database backup found!"
    ERRORS=$((ERRORS + 1))
else
    # Verify backup can be read
    if [[ "$LATEST_DB" == *.gz ]]; then
        if ! gunzip -t "$LATEST_DB" 2>/dev/null; then
            log "ERROR: Database backup is corrupted!"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if ! pg_restore --list "$LATEST_DB" > /dev/null 2>&1; then
            log "ERROR: Database backup is invalid!"
            ERRORS=$((ERRORS + 1))
        fi
    fi
    
    # Check age
    AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$LATEST_DB")) / 3600 ))
    if [ $AGE_HOURS -gt 25 ]; then
        log "WARNING: Latest database backup is $AGE_HOURS hours old!"
        ERRORS=$((ERRORS + 1))
    else
        log "OK: Database backup verified ($AGE_HOURS hours old)"
    fi
fi

# 2. Check files backup
LATEST_FILES=$(ls -t "$BACKUP_DIR/files/"*.tar.gz 2>/dev/null | head -1)
if [ -z "$LATEST_FILES" ]; then
    log "ERROR: No files backup found!"
    ERRORS=$((ERRORS + 1))
else
    if ! tar -tzf "$LATEST_FILES" > /dev/null 2>&1; then
        log "ERROR: Files backup is corrupted!"
        ERRORS=$((ERRORS + 1))
    else
        log "OK: Files backup verified"
    fi
fi

# 3. Check S3 backups (if configured)
if command -v aws &> /dev/null; then
    S3_COUNT=$(aws s3 ls s3://clinic-backups/db/ --recursive | wc -l)
    if [ $S3_COUNT -eq 0 ]; then
        log "WARNING: No backups found in S3!"
        ERRORS=$((ERRORS + 1))
    else
        log "OK: $S3_COUNT backups found in S3"
    fi
fi

# Report
if [ $ERRORS -gt 0 ]; then
    log "VERIFICATION FAILED: $ERRORS errors found"
    echo "Backup verification failed with $ERRORS errors. Check $LOG_FILE for details." | \
        mail -s "ALERT: Backup Verification Failed" "$ALERT_EMAIL"
    exit 1
else
    log "VERIFICATION PASSED: All backups OK"
fi
```

### Monthly Restore Test

Create `/home/clinic/scripts/test-restore.sh`:

```bash
#!/bin/bash
#
# Monthly restore test to staging environment
#

STAGING_DB="clinic_db_staging"
BACKUP_FILE=$(ls -t /var/backups/clinic/db/*.dump* | head -1)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting monthly restore test..."

# Create staging database
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS $STAGING_DB;
CREATE DATABASE $STAGING_DB OWNER clinic_user;
EOF

# Restore
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | pg_restore -U clinic_user -d $STAGING_DB
else
    pg_restore -U clinic_user -d $STAGING_DB "$BACKUP_FILE"
fi

# Verify record counts
psql -U clinic_user -d $STAGING_DB -c "
    SELECT 'patients' as tbl, COUNT(*) FROM patients;
    SELECT 'appointments' as tbl, COUNT(*) FROM appointments;
"

# Cleanup
sudo -u postgres psql -c "DROP DATABASE $STAGING_DB;"

log "Restore test completed successfully"
```

---

## Retention Policy

### Retention Schedule

| Backup Type | Daily | Weekly | Monthly | Yearly |
|-------------|-------|--------|---------|--------|
| Database | 7 days | 4 weeks | 12 months | 7 years |
| Files | 7 days | 4 weeks | 12 months | - |
| Logs | 14 days | - | - | - |
| Config | 30 days | - | - | - |

### Cleanup Script

```bash
#!/bin/bash
# cleanup-backups.sh

BACKUP_DIR="/var/backups/clinic"

# Keep daily backups for 7 days
find "$BACKUP_DIR/db" -name "*.dump*" -mtime +7 -exec rm {} \;

# Keep weekly backups (Sunday) for 4 weeks
# ... (implementation depends on naming convention)

# Keep monthly backups for 12 months
find "$BACKUP_DIR/monthly" -mtime +365 -exec rm {} \;

# Archive to cold storage after 30 days
aws s3 cp "$BACKUP_DIR/db/" "s3://clinic-backups-archive/db/" \
    --recursive --storage-class GLACIER \
    --exclude "*" --include "*.dump.gz" \
    --older-than 30d
```

---

## Monitoring & Alerts

### Backup Monitoring Checklist

Daily checks (automated):
- [ ] Backup job completed successfully
- [ ] Backup file size is reasonable
- [ ] Backup age < 25 hours
- [ ] S3 upload succeeded

Weekly checks (manual):
- [ ] Review backup logs
- [ ] Verify backup count matches retention policy
- [ ] Check storage usage
- [ ] Test random backup restoration

### Alert Configuration

Add to monitoring system (e.g., Prometheus + Alertmanager):

```yaml
groups:
  - name: backups
    rules:
      - alert: BackupMissing
        expr: time() - backup_last_success_timestamp > 90000  # 25 hours
        labels:
          severity: critical
        annotations:
          summary: "Database backup is overdue"
          
      - alert: BackupFailed
        expr: backup_last_status != 0
        labels:
          severity: critical
        annotations:
          summary: "Last backup job failed"
```

---

## Quick Reference

### Emergency Contacts

| Role | Contact |
|------|---------|
| DBA | dba@example.com |
| DevOps | devops@example.com |
| Security | security@example.com |

### Key Commands

```bash
# Create database backup
pg_dump -U clinic_user -Fc clinic_db > backup.dump

# Restore database
pg_restore -U clinic_user -d clinic_db backup.dump

# Check backup status
tail -f /var/log/clinic/backup.log

# List recent backups
ls -lah /var/backups/clinic/db/
```

---

**⚠️ REMEMBER: Untested backups are not backups. Test regularly!**
