# Production Setup Guide

## Step 1: Environment Variables

### 1.1 Copy .env.example to .env

```bash
cd backend
cp .env.example .env
```

### 1.2 Generate SECRET_KEY

```bash
python generate_secret_key.py
```

Copy the generated key to your `.env` file:

```env
SECRET_KEY=your-generated-secret-key-here
```

### 1.3 Configure Required Variables

Edit `.env` and set at minimum:

```env
# CRITICAL
SECRET_KEY=your-secret-key-here
ENV=production

# DATABASE
DATABASE_URL=postgresql://user:password@localhost:5432/clinic

# CORS
BACKEND_CORS_ORIGINS=https://your-domain.com
FRONTEND_URL=https://your-domain.com

# FCM (Optional but recommended)
FCM_ENABLED=true
FCM_SERVER_KEY=your-fcm-server-key
FCM_PROJECT_ID=your-fcm-project-id

# BACKUP (Recommended)
AUTO_BACKUP_ENABLED=true
BACKUP_HOUR=2
BACKUP_MINUTE=0
```

## Step 2: Database Migrations

### 2.1 Run Migrations

```bash
cd backend
alembic upgrade head
```

### 2.2 Verify Migration Status

```bash
alembic current
```

## Step 3: Install Monitoring Dependencies (Optional)

```bash
pip install -r requirements-monitoring.txt
```

Configure Sentry (if using):

```env
SENTRY_DSN=your-sentry-dsn
SENTRY_TRACES_SAMPLE_RATE=0.1
```

## Step 4: Load Testing

### 4.1 Run Load Tests

```bash
# Basic test
python load_test.py

# Custom test
python load_test.py --users 50 --requests 20 --url http://your-api-url

# Test specific endpoint
python load_test.py --endpoint /api/v1/patients/ --users 10 --requests 100
```

### 4.2 Expected Results

- Success rate: > 95%
- Average response time: < 500ms
- P95 response time: < 2000ms
- Error rate: < 5%

## Step 5: Start Production Server

### 5.1 Using Uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5.2 Using Gunicorn (Recommended for production)

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 5.3 Using Docker

```bash
cd ops
docker compose up --build -d
```

## Step 6: Verify Setup

### 6.1 Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### 6.2 Run Production Readiness Tests

```bash
python test_production_readiness.py
```

All tests should pass.

## Step 7: Monitoring Setup

### 7.1 Enable Monitoring

Add to `.env`:

```env
# Sentry (Error Tracking)
SENTRY_DSN=your-sentry-dsn

# Prometheus (Metrics)
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

### 7.2 Access Metrics

- Prometheus: http://localhost:9090/metrics
- Health: http://localhost:8000/api/v1/health

## Step 8: Backup Verification

### 8.1 Test Backup

```bash
# Create manual backup
curl -X POST http://localhost:8000/api/v1/system/backup/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"

# List backups
curl http://localhost:8000/api/v1/system/backup/list \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 8.2 Verify Automated Backups

Check logs for scheduled backup messages:

```bash
tail -f logs/app.log | grep backup
```

## Security Checklist

- [ ] SECRET_KEY is set and secure (not default)
- [ ] ENV=production
- [ ] CORS origins configured correctly
- [ ] Database credentials are secure
- [ ] FCM keys configured (if using push notifications)
- [ ] Payment provider keys configured securely
- [ ] Telegram bot token configured (if using)
- [ ] Backup system enabled and tested
- [ ] Monitoring configured
- [ ] Logs are being collected
- [ ] Rate limiting enabled
- [ ] 2FA is working correctly

## Troubleshooting

### Migration Errors

If migrations fail:

```bash
# Check current migration
alembic current

# Check migration history
alembic history

# Rollback if needed
alembic downgrade -1
```

### Load Test Failures

If load tests show high error rates:

1. Check server logs
2. Verify database connection
3. Check resource usage (CPU, memory)
4. Review error messages in test output

### Monitoring Not Working

1. Verify dependencies installed: `pip list | grep sentry`
2. Check environment variables
3. Review logs for initialization errors

## Next Steps

1. Set up reverse proxy (nginx)
2. Configure SSL/TLS certificates
3. Set up log aggregation
4. Configure alerting rules
5. Schedule regular security audits
6. Set up disaster recovery procedures


