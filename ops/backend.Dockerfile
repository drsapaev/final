# =======================
# Backend image (Python)
# =======================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for reportlab / pillow (fonts, jpeg, zlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libfreetype6 libjpeg62-turbo zlib1g ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# If your project uses pyproject.toml with dependencies, prefer installing it.
# We keep a safe baseline of libs to run the app.
RUN pip install --upgrade pip
RUN pip install \
      fastapi==0.115.0 \
      "uvicorn[standard]==0.30.6" \
      SQLAlchemy==2.0.36 \
      alembic==1.13.2 \
      python-jose[cryptography]==3.3.0 \
      passlib[bcrypt]==1.7.4 \
      reportlab==4.2.2 \
      qrcode==7.4.2 \
      pydantic==2.9.2

# Copy backend sources
COPY . /app/

# Entrypoint script
COPY ops/backend.entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app

EXPOSE 8000

FROM base AS runtime
CMD ["/bin/bash", "/entrypoint.sh"]