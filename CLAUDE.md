# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Installation
- `make setup` - Set up Python virtual environment and install all dependencies
- `make dev` - Start all development services (equivalent to `./start-all.sh`)
- `make tests` - Run Python tests in packages/python/tests/
- `make clean` - Remove virtual environment

### Frontend (NextJS)
Navigate to `packages/typescript/frontend/` directory:
- `npm run dev` - Start development server on port 3000
- `npm run build` - Build production bundle
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

### Backend (FastAPI)
From `packages/` directory with activated virtual environment:
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` - Start development server
- `python worker/worker.py` - Start background worker process

### Testing
- `. .venv/bin/activate; pytest -n auto packages/python/tests/` - Run all Python tests with parallel execution
- Tests are located in `packages/python/tests/` with comprehensive coverage of API endpoints

## Architecture Overview

The Smart Document Router is a full-stack document processing platform with human-in-the-loop workflows for enterprise ERP integration.

### Core Components

**Frontend (NextJS + TypeScript)**
- Located in `packages/typescript/frontend/src/`
- Next.js 14 with App Router architecture
- NextAuth.js for authentication with MongoDB adapter
- Material-UI and TailwindCSS for styling
- React Flow for visual workflow builder
- Monaco Editor for code editing
- Multi-tenant organization structure

**Backend (FastAPI + Python)**
- Main API server in `packages/python/app/`
- FastAPI with Pydantic models for data validation
- MongoDB for data persistence
- Background worker system in `packages/python/worker/`
- Queue-based task processing

**Data Layer (`packages/python/analytiq_data/`)**
- Common utilities and data models
- MongoDB client and operations
- AWS/Textract integration for OCR
- LLM integrations via LiteLLM (OpenAI, Anthropic, Gemini, Groq)
- Document processing pipelines

**SDK (`packages/python/sdk/`)**
- Python client library for API integration
- Type-safe models and API clients
- Examples in `packages/python/sdk/examples/`

### Key Architectural Patterns

**Multi-tenant Organization Model**
- Organizations contain users, documents, forms, schemas, prompts
- Role-based access control (admin, member)
- Organization-scoped data isolation

**Document Processing Pipeline**
- Upload → OCR (Textract) → LLM Processing → Human Review → Export
- Form-based data extraction with JSON Schema validation
- Tag-based categorization and routing

**Authentication & Authorization**
- NextAuth.js with email/password and social providers
- JWT tokens with MongoDB session storage
- Organization invitation system

## Development Workflow

### Starting Development Environment
1. Run `make setup` to install dependencies
2. Configure the top-level `.env` file
3. Start MongoDB locally or use cloud instance
4. Run `make dev` or `./start-all.sh` to start all services

### Services Running
- FastAPI backend: http://localhost:8000 (API docs at /docs)
- NextJS frontend: http://localhost:3000
- Background worker: processes queue tasks
- Static file server: http://localhost:8080 (for public assets)

### Database Setup
- MongoDB database named `test` for development
- Database migrations in `packages/python/analytiq_data/migrations/`
- MongoDB Compass recommended for database management

### Environment Configuration
- Single `.env` file at project root (MongoDB, AWS, LLM API keys, NextAuth, API URLs)
- Next.js automatically reads from the top-level `.env` file
- Log level controlled via `LOG_LEVEL` environment variable

### Code Organization
- Frontend pages follow Next.js App Router structure in `src/app/`
- API routes in `src/app/api/`
- React components in `src/components/`
- Backend models in `packages/python/app/models.py`
- Shared utilities in `packages/python/analytiq_data/common/`

### Testing Strategy
- Python tests use pytest with async support
- Test database isolation and cleanup
- API endpoint testing with authentication
- Frontend testing not currently configured