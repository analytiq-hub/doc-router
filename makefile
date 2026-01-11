SHELL := /bin/bash

help:
	@echo "Available make targets:"
	@echo ""
	@echo "  make help                    - Show this help message"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup                   - Interactive menu: Python, TypeScript, Dev (both), Kubernetes, or UI setup"
	@echo "  make setup-dev               - Set up both Python and TypeScript (full dev environment)"
	@echo "  make setup-python            - Set up Python virtual environment and dependencies"
	@echo "  make setup-typescript        - Install and build all TypeScript packages"
	@echo "  make setup-kind              - Set up Kubernetes kind cluster"
	@echo "  make setup-ui                - Set up UI test environment"
	@echo ""
	@echo "Development:"
	@echo "  make deploy-dev              - Start local development environment"
	@echo ""
	@echo "Deployment (Interactive):"
	@echo "  make deploy                  - Interactive menu: Local, Docker Compose, or Kubernetes"
	@echo ""
	@echo "Deployment (Direct):"
	@echo "  make deploy-compose          - Deploy to Docker Compose"
	@echo "  make deploy-compose-embedded - Deploy to Docker Compose with embedded MongoDB"
	@echo "  make deploy-kind             - Deploy to Kubernetes kind cluster"
	@echo ""
	@echo "Shutdown (Interactive):"
	@echo "  make down                    - Interactive menu: Stop containers or remove volumes"
	@echo ""
	@echo "Shutdown (Direct):"
	@echo "  make down-compose            - Stop Docker Compose containers"
	@echo "  make down-compose-clean      - Stop Docker Compose and remove volumes"
	@echo "  make down-kind               - Delete Kubernetes kind cluster"
	@echo ""
	@echo "Testing:"
	@echo "  make tests                   - Run Python unit tests"
	@echo "  make tests-scale             - Run Python scale tests"
	@echo "  make tests-all               - Run all Python tests"
	@echo "  make tests-ui                - Run UI tests"
	@echo "  make tests-ui-debug          - Run UI tests in debug mode"
	@echo "  make tests-ts                - Run TypeScript SDK and MCP tests"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean                   - Remove Python virtual environment"

setup:
	@if ! command -v gum &> /dev/null; then \
		echo "Error: gum is not installed. Please install it first:"; \
		echo "  On macOS: brew install gum"; \
		echo "  On Linux: See https://github.com/charmbracelet/gum#installation"; \
		exit 1; \
	fi; \
	choice=$$(gum choose --header "Select setup target:" \
		"Development Environment (Python + TypeScript)" \
		"Python Environment" \
		"TypeScript Packages" \
		"Kubernetes (kind)" \
		"UI Test Environment"); \
	case "$$choice" in \
		"Development Environment (Python + TypeScript)") \
			$(MAKE) setup-dev;; \
		"Python Environment") \
			$(MAKE) setup-python;; \
		"TypeScript Packages") \
			$(MAKE) setup-typescript;; \
		"Kubernetes (kind)") \
			$(MAKE) setup-kind;; \
		"UI Test Environment") \
			$(MAKE) setup-ui;; \
		*) \
			echo "No selection made or cancelled."; \
			exit 1;; \
	esac

setup-python:
	# Create and activate virtual environment if it doesn't exist
	if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..." ; \
		python3 -m venv .venv ; \
	fi ; \
	source .venv/bin/activate ; \
	# Install uv if not already installed
	if ! command -v uv &> /dev/null; then \
		echo "Installing uv..." ; \
		curl -LsSf https://astral.sh/uv/install.sh | sh ; \
	fi ; \
	# Install build dependencies
	uv pip install hatchling ; \
	# Install packages in order
	uv pip install -r packages/python/requirements.txt ; \
	uv pip install -e packages/python/sdk ; \
	# Ensure test dependencies are installed
	uv pip install pytest-asyncio pytest-cov pytest-xdist

setup-dev: setup-python setup-typescript

deploy-dev: setup-python
	cp .env packages/typescript/frontend/.env.local
	./start-all.sh

setup-typescript: setup-python
	# Install and build all TypeScript packages
	cd packages/typescript/sdk && npm install && npm run build
	cd packages/typescript/mcp && npm install && npm run build
	cd packages/typescript/frontend && npm install

# Legacy deployment
#deploy:
#	# Use .env for runtime env vars without baking them into images
#	docker compose down ; \
#	docker compose --env-file .env up -d --build

deploy:
	@if ! command -v gum &> /dev/null; then \
		echo "Error: gum is not installed. Please install it first:"; \
		echo "  On macOS: brew install gum"; \
		echo "  On Linux: See https://github.com/charmbracelet/gum#installation"; \
		exit 1; \
	fi; \
	choice=$$(gum choose --header "Select deployment target:" \
		"Local Development" \
		"Docker Compose" \
		"Docker Compose (Embedded MongoDB)" \
		"Kubernetes (kind)"); \
	case "$$choice" in \
		"Local Development") \
			$(MAKE) deploy-dev;; \
		"Docker Compose") \
			$(MAKE) deploy-compose;; \
		"Docker Compose (Embedded MongoDB)") \
			$(MAKE) deploy-compose-embedded;; \
		"Kubernetes (kind)") \
			$(MAKE) deploy-kind;; \
		*) \
			echo "No selection made or cancelled."; \
			exit 1;; \
	esac

deploy-compose:
	cat .env .env.compose > deploy/compose/.env; \
	cd deploy/compose; \
	docker compose down; \
	docker compose -f docker-compose.yml --env-file .env up -d --build

deploy-compose-embedded:
	cat .env .env.compose.embedded > deploy/compose/.env; \
	cd deploy/compose; \
	docker compose down; \
	docker compose -f docker-compose.embedded.yml --env-file .env up -d --build	

down:
	@if ! command -v gum &> /dev/null; then \
		echo "Error: gum is not installed. Please install it first:"; \
		echo "  On macOS: brew install gum"; \
		echo "  On Linux: See https://github.com/charmbracelet/gum#installation"; \
		exit 1; \
	fi; \
	choice=$$(gum choose --header "Select shutdown target:" \
		"Docker Compose (stop containers)" \
		"Docker Compose (stop and remove volumes)" \
		"Kubernetes (kind)"); \
	case "$$choice" in \
		"Docker Compose (stop containers)") \
			$(MAKE) down-compose;; \
		"Docker Compose (stop and remove volumes)") \
			$(MAKE) down-compose-clean;; \
		"Kubernetes (kind)") \
			$(MAKE) down-kind;; \
		*) \
			echo "No selection made or cancelled."; \
			exit 1;; \
	esac

down-compose:
	cd deploy/compose; \
	docker compose down

down-compose-clean:
	cd deploy/compose; \
	docker compose -f docker-compose.embedded.yml down -v 2>/dev/null || true; \
	docker compose -f docker-compose.yml down -v 2>/dev/null || true; \
	docker volume rm compose_doc-router-local-mongodb 2>/dev/null || true; \
	echo "Removed containers and volumes (including MongoDB data volume: compose_doc-router-local-mongodb)"

setup-kind:
	cd deploy/kubernetes/scripts && ./setup-kind.sh

deploy-kind:
	cd deploy/kubernetes/scripts && ./deploy-kind.sh

down-kind:
	@CLUSTER_NAME=$${CLUSTER_NAME:-doc-router}; \
	if kind get clusters | grep -q "^$$CLUSTER_NAME$$"; then \
		echo "Deleting kind cluster: $$CLUSTER_NAME"; \
		kind delete cluster --name $$CLUSTER_NAME; \
	else \
		echo "Kind cluster $$CLUSTER_NAME does not exist"; \
	fi

tests: setup-python
	. .venv/bin/activate && pytest -n auto packages/python/tests/

tests-scale: setup-python
	. .venv/bin/activate && pytest packages/python/tests_scale

tests-all: tests tests-scale

setup-ui:
	cd tests-ui && npm install

tests-ui: setup-ui
	cd tests-ui && npm run test:ui

tests-ui-debug: setup-ui
	cd tests-ui && npm run test:ui:debug

tests-ts:
	cd packages/typescript/sdk && npm install && npm run test:all
	cd packages/typescript/mcp && npm install && npm run test

clean:
	rm -rf .venv

.PHONY: help deploy-dev tests setup setup-dev setup-python setup-typescript setup-kind setup-ui tests-ts deploy deploy-compose deploy-compose-embedded deploy-kind down down-compose down-compose-clean down-kind
