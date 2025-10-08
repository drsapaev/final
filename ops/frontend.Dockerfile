# =======================
# Frontend image (Vite)
# =======================
FROM node:20.18.0-slim AS base

ENV NODE_ENV=development \
    CI=true

WORKDIR /app

# Install deps (no lockfile in repo — install from package.json)
COPY frontend/package.json /app/package.json
RUN npm install --legacy-peer-deps

# Copy sources (will be overridden by bind mount in docker-compose)
COPY frontend/ /app/

EXPOSE 3000

# HTTP server; listen on 0.0.0.0 inside container
CMD ["npm", "run", "dev"]