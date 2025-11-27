# Environment Variables Documentation

This document explains all environment variables used in the DocRouter project, their purpose, and how they are used throughout the codebase.

## Overview

The DocRouter project uses a single `.env` file at the project root that is shared between the FastAPI backend, Next.js frontend, and worker processes. The environment variables are loaded using `python-dotenv` and are accessible to all components of the system.

## Core Application Variables

### `ENV`
- **Purpose**: Defines the current environment (development, production, testing)
- **Default**: `"dev"`
- **Usage**: 
  - Used to determine the MongoDB database name
  - Controls logging and debugging behavior
  - Used in FastAPI backend (`packages/python/app/main.py`, `packages/python/app/auth.py`)
  - Used in worker processes (`packages/python/worker/worker.py`)
  - Used in frontend MongoDB connection (`packages/typescript/frontend/src/utils/mongodb.ts`)
- **Values**: `"dev"`, `"prod"`, `"test"` (for testing)

### `MONGODB_URI`
- **Purpose**: MongoDB connection string
- **Default**: `"mongodb://localhost:27017"`
- **Usage**:
  - Primary database connection for all components
  - Used in FastAPI backend (`packages/python/app/main.py`, `packages/python/app/auth.py`)
  - Used in worker processes (`packages/python/worker/worker.py`)
  - Used in frontend MongoDB connection (`packages/typescript/frontend/src/utils/mongodb.ts`)
  - Used in payments module (`packages/python/app/payments.py`)
- **Format**: `mongodb://[username:password@]host:port[/database]?authSource=admin`

### `FASTAPI_ROOT_PATH`
- **Purpose**: Root path for FastAPI application (useful for reverse proxies)
- **Default**: `"/"`
- **Usage**: Used in FastAPI app configuration (`packages/python/app/main.py`)

## Authentication & NextAuth Variables

### `NEXTAUTH_URL`
- **Purpose**: Base URL for NextAuth.js authentication
- **Usage**:
  - Used in FastAPI backend for CORS configuration
  - Used in payments module for webhook URLs
  - Added to CORS allowed origins if present
- **Format**: `https://yourdomain.com` or `http://localhost:3000`

### `NEXTAUTH_SECRET`
- **Purpose**: Secret key for NextAuth.js session encryption
- **Required**: Yes
- **Usage**: 
  - Used in NextAuth configuration (`packages/typescript/frontend/src/auth.ts`)
  - JWT token signing in authentication (`packages/python/app/auth.py`)
  - Token encryption/decryption (`packages/python/analytiq_data/crypto/encryption.py`)

### `AUTH_GITHUB_ID`
- **Purpose**: GitHub OAuth application client ID
- **Usage**: GitHub authentication provider configuration (`packages/typescript/frontend/src/auth.ts`)

### `AUTH_GITHUB_SECRET`
- **Purpose**: GitHub OAuth application client secret
- **Usage**: GitHub authentication provider configuration (`packages/typescript/frontend/src/auth.ts`)

### `AUTH_GOOGLE_ID`
- **Purpose**: Google OAuth application client ID
- **Usage**: Google authentication provider configuration (`packages/typescript/frontend/src/auth.ts`)

### `AUTH_GOOGLE_SECRET`
- **Purpose**: Google OAuth application client secret
- **Usage**: Google authentication provider configuration (`packages/typescript/frontend/src/auth.ts`)

## Frontend Configuration

### `NEXT_PUBLIC_FASTAPI_FRONTEND_URL`
- **Purpose**: URL for the FastAPI backend as seen by the frontend
- **Default**: `"http://localhost:8000"`
- **Usage**:
  - API client configuration (`packages/typescript/frontend/src/utils/api.ts`)
  - Developer settings page (`packages/typescript/frontend/src/app/settings/user/developer/page.tsx`)
  - Formio provider configuration (`packages/typescript/frontend/src/components/FormioProvider.tsx`)

## AWS Configuration

### `AWS_ACCESS_KEY_ID`
- **Purpose**: AWS access key for AWS services
- **Usage**:
  - AWS client initialization (`packages/python/analytiq_data/aws/client.py`)
  - Used in startup process (`packages/python/app/startup.py`)

### `AWS_SECRET_ACCESS_KEY`
- **Purpose**: AWS secret access key for AWS services
- **Usage**:
  - AWS client initialization (`packages/python/analytiq_data/aws/client.py`)
  - Used in startup process (`packages/python/app/startup.py`)

### `AWS_S3_BUCKET_NAME`
- **Purpose**: S3 bucket name for file storage
- **Default**: `"analytiq-data"`
- **Usage**: AWS S3 operations (`packages/python/analytiq_data/aws/client.py`)

### `AWS_BEDROCK_API_KEY`
- **Purpose**: AWS Bedrock API key for LLM services
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

