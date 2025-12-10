# Production Security Configuration Guide

## Table of Contents
1. [Environment Variables](#environment-variables)
2. [CORS Configuration](#cors-configuration)
3. [Rate Limiting](#rate-limiting)
4. [Sentry Error Tracking](#sentry-error-tracking)
5. [Health Checks](#health-checks)
6. [Security Checklist](#security-checklist)

---

## Environment Variables

### Required for Production

```bash
# CRITICAL: Generate secure key for JWT tokens
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-32-char-or-longer-secret-key

# Set environment to production
ENV=production

# Database URL (use PostgreSQL in production)
DATABASE_URL=postgresql://user:password@host:5432/clinic_db
```

### CORS Configuration

```bash
# Disable CORS entirely (if behind reverse proxy handling CORS)
CORS_DISABLE=false

# NEVER use in production - allows any origin
CORS_ALLOW_ALL=false

# Production origins (comma-separated list)
PRODUCTION_CORS_ORIGINS=https://clinic.example.com,https://app.clinic.example.com
```

### Rate Limiting

```bash
# Enable/disable rate limiting
RATE_LIMIT_ENABLED=true

# Max login attempts per 5 minutes (default: 5)
RATE_LIMIT_LOGIN=5

# Max API requests per hour (default: 100)
RATE_LIMIT_API=100

# IP lockout duration in seconds (default: 900 = 15 minutes)
RATE_LIMIT_LOCKOUT_DURATION=900
```

### Sentry Error Tracking

```bash
# Sentry DSN - get from sentry.io project settings
SENTRY_DSN=https://key@sentry.io/project-id

# Sample rate for errors (0.0-1.0, default: 1.0 = capture all)
SENTRY_SAMPLE_RATE=1.0

# Sample rate for performance traces (0.0-1.0, default: 0.1 = 10%)
SENTRY_TRACES_SAMPLE_RATE=0.1

# Environment tag (default: uses ENV value)
SENTRY_ENVIRONMENT=production
```

#### Installing Sentry SDK
```bash
pip install sentry-sdk[fastapi]
```

### Structured Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log format: 'console' for development, 'json' for production
LOG_FORMAT=json
```

#### JSON Log Format (Production)

When `LOG_FORMAT=json` or `ENV=production`, logs are output as JSON:

```json
{
    "timestamp": "2024-12-10T12:00:00.000000Z",
    "level": "INFO",
    "logger": "clinic.main",
    "message": "User logged in",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "module": "authentication",
    "function": "login",
    "line": 42,
    "user_id": 123
}
```

#### Request ID Tracing

Every request receives a unique `X-Request-ID` header which:
- Appears in all log messages for that request
- Is returned in response headers
- Can be passed from client (`X-Request-ID` header) for distributed tracing

---

## CORS Configuration

### Development (default)
```python
BACKEND_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
```

### Production
Set `PRODUCTION_CORS_ORIGINS` environment variable:
```bash
export PRODUCTION_CORS_ORIGINS="https://clinic.example.com,https://api.clinic.example.com"
```

### Behind Reverse Proxy (Nginx/Caddy)
If your reverse proxy handles CORS, you can disable it in the application:
```bash
export CORS_DISABLE=true
```

---

## Rate Limiting

The application includes comprehensive rate limiting:

| Endpoint Type | Default Limit | Window | Description |
|--------------|---------------|--------|-------------|
| Login | 5 requests | 5 min | Prevents password brute force |
| 2FA Verify | 10 requests | 5 min | Prevents OTP brute force |
| Password Reset | 3 requests | 1 hour | Limits reset request abuse |
| Password Change | 5 requests | 1 hour | Limits change attempts |
| API (general) | 100 requests | 1 hour | General API rate limit |

### Brute Force Protection
- After exceeding login attempts, IP is locked for 15 minutes (configurable)
- Failed attempts are tracked per IP + endpoint combination
- X-RateLimit-* headers are included in responses

### Redis (Recommended for Production)
For production with multiple instances, configure Redis for rate limit storage:
```bash
# TODO: Add Redis configuration
REDIS_URL=redis://localhost:6379/0
```

---

## Database Connection Pooling

Configure connection pool for optimal production performance.

### Environment Variables

```bash
# Number of persistent connections in pool (default: 5)
DB_POOL_SIZE=10

# Additional connections beyond pool_size (default: 10)
# Total max connections = DB_POOL_SIZE + DB_MAX_OVERFLOW
DB_MAX_OVERFLOW=20

# Seconds to wait for connection from pool (default: 30)
# Raises TimeoutError if exceeded
DB_POOL_TIMEOUT=30

# Seconds before connection is recycled (default: 3600)
# Important for PostgreSQL/MySQL to prevent stale connections
# Set to -1 to disable
DB_POOL_RECYCLE=3600
```

### Recommended Settings by Load

| Load Level | Concurrent Users | `DB_POOL_SIZE` | `DB_MAX_OVERFLOW` | Total Max |
|------------|-----------------|----------------|-------------------|-----------|
| Light | 1-50 | 5 | 10 | 15 |
| Medium | 50-150 | 10 | 20 | 30 |
| Heavy | 150-500 | 20 | 30 | 50 |
| Enterprise | 500+ | 30+ | 50+ | 80+ |

### Monitoring Pool Status

The application logs pool configuration at startup:
```
[app.db.session] Connection pool: size=10, max_overflow=20, timeout=30s, recycle=3600s
```

### PostgreSQL Specific

For PostgreSQL in production:
```bash
# Use longer recycle time
DB_POOL_RECYCLE=7200

# Enable pre-ping to verify connections
# (enabled by default in session.py via pool_pre_ping=True)
```

---

## Sentry Error Tracking

Sentry provides real-time error tracking and performance monitoring.

### Setup

1. Create account at [sentry.io](https://sentry.io)
2. Create new Python project
3. Copy DSN from project settings
4. Install SDK: `pip install sentry-sdk[fastapi]`
5. Set environment variables

### Features Enabled

| Feature | Description |
|---------|-------------|
| FastAPI Integration | Automatic capture of unhandled exceptions |
| SQLAlchemy Integration | Database query tracking |
| Logging Integration | Error-level logs sent to Sentry |
| Performance Tracing | Slow request detection |

### Best Practices

- **Production only**: Don't set SENTRY_DSN in development
- **Sample rates**: Use lower traces sample rate (0.1-0.2) for high-traffic
- **PII protection**: `send_default_pii=False` prevents sensitive data capture
- **Environment tags**: Use SENTRY_ENVIRONMENT to distinguish prod/staging

### Testing Sentry Integration

```python
# Raise a test error (only do this once!)
import sentry_sdk
sentry_sdk.capture_message("Test message from Clinic Manager")
```

---

## Health Checks

Three endpoints are available for monitoring:

### `GET /health` - Health Check
- **Purpose**: Load balancer health checks
- **Returns**: 200 OK if application is running
- **Response**:
```json
{
    "status": "healthy",
    "timestamp": "2024-12-10T12:00:00.000000",
    "version": "0.9.0",
    "env": "production"
}
```

### `GET /ready` - Readiness Check
- **Purpose**: Kubernetes readiness probe
- **Returns**: 200 if ready, 503 if not ready
- **Checks**: Database connectivity, configuration validity
- **Response**:
```json
{
    "status": "ready",
    "timestamp": "2024-12-10T12:00:00.000000",
    "version": "0.9.0",
    "checks": {
        "database": true,
        "config": true
    }
}
```

### `GET /live` - Liveness Check
- **Purpose**: Kubernetes liveness probe
- **Returns**: 200 if process is alive
- **Response**:
```json
{
    "status": "alive",
    "timestamp": "2024-12-10T12:00:00.000000"
}
```

### Kubernetes Configuration Example
```yaml
livenessProbe:
  httpGet:
    path: /live
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## Security Checklist

### Before Deployment

- [ ] Set `SECRET_KEY` environment variable (min 32 chars)
- [ ] Set `ENV=production`
- [ ] Configure `PRODUCTION_CORS_ORIGINS` with actual domains
- [ ] Ensure `CORS_ALLOW_ALL=false`
- [ ] Enable rate limiting (`RATE_LIMIT_ENABLED=true`)
- [ ] Use PostgreSQL instead of SQLite
- [ ] Configure HTTPS (via reverse proxy)
- [ ] Set up monitoring for `/health`, `/ready`, `/live`
- [ ] Configure Sentry error tracking (`SENTRY_DSN`)

### Infrastructure

- [ ] Deploy behind reverse proxy (Nginx/Caddy/Traefik)
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Configure log aggregation
- [ ] Set up backup automation

### Monitoring

- [ ] Configure health check endpoints in load balancer
- [ ] Set up alerting for 5xx errors (Sentry)
- [ ] Monitor rate limit metrics
- [ ] Track failed login attempts
- [ ] Set up Sentry performance monitoring
- [ ] Track failed login attempts

---

## Example Production .env

```bash
# Core
SECRET_KEY=6HK2DZj8qL4xPRvYnM9aS7cWfT3gJbE0uNhXiYlOpQw
ENV=production

# Database
DATABASE_URL=postgresql://clinic:strongpassword@db.example.com:5432/clinic_prod

# Database Connection Pool
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# CORS
CORS_DISABLE=false
CORS_ALLOW_ALL=false
PRODUCTION_CORS_ORIGINS=https://clinic.example.com,https://app.clinic.example.com

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN=5
RATE_LIMIT_API=200
RATE_LIMIT_LOCKOUT_DURATION=900

# Sentry Error Tracking
SENTRY_DSN=https://abc123@sentry.io/12345
SENTRY_SAMPLE_RATE=1.0
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Frontend URL (for QR codes)
FRONTEND_URL=https://clinic.example.com
```
