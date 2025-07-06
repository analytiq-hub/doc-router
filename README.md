# [Smart Document Router](https://docrouter.ai)

[![Backend Tests](https://github.com/analytiq-hub/doc-router/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/analytiq-hub/doc-router/actions/workflows/backend-tests.yml)

The [Smart Document Router](https://docrouter.ai) is an open source Document Understanding and Data Extraction tool. It is like [LLamaCloud](https://docs.llamaindex.ai), but for Enterprises using ERP systems.
* It ingests unstructured docs from faxes, email, and ERPs.
* It selects streams of docs that can be processed autonomously with LLMs and NLP - reducing the need for time-consuming, expensive manual workflows.

The Document Router is designed to work with a human-in-the-loop and can processes financial data correctly 'on the nose'. (We are not doing RAG!)

# Tech stack
* NextJS, NextAuth, MaterialUI, TailwindCSS
* FastAPI
* MongoDB
* Pydantic
* LiteLLM
* OpenAI, Anthropic, Gemini, Groq/DeepSeek...

[PyData Boston DocRouter Slides](https://docs.google.com/presentation/d/14nAjSmZA1WGViqSk5IZuzggSuJZQPYrwTGsPjO6FPfU) (Feb '24) have more details about tech stack, and how Cursor AI was used to build the DocRouter.

# User Experience
![Smart Document Router](./docs/assets/files.png)
![Smart Document Router](./docs/assets/extractions.png)

# Example Deployment
![Smart Document Router](./docs/assets/doc-router-arch.png)

# Project Slides
[Smart Document Router Slides](https://docs.google.com/presentation/d/1wU0jtcXnqCu5nxaRRCp7D37Q63i4gr-4ASdUhO__tM8)

# Docs
* Installation
  * [Local Development Setup](./docs/INSTALL.local_devel.md)
  * [Docker Setup](./docs/INSTALL.docker.md)
  * [AWS Setup](./docs/INSTALL.aws.md)
* Development
  * [Database Migrations Guide](./backend/analytiq_data/migrations/MIGRATIONS.md)