## Email Configuration

### `SES_FROM_EMAIL`
- **Purpose**: Email address used as sender for AWS SES emails
- **Usage**: Email sending configuration (`packages/python/app/main.py`)

## LLM Provider API Keys

The following environment variables are used for various LLM providers:

### `ANTHROPIC_API_KEY`
- **Purpose**: Anthropic API key for Claude models
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `AZURE_OPENAI_API_KEY`
- **Purpose**: Azure OpenAI API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `AZURE_AI_STUDIO_API_KEY`
- **Purpose**: Azure AI Studio API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `GEMINI_API_KEY`
- **Purpose**: Google Gemini API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `GROQ_API_KEY`
- **Purpose**: Groq API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `MISTRAL_API_KEY`
- **Purpose**: Mistral AI API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `OPENAI_API_KEY`
- **Purpose**: OpenAI API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

### `VERTEX_AI_API_KEY`
- **Purpose**: Google Vertex AI API key
- **Usage**: LLM provider configuration (`packages/python/analytiq_data/llm/providers.py`)

## Payment Configuration (Stripe)

### `STRIPE_SECRET_KEY`
- **Purpose**: Stripe secret key for payment processing
- **Usage**: Stripe client initialization (`packages/python/app/payments.py`)

### `STRIPE_WEBHOOK_SECRET`
- **Purpose**: Stripe webhook secret for verifying webhook signatures
- **Usage**: Stripe webhook verification (`packages/python/app/payments.py`)

## System Administration

### `ADMIN_EMAIL`
- **Purpose**: Email address for the default system administrator
- **Usage**: System initialization (`packages/python/app/startup.py`)

### `ADMIN_PASSWORD`
- **Purpose**: Password for the default system administrator
- **Usage**: System initialization (`packages/python/app/startup.py`)

## Worker Configuration

### `N_WORKERS`
- **Purpose**: Number of worker processes to run
- **Default**: `"1"`
- **Usage**: Worker process scaling (`packages/python/worker/worker.py`)

## Logging Configuration

### `LOG_LEVEL`
- **Purpose**: Logging level for the application
- **Default**: `"INFO"`
- **Usage**: Logging configuration (`packages/python/analytiq_data/common/setup.py`)
- **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## CORS Configuration

### `CORS_ORIGINS`
- **Purpose**: Comma-separated list of allowed CORS origins
- **Default**: `"http://localhost:3000,http://127.0.0.1:3000,http://host.docker.internal:3000"`
- **Usage**: CORS middleware configuration (`packages/python/app/main.py`)

## Testing Variables

### `BASE_URL`
- **Purpose**: Base URL for UI testing
- **Default**: `"http://localhost:3000"`
- **Usage**: UI test configuration (`tests-ui/utils/test-helpers.ts`)

### `API_URL`
- **Purpose**: API URL for UI testing
- **Default**: `"http://localhost:8000"`
- **Usage**: UI test configuration (`tests-ui/utils/test-helpers.ts`)

### `SCREENSHOTS`
- **Purpose**: Enable screenshot capture during tests
- **Usage**: UI test configuration (`tests-ui/utils/test-helpers.ts`)

### `HEADLESS`
- **Purpose**: Run browser tests in headless mode
- **Default**: `true`
- **Usage**: UI test configuration (`tests-ui/setup.ts`)

### `SLOW_MO`
- **Purpose**: Slow down test execution for debugging
- **Usage**: UI test configuration (`tests-ui/setup.ts`)

### `DEVTOOLS`
- **Purpose**: Enable browser devtools during tests
- **Usage**: UI test configuration (`tests-ui/setup.ts`)

## MCP (Model Context Protocol) Variables

### `DOCROUTER_URL`
- **Purpose**: DocRouter API URL for MCP server
- **Usage**: MCP server configuration (`packages/docrouter_mcp/docrouter_mcp_server.py`)

### `DOCROUTER_ORG_ID`
- **Purpose**: Organization ID for MCP server
- **Usage**: MCP server configuration (`packages/docrouter_mcp/docrouter_mcp_server.py`)

### `DOCROUTER_ORG_API_TOKEN`
- **Purpose**: Organization API token for MCP server
- **Usage**: MCP server configuration (`packages/docrouter_mcp/docrouter_mcp_server.py`)

## Database Configuration

### `MONGO_URI`
- **Purpose**: Alternative MongoDB URI (used in payments module)
- **Default**: `"mongodb://localhost:27017"`
- **Usage**: Payments module database connection (`packages/python/app/payments.py`)

## Environment-Specific Behavior

### Development Environment (`ENV=dev`)
- Uses local MongoDB instance
- Enables detailed logging
- Allows localhost CORS origins
- Uses development API keys

