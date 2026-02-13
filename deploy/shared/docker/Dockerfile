FROM node:24 AS frontend

WORKDIR /app

# Copy SDK source first (needed for frontend dependency)
COPY packages/typescript/sdk/ ./packages/typescript/sdk/
# Install SDK dependencies first
RUN cd packages/typescript/sdk && npm install
# Copy frontend package.json
COPY packages/typescript/frontend/package*.json ./packages/typescript/frontend/
# Install frontend dependencies (this will build the SDK via the prepare script)
RUN cd packages/typescript/frontend && npm install

# Build-time arguments
ARG NEXT_PUBLIC_FASTAPI_FRONTEND_URL
ARG NODE_ENV=production

# Set build-time environment variables
ENV NEXT_PUBLIC_FASTAPI_FRONTEND_URL=${NEXT_PUBLIC_FASTAPI_FRONTEND_URL:-http://localhost:8000}
ENV NODE_ENV=${NODE_ENV}

RUN echo "NEXT_PUBLIC_FASTAPI_FRONTEND_URL=${NEXT_PUBLIC_FASTAPI_FRONTEND_URL}"
RUN echo "FASTAPI_BACKEND_URL=${FASTAPI_BACKEND_URL}"
RUN echo "NODE_ENV=${NODE_ENV}"
# Now copy the rest of the frontend files
COPY packages/typescript/frontend/ ./packages/typescript/frontend/
ENV NODE_OPTIONS=--max-old-space-size=4096
RUN cd packages/typescript/frontend && npm run build

EXPOSE 3000

# Use slim Python 3.12 as the base image
FROM python:3.12-slim AS backend

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV STRIPE_PRODUCT_TAG=""

# Set the working directory in the container
WORKDIR /app

# Copy the packages
COPY packages/ ./packages/

# Install system dependencies and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv

# Copy only packages requirements first
COPY packages/python/requirements.txt ./packages/python/
RUN uv pip install --system --no-cache-dir -r packages/python/requirements.txt

EXPOSE 8000
