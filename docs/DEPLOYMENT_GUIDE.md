# Clinic Management System - Deployment Guide

> **Version**: 1.0  
> **Last Updated**: December 2024  
> **Environment**: Production

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Quick Start](#quick-start)
4. [Detailed Deployment Steps](#detailed-deployment-steps)
5. [Environment Configuration](#environment-configuration)
6. [Database Setup](#database-setup)
7. [Backend Deployment](#backend-deployment)
8. [Frontend Deployment](#frontend-deployment)
9. [Nginx Configuration](#nginx-configuration)
10. [SSL/TLS Setup](#ssltls-setup)
11. [Docker Deployment](#docker-deployment)
12. [Health Checks](#health-checks)
13. [Rollback Procedures](#rollback-procedures)
14. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Minimum Version | Recommended |
|----------|-----------------|-------------|
| Python | 3.10+ | 3.11 |
| Node.js | 18+ | 20 LTS |
| PostgreSQL | 14+ | 15 |
| Nginx | 1.18+ | 1.24 |
| Git | 2.30+ | Latest |

### Required Access

- [ ] Server SSH access (sudo privileges)
- [ ] Domain DNS management
- [ ] SSL certificate (or Let's Encrypt)
- [ ] Database credentials
- [ ] SMTP server credentials (for email)
- [ ] Sentry DSN (for error tracking)

---

## System Requirements

### Minimum Production Server Specs

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 50 GB SSD | 100 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Estimated Resource Usage

- **Backend**: ~200-500 MB RAM per worker
- **Frontend Build**: ~512 MB RAM during build
- **PostgreSQL**: ~256 MB base + data
- **Nginx**: ~50 MB RAM

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/your-org/clinic-system.git
cd clinic-system

# 2. Setup environment
cp .env.example .env
# Edit .env with your production values

# 3. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head

# 4. Frontend build
cd ../frontend
npm install
npm run build

# 5. Start services
# Start backend with gunicorn/uvicorn
# Serve frontend with nginx
```

---

## Detailed Deployment Steps

### Step 1: Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    nodejs npm \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    git curl wget

# Create application user
sudo useradd -m -s /bin/bash clinic
sudo usermod -aG sudo clinic
```

### Step 2: Clone Repository

```bash
# Switch to application user
sudo su - clinic

# Clone repository
git clone https://github.com/your-org/clinic-system.git ~/clinic
cd ~/clinic
```

### Step 3: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with production values
nano .env
```

---

## Environment Configuration

### Backend Environment Variables (.env)

```env
# ===================
# Core Settings
# ===================
ENV=production
DEBUG=false
SECRET_KEY=your-256-bit-secret-key-here
CORS_ORIGINS=["https://clinic.example.com"]

# ===================
# Database
# ===================
DATABASE_URL=postgresql://clinic_user:strong_password@localhost:5432/clinic_db
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# ===================
# Security
# ===================
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_MIN_LENGTH=12

# ===================
# Sentry Error Tracking
# ===================
SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_ENVIRONMENT=production
SENTRY_SAMPLE_RATE=1.0
SENTRY_TRACES_SAMPLE_RATE=0.1

# ===================
# Logging
# ===================
LOG_LEVEL=INFO
LOG_FORMAT=json

# ===================
# Email (SMTP)
# ===================
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=Clinic System <noreply@example.com>

# ===================
# File Storage
# ===================
UPLOAD_DIR=/var/www/clinic/uploads
MAX_UPLOAD_SIZE_MB=10

# ===================
# Frontend URL
# ===================
FRONTEND_URL=https://clinic.example.com
BACKEND_URL=https://api.clinic.example.com
```

### Frontend Environment Variables

Create `frontend/.env.production`:

```env
VITE_API_URL=https://api.clinic.example.com
VITE_WS_URL=wss://api.clinic.example.com/ws
VITE_ENVIRONMENT=production
```

---

## Database Setup

### Step 1: Install and Configure PostgreSQL

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE USER clinic_user WITH PASSWORD 'strong_password_here';
CREATE DATABASE clinic_db OWNER clinic_user;
GRANT ALL PRIVILEGES ON DATABASE clinic_db TO clinic_user;
\c clinic_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF
```

### Step 2: Configure PostgreSQL for Production

Edit `/etc/postgresql/15/main/postgresql.conf`:

```conf
# Connection Settings
listen_addresses = 'localhost'
max_connections = 100

# Memory Settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB

# WAL Settings
wal_level = replica
max_wal_size = 1GB
min_wal_size = 80MB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_min_duration_statement = 500
```

### Step 3: Run Migrations

```bash
cd ~/clinic/backend
source venv/bin/activate
alembic upgrade head
```

---

## Backend Deployment

### Step 1: Setup Python Environment

```bash
cd ~/clinic/backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install production dependencies
pip install gunicorn uvicorn[standard]
```

### Step 2: Create Systemd Service

Create `/etc/systemd/system/clinic-backend.service`:

```ini
[Unit]
Description=Clinic Backend API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=clinic
Group=clinic
WorkingDirectory=/home/clinic/clinic/backend
Environment="PATH=/home/clinic/clinic/backend/venv/bin"
EnvironmentFile=/home/clinic/clinic/.env
ExecStart=/home/clinic/clinic/backend/venv/bin/gunicorn \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/clinic/access.log \
    --error-logfile /var/log/clinic/error.log \
    --capture-output \
    --timeout 120 \
    app.main:app

Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitInterval=60

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/log/clinic /home/clinic/clinic/backend/uploads

[Install]
WantedBy=multi-user.target
```

### Step 3: Start Backend Service

```bash
# Create log directory
sudo mkdir -p /var/log/clinic
sudo chown clinic:clinic /var/log/clinic

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable clinic-backend
sudo systemctl start clinic-backend

# Check status
sudo systemctl status clinic-backend
```

---

## Frontend Deployment

### Step 1: Build Frontend

```bash
cd ~/clinic/frontend

# Install dependencies
npm ci --production=false

# Build for production
npm run build

# Output is in dist/ directory
```

### Step 2: Serve Static Files

```bash
# Create web directory
sudo mkdir -p /var/www/clinic
sudo cp -r dist/* /var/www/clinic/
sudo chown -R www-data:www-data /var/www/clinic
```

---

## Nginx Configuration

### Main Configuration

Create `/etc/nginx/sites-available/clinic`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name clinic.example.com api.clinic.example.com;
    return 301 https://$server_name$request_uri;
}

# Frontend
server {
    listen 443 ssl http2;
    server_name clinic.example.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/clinic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clinic.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' wss: https:;" always;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Root
    root /var/www/clinic;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Don't cache HTML
    location ~* \.html$ {
        expires -1;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}

# Backend API
server {
    listen 443 ssl http2;
    server_name api.clinic.example.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/clinic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clinic.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Client max body size (for file uploads)
    client_max_body_size 10M;

    # Proxy to backend
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        proxy_read_timeout 120s;
        proxy_connect_timeout 60s;
    }

    # WebSocket endpoint
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;  # WebSocket timeout
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }
}
```

### Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/clinic /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL/TLS Setup

### Option 1: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d clinic.example.com -d api.clinic.example.com

# Test renewal
sudo certbot renew --dry-run
```

### Option 2: Manual Certificate

```bash
# Create directory
sudo mkdir -p /etc/ssl/clinic

# Copy certificates
sudo cp your-cert.crt /etc/ssl/clinic/fullchain.pem
sudo cp your-key.key /etc/ssl/clinic/privkey.pem
sudo chmod 600 /etc/ssl/clinic/privkey.pem
```

---

## Docker Deployment

### Docker Compose (Alternative)

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://clinic:password@db:5432/clinic
    env_file:
      - .env
    depends_on:
      - db
    restart: always
    networks:
      - clinic-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    restart: always
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/letsencrypt:ro
    networks:
      - clinic-net

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: clinic
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: clinic
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    networks:
      - clinic-net

volumes:
  postgres_data:

networks:
  clinic-net:
    driver: bridge
```

### Deploy with Docker

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop
docker-compose -f docker-compose.prod.yml down
```

---

## Health Checks

### Backend Health Endpoint

```bash
# Check health
curl https://api.clinic.example.com/health

# Expected response
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

### Automated Monitoring Script

Create `/home/clinic/scripts/health-check.sh`:

```bash
#!/bin/bash

HEALTH_URL="https://api.clinic.example.com/health"
ALERT_EMAIL="admin@example.com"

response=$(curl -s -w "%{http_code}" -o /tmp/health.json $HEALTH_URL)

if [ "$response" != "200" ]; then
    echo "Health check failed with status $response" | \
        mail -s "ALERT: Clinic System Down" $ALERT_EMAIL
fi
```

Add to crontab:
```bash
*/5 * * * * /home/clinic/scripts/health-check.sh
```

---

## Rollback Procedures

### Quick Rollback

```bash
# 1. Stop current service
sudo systemctl stop clinic-backend

# 2. Switch to previous version
cd ~/clinic
git checkout <previous-tag>

# 3. Reinstall dependencies if needed
source ~/clinic/backend/venv/bin/activate
pip install -r requirements.txt

# 4. Rollback database if needed
alembic downgrade -1

# 5. Restart service
sudo systemctl start clinic-backend
```

### Full Rollback Checklist

1. [ ] Stop backend service
2. [ ] Backup current database state
3. [ ] Checkout previous stable version
4. [ ] Run database rollback (if needed)
5. [ ] Rebuild frontend (if needed)
6. [ ] Restart backend service
7. [ ] Verify health checks pass
8. [ ] Monitor logs for errors

---

## Troubleshooting

### Common Issues

#### Backend won't start

```bash
# Check logs
sudo journalctl -u clinic-backend -n 100

# Common fixes:
# - Check .env file permissions and syntax
# - Verify database connection
# - Check port availability
sudo lsof -i :8000
```

#### Database connection errors

```bash
# Test connection
psql -h localhost -U clinic_user -d clinic_db

# Check PostgreSQL status
sudo systemctl status postgresql

# View PostgreSQL logs
tail -f /var/log/postgresql/postgresql-15-main.log
```

#### Nginx errors

```bash
# Test configuration
sudo nginx -t

# Check logs
tail -f /var/log/nginx/error.log
```

#### SSL certificate issues

```bash
# Check certificate expiry
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### Log Locations

| Component | Log Location |
|-----------|--------------|
| Backend | `/var/log/clinic/` |
| Nginx | `/var/log/nginx/` |
| PostgreSQL | `/var/log/postgresql/` |
| System | `journalctl -u clinic-backend` |

### Performance Issues

```bash
# Check server resources
htop
free -h
df -h

# Check backend workers
ps aux | grep gunicorn

# Check database connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Post-Deployment Checklist

- [ ] All services are running
- [ ] Health checks pass
- [ ] SSL certificate is valid
- [ ] Logs are being collected
- [ ] Sentry is receiving events
- [ ] Database backups are scheduled
- [ ] Monitoring alerts are configured
- [ ] Load testing completed
- [ ] Security scan completed
- [ ] Documentation is updated

---

**Need help?** Contact: devops@example.com
