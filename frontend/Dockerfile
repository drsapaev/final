# Production Dockerfile for frontend
FROM node:20.19.6-slim AS builder

ARG VITE_API_BASE=/api/v1
ARG VITE_API_URL=
ARG VITE_API_BASE_URL=
ARG VITE_WS_URL=
ARG VITE_WS_HOST=

ENV CI=true \
    NODE_ENV=production \
    VITE_API_BASE=${VITE_API_BASE} \
    VITE_API_URL=${VITE_API_URL} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_URL=${VITE_WS_URL} \
    VITE_WS_HOST=${VITE_WS_HOST}

WORKDIR /app

COPY package.json /app/package.json
COPY package-lock.json /app/package-lock.json
RUN npm ci --legacy-peer-deps

COPY src /app/src
COPY public /app/public
COPY index.html /app/index.html
COPY vite.config.js /app/vite.config.js

RUN npm run build

# DOCKER-DEPLOY-AUDIT: Security headers in nginx
FROM nginx:1.27-alpine AS runtime

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
