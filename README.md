# [Smart Document Router](https://docrouter.ai)

[![Backend Tests](https://github.com/analytiq-hub/doc-router/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/analytiq-hub/doc-router/actions/workflows/backend-tests.yml)

The [Smart Document Router](https://docrouter.ai) is an open source document processing data layer. 
* It ingests unstructured docs through [REST APIs](https://docrouter.ai/docs/rest-api/) and integrations from faxes, emails, and ERPs.
* It processes documents at scale with OCR and LLMs
* And it chunks, embeds, and organizes documents into queriable [knowledge bases](https://docrouter.ai/docs/knowledge-bases/)

The Document Router is designed to work standalone or with a human-in-the-loop, and can process `medical, insurance, financial, supply chain, and legal documents`.

It acts as a system of record for the `extraction schemas` and `prompts`, and it is portable over all major clouds and LLM providers.

A [Document Agent](https://docrouter.ai/docs/document-agent/) is available to configure prompts and extractions, and to review processed results. 

# Tech stack
* NextJS, NextAuth, MaterialUI, TailwindCSS
* FastAPI
* MongoDB
* Pydantic
* LiteLLM
* OpenAI, Anthropic, Gemini, Vertex AI for GCP, AWS Bedrock, xAI, OpenRouter...

[PyData Boston DocRouter Slides](https://docs.google.com/presentation/d/14nAjSmZA1WGViqSk5IZuzggSuJZQPYrwTGsPjO6FPfU) (Feb '24) have more details about tech stack, and how Cursor AI was used to build the DocRouter.

# User Experience
![Smart Document Router](https://docrouter.ai/assets/images/files.png)
![Smart Document Router](https://docrouter.ai/assets/images/extractions.png)

# Example Deployment
![Smart Document Router](https://docrouter.ai/assets/images/doc-router-arch.png)

# Presentations
* [Smart Document Router Slides](https://docs.google.com/presentation/d/1wU0jtcXnqCu5nxaRRCp7D37Q63i4gr-4ASdUhO__tM8) from Boston PyData, Spring 2025
* [DocRouter.AI: Adventures in CSS and AI Coding](https://www.linkedin.com/pulse/docrouterai-adventures-css-ai-coding-andrei-radulescu-banu-oswxe), Summer 2025

# Docs
* Installation
  * [Local Development Setup](./docs/INSTALL.local_devel.md)
  * [Docker Setup](./docs/INSTALL.docker.md)
  * [AWS Setup](./docs/INSTALL.aws.md)
* Development
  * [Environment Variables Guide](./docs/env.md)
  * [Database Migrations Guide](./backend/analytiq_data/migrations/MIGRATIONS.md)
