# Contributing to Smart Document Router

Thank you for your interest in contributing to Smart Document Router! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch** for your changes
4. **Make your changes** following the guidelines below
5. **Test your changes** thoroughly
6. **Submit a pull request**

## Development Setup

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- MongoDB
- Docker (optional)

### Local Development
1. Follow the [Local Development Setup](./docs/INSTALL.local_devel.md) guide
2. Run the backend tests: `make test`
3. Run the frontend: `cd packages/typescript/frontend && npm run dev`

## Code Style Guidelines

### Frontend (Next.js/React)
- Use TypeScript for all new code
- Follow the existing component structure in `packages/typescript/frontend/src/components/`
- Use Tailwind CSS for styling (Material-UI for complex components)
- Write meaningful component and function names
- Add proper TypeScript types

### Backend (FastAPI/Python)
- Add docstrings for public functions
- Use Pydantic models for data validation

## Testing

- Write tests for new features
- Ensure all existing tests pass
- Run the test suite before submitting PRs

## Pull Request Guidelines

- Provide a clear description of your changes
- Include any relevant issue numbers
- Ensure your code follows the project's style guidelines
- Add tests for new functionality
- Update documentation if needed

## Questions or Need Help?

- Open an issue for bugs or feature requests
- Join our community discussions
- Check existing issues and pull requests

Thank you for contributing to Smart Document Router! 