# DocRouter Code Structure

## Current Structure Issues
- **docrouter_sdk** does not depend on other modules, but needs to import other modules during unit testing.
- **analytiq_data** eventually needs to be installed on its own, separate from docrouter_sdk.
- **api** and **worker** depend on analytiq_data. The docrouter_sdk currently does not, but in the future it might.
- The frontend is a separate npm-based package

## Python Module Structure 
```
doc-router/
├── packages/ # Python packages that can be independently installed
│ ├── pyproject.toml # Unified package with optional dependencies
│ ├── sdk/ # SDK implementation
│ │ ├── api/ # API client implementation
│ │ ├── models/ # Data models
│ │ └── example/ # Example code
│ │
│ └── tests/ # Tests for all packages
│
├── packages/ # Python packages. Some could be moved to packages/
│ ├── analytiq_data/ # Data handling implementation
│ │ ├── common/ # Common utilities
│ │ ├── mongodb/ # MongoDB integration
│ │ └── llm/ # LLM integration
│ │
│ ├── api/ # API implementation
│ │ └── main.py # FastAPI implementation
│ │
│ ├── worker/ # Worker implementation
│ │ └── worker.py # Background worker tasks
│ │
│ └── tests/ # Tests for all packages
│
├── packages/typescript/frontend/ # Next.js frontend application
│ ├── public/ # Static assets
│ ├── src/
│ │ ├── app/ # App Router components
│ │ ├── components/ # Shared React components
│ │ ├── lib/ # Utility functions
│ │ └── styles/ # Global styles
│ ├── package.json # Frontend dependencies
│ └── next.config.mjs # Next.js configuration
│
├── docker/ # Docker configurations
│ ├── api/ # API service Dockerfile
│ ├── worker/ # Worker service Dockerfile
│ └── frontend/ # Frontend Dockerfile (now in packages/typescript/frontend)
│
├── docs/ # Project documentation
├── package.json # Root package.json for scripts
├── docker-compose.yml # Development environment setup
└── README.md # Project overview
```

## Dependencies Management

### Python Package Dependencies
- Each Python package should have its own `pyproject.toml` file:

```toml
# Example for sdk/pyproject.toml
[project]
name = "docrouter-sdk"
version = "0.1.0"
description = "Python client library for the Smart Document Router API"
# ... other metadata ...
dependencies = [
    "requests>=2.0.0",
    "pydantic>=2.0.0",
    "python-dateutil>=2.0.0"
]

[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "analytiq-data[test]",  # For testing only
]
```