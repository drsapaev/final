# Backup & Restore Procedure

## Daily PostgreSQL Backup
```bash
docker-compose exec db pg_dump -U clinic clinic | gzip > backups/db_$(date +%Y%m%d).sql.gz
find backups/ -name "db_*.sql.gz" -mtime +30 -delete
```

## File Storage Backup
```bash
rsync -avz backend/uploads/ backups/uploads_$(date +%Y%m%d)/
```

## Restore Procedure
```bash
# 1. Stop backend
docker-compose stop backend

# 2. Restore database
gunzip -c backups/db_20260101.sql.gz | docker-compose exec -T db psql -U clinic clinic

# 3. Restore files
docker-compose cp backups/uploads backend:/app/

# 4. Restart
docker-compose start backend
```

## RTO/RPO
- RPO (max data loss): 24 hours (daily backup)
- RTO (max downtime): 2 hours
- For lower RPO: configure PostgreSQL WAL archiving
