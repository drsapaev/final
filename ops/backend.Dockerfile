# =======================
# Backend image (Python)
# =======================
FROM python:3.11.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for reportlab / pillow (fonts, jpeg, zlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libfreetype6 libjpeg62-turbo zlib1g ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies from requirements.txt
RUN pip install --upgrade pip
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Copy backend sources
COPY backend/ /app/

# Entrypoint script
COPY ops/backend.entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app

EXPOSE 8000

FROM base AS runtime
CMD ["/bin/bash", "/entrypoint.sh"]