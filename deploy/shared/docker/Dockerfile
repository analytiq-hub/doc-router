# Production UI: Vite static SPA (build) + nginx (runtime).
FROM node:24 AS frontend
WORKDIR /app
COPY packages/typescript/sdk/ ./packages/typescript/sdk/
RUN cd packages/typescript/sdk && npm install
COPY packages/typescript/frontend/package*.json ./packages/typescript/frontend/
COPY packages/typescript/frontend/scripts/ ./packages/typescript/frontend/scripts/
RUN cd packages/typescript/frontend && npm install
ARG NODE_ENV=production
ARG PUBLIC_API_URL=/fastapi
ARG APP_NAME="Smart Document Router"
ARG APP_FAVICON=""
ENV NODE_ENV=${NODE_ENV}
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
ENV APP_NAME=${APP_NAME}
ENV APP_FAVICON=${APP_FAVICON}
# Relative /fastapi only — absolute :8000 URLs break httpOnly cookies behind compose/nginx UI.
ENV VITE_FASTAPI_FRONTEND_URL=${PUBLIC_API_URL}
COPY packages/typescript/frontend/ ./packages/typescript/frontend/
COPY branding ./branding
COPY scripts/sync-branding.sh ./scripts/sync-branding.sh
ARG NODE_MAX_OLD_SPACE_MB=4096
ENV NODE_OPTIONS=--max-old-space-size=${NODE_MAX_OLD_SPACE_MB}
RUN chmod +x ./scripts/sync-branding.sh \
    && printf 'APP_NAME=%s\n' "$APP_NAME" > .env \
    && { [ -z "$APP_FAVICON" ] || printf 'APP_FAVICON=%s\n' "$APP_FAVICON" >> .env; } \
    && printf 'VITE_FASTAPI_FRONTEND_URL=/fastapi\n' >> .env \
    && ./scripts/sync-branding.sh \
    && cd packages/typescript/frontend && npm run build

FROM nginx:alpine AS runner
COPY packages/typescript/frontend/nginx-mjs-types.conf /etc/nginx/conf.d/00-mjs-types.conf
COPY packages/typescript/frontend/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /app/packages/typescript/frontend/dist-vite /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# Use slim Python 3.12 as the base image
FROM python:3.12-slim AS backend

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV STRIPE_PRODUCT_TAG=""

# Set the working directory in the container
WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv

# Install Python deps before copying source (better layer caching)
COPY packages/python/requirements.txt ./packages/python/
RUN uv pip install --system --no-cache-dir -r packages/python/requirements.txt

# Copy the packages and repo-root schemas (credential kinds, etc.)
COPY packages/ ./packages/
COPY schemas/ ./schemas/

EXPOSE 8000