### Production Environment (`ENV=prod`)
- Uses production MongoDB instance
- Restricts CORS origins
- Uses production API keys
- Enables security features

### Testing Environment (`ENV=pytest`)
- Uses test-specific database
- Enables test-specific configurations
- Used for automated testing

## Docker vs Host-Side Development Configuration

The following variables need to be configured differently when running in Docker containers versus host-side development:

### `MONGODB_URI`
- **Host-side Development**: 
  - Default: `mongodb://localhost:27017`
  - Points to local MongoDB instance running on the host
- **Docker Setup**:
  - **With embedded MongoDB**: `mongodb://admin:admin@mongodb:27017?authSource=admin`
  - **With external MongoDB**: `mongodb://YOUR_HOST_IP:27017` (replace YOUR_HOST_IP with actual host IP)
  - Uses Docker service names (`mongodb`) instead of `localhost`

### `NEXT_PUBLIC_FASTAPI_FRONTEND_URL`
- **Host-side Development**: 
  - Default: `http://localhost:8000`
  - Frontend connects to backend on localhost
- **Docker Setup**:
  - Default: `http://localhost:8000` (but may need to be `http://backend:8000` for internal container communication)
  - Frontend container connects to backend container

### `FASTAPI_ROOT_PATH`
- **Host-side Development**: 
  - Default: `/`
  - No path prefix needed
- **Docker Setup**:
  - Default: `/fastapi`
  - Often set to `/fastapi` for reverse proxy configurations

### `NEXTAUTH_URL`
- **Host-side Development**: 
  - Default: `http://localhost:3000`
- **Docker Setup**:
  - Should match the external URL where the frontend is accessible
  - May need to be set to the host's public IP or domain

### `CORS_ORIGINS`
- **Host-side Development**: 
  - Default: `http://localhost:3000,http://127.0.0.1:3000,http://host.docker.internal:3000`
- **Docker Setup**:
  - May need to include additional origins for container-to-container communication
  - Should include the external frontend URL

### Network-Specific Variables

#### Docker Container Communication
When running in Docker, containers communicate using service names:
- `mongodb://mongodb:27017` (instead of `mongodb://localhost:27017`)
- `http://backend:8000` (for internal container-to-container communication)

#### Host Gateway Access
Docker containers can access host services using:
- `host.docker.internal` (on Docker Desktop)
- Host machine IP address (on Linux)

### Example Configurations

#### Host-Side Development (.env)
```bash
ENV=dev
MONGODB_URI=mongodb://localhost:27017
NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://localhost:8000
FASTAPI_ROOT_PATH=/
NEXTAUTH_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

#### Docker with Embedded MongoDB (.env)
```bash
ENV=dev
MONGODB_URI=mongodb://admin:admin@mongodb:27017?authSource=admin
NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://localhost:8000
FASTAPI_ROOT_PATH=/fastapi
NEXTAUTH_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://host.docker.internal:3000
```

#### Docker with External MongoDB (.env)
```bash
ENV=dev
MONGODB_URI=mongodb://YOUR_HOST_IP:27017
NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://localhost:8000
FASTAPI_ROOT_PATH=/fastapi
NEXTAUTH_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://host.docker.internal:3000
```

### Key Differences Summary

| Variable | Host Development | Docker Setup |
|----------|------------------|--------------|
| `MONGODB_URI` | `localhost:27017` | `mongodb:27017` or `YOUR_HOST_IP:27017` |
| `FASTAPI_ROOT_PATH` | `/` | `/fastapi` |
| Container Communication | N/A | Uses service names |
| Network Access | Direct localhost | Via Docker network |
| CORS Origins | Localhost only | May include additional origins |

## File Loading

The environment variables are loaded from the top-level `.env` file using:
- Python: `python-dotenv` in `packages/python/analytiq_data/common/setup.py`
- Next.js: Automatic loading from project root
- The `.env` file is copied to `packages/typescript/frontend/.env.local` during build process

## Example .env File Structure

```bash
# Core Application
ENV=dev
MONGODB_URI=mongodb://localhost:27017
FASTAPI_ROOT_PATH=/

# Authentication
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret-here
AUTH_GITHUB_ID=your-github-client-id
AUTH_GITHUB_SECRET=your-github-client-secret
AUTH_GOOGLE_ID=your-google-client-id
AUTH_GOOGLE_SECRET=your-google-client-secret

# Frontend
NEXT_PUBLIC_FASTAPI_FRONTEND_URL=http://localhost:8000

# AWS Configuration
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_S3_BUCKET_NAME=analytiq-data

# LLM Providers
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key

# Email
SES_FROM_EMAIL=noreply@yourdomain.com

# Payments
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret

# System Admin
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=secure-admin-password

# Workers
N_WORKERS=1

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```
