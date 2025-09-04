# =======================
# Frontend image (Vite)
# =======================
FROM node:20-slim AS base

ENV NODE_ENV=development \
    CI=true

WORKDIR /app

# Install deps (no lockfile in repo — install from package.json)
COPY frontend/package.json /app/package.json
RUN npm install --force --legacy-peer-deps && \
    npm install rollup@^3.29.4 --force --save-dev

# Copy sources (will be overridden by bind mount in docker-compose)
COPY frontend/ /app/

EXPOSE 5173

# Vite dev server; --host to listen on 0.0.0.0 inside container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--strictPort"]