# Docker Compose Deployment Guide

This guide covers deploying doc-router using Docker Compose for local development and simple deployments.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

### With Embedded MongoDB

```bash
cd deploy/compose
docker-compose -f docker-compose.embedded.yml up -d
```

### With External MongoDB

1. Set `MONGODB_URI` environment variable or create `.env` file:
   ```bash
   export MONGODB_URI=mongodb://your-host:27017
   ```

2. Start services:
   ```bash
   cd deploy/compose
   docker-compose up -d
   ```

## Configuration

### Environment Variables

Create a `.env` file in `deploy/compose/` or set environment variables:

```bash
# MongoDB
MONGODB_URI=mongodb://admin:admin@mongodb:27017?authSource=admin

# NextAuth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-here

# API Keys (optional)
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
# ... etc
```

### Ports

Default ports:
- Frontend: `3000`
- Backend: `8000`
- MongoDB: `27018` (embedded compose only)

Modify in `docker-compose.yml` if needed.

## Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build

# View status
docker-compose ps
```

## Accessing Services

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- MongoDB: `localhost:27018` (embedded compose)

## Troubleshooting

### Port Conflicts

If ports are already in use, modify port mappings in `docker-compose.yml`:

```yaml
ports:
  - "3001:3000"  # Use 3001 instead of 3000
```

### MongoDB Connection Issues

1. Check MongoDB is running:
   ```bash
   docker-compose ps mongodb
   ```

2. Check MongoDB logs:
   ```bash
   docker-compose logs mongodb
   ```

3. Verify connection string in environment variables

### Build Failures

1. Check Docker has enough resources (memory, disk)
2. Clear Docker cache:
   ```bash
   docker system prune -a
   ```
3. Rebuild from scratch:
   ```bash
   docker-compose build --no-cache
   ```

## Data Persistence

MongoDB data is persisted in a Docker volume:
- Volume name: `doc-router-local-mongodb`
- Location: Docker's volume storage

To backup:
```bash
docker run --rm -v doc-router-local-mongodb:/data -v $(pwd):/backup \
  mongo:latest tar czf /backup/mongodb-backup.tar.gz /data
```

## Next Steps

- For Kubernetes deployment, see `deploy/shared/docs/kind.md`
- For production deployment, see `deploy/shared/docs/eks.md`
