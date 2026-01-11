# Quick Start with DockerHub

The easiest way to run DocRouter is using the pre-built Docker images from DockerHub. This guide shows how to use the separate frontend and backend images.

## Prerequisites

- Docker installed and running
- MongoDB instance (see options below)

## Quick Start

### Using Docker Compose (Recommended)

The easiest way to get started is using Docker Compose with the pre-built images:

```bash
# Pull and start using DockerHub images
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml pull
docker compose -f docker-compose.dockerhub.embedded.yml up -d
```

Or use the makefile:
```bash
make deploy-compose-dockerhub-embedded
```

This will:
- Pull the latest frontend and backend images from DockerHub
- Start MongoDB in a container
- Start both frontend and backend services
- Configure everything to work together

## Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Environment Variables

### Required

- `MONGODB_URI` - MongoDB connection string
- `NEXTAUTH_URL` - Public URL of your application (e.g., `http://localhost:3000`)
- `NEXTAUTH_SECRET` - Secret key for NextAuth (generate with: `openssl rand -base64 32`)

### Optional

- `ENV` - Environment (default: `dev`)
- `FASTAPI_ROOT_PATH` - FastAPI root path (default: `/fastapi`)
- `ADMIN_EMAIL` - Admin user email (default: `admin`)
- `ADMIN_PASSWORD` - Admin user password (default: `admin`)
- `OPENAI_API_KEY` - OpenAI API key for LLM features
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GEMINI_API_KEY` - Google Gemini API key
- `GROQ_API_KEY` - Groq API key
- `MISTRAL_API_KEY` - Mistral API key
- `AWS_ACCESS_KEY_ID` - AWS access key for S3/Textract
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_S3_BUCKET_NAME` - S3 bucket name
- `SES_FROM_EMAIL` - AWS SES email for sending emails
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret
- `STRIPE_PRODUCT_TAG` - Stripe product tag
- `AUTH_GITHUB_ID` - GitHub OAuth app ID
- `AUTH_GITHUB_SECRET` - GitHub OAuth app secret
- `AUTH_GOOGLE_ID` - Google OAuth app ID
- `AUTH_GOOGLE_SECRET` - Google OAuth app secret

## Example: Full Configuration

Edit your `.env` file with all the required variables, then:

```bash
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml pull
docker compose -f docker-compose.dockerhub.embedded.yml up -d
```

## Stopping the Services

```bash
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml down
```

Or use the makefile:
```bash
make down-compose
```

## Viewing Logs

```bash
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml logs -f
```

## Updating to Latest Version

```bash
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml pull
docker compose -f docker-compose.dockerhub.embedded.yml up -d
```

## Troubleshooting

### Services exit immediately

Check logs:
```bash
cd deploy/compose
docker compose -f docker-compose.dockerhub.embedded.yml logs
```

Common issues:
- MongoDB connection failed: Check `MONGODB_URI` is correct
- Missing required environment variables
- Port conflicts: Make sure ports 3000 and 8000 are available

### Cannot connect to MongoDB

- Verify MongoDB is running: `docker ps | grep mongo`
- Check connection string format in your `.env` file
- For external MongoDB, ensure network connectivity

### Frontend shows errors

- Check that `NEXTAUTH_URL` matches your actual URL
- Verify `NEXTAUTH_SECRET` is set in your `.env` file
- Check browser console for specific errors

## Production Deployment

For production, consider:

1. **Use a managed MongoDB service** (MongoDB Atlas, AWS DocumentDB, etc.)
2. **Set strong secrets**: Generate secure `NEXTAUTH_SECRET` and `ADMIN_PASSWORD`
3. **Use HTTPS**: Set up reverse proxy (nginx, Traefik) with SSL certificates
4. **Configure proper domain**: Update `NEXTAUTH_URL` to your production domain
5. **Set resource limits**: Use `--memory` and `--cpus` flags
6. **Enable health checks**: The image includes a health check on port 3000
7. **Use Docker secrets**: For sensitive environment variables

For production, use docker-compose with resource limits in the compose file, or deploy the frontend and backend images separately to your orchestration platform (Kubernetes, ECS, etc.).

## Building Your Own Images

If you want to build the images yourself:

```bash
# Build both images with default settings
make dockerhub-build

# Build with custom backend URL
make dockerhub-build NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://backend:8000

# Build and push both images to DockerHub
make dockerhub-build-push
```

See [DOCKERHUB_SETUP.md](./DOCKERHUB_SETUP.md) for more details on building and publishing images.
