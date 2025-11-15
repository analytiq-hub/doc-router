SHELL := /bin/bash

setup:
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
	uv pip install -e packages/python/docrouter_sdk ; \
	# Ensure test dependencies are installed
	uv pip install pytest-asyncio pytest-cov pytest-xdist

dev: setup
	cp .env packages/typescript/frontend/.env.local
	./start-all.sh

install: setup
	# Install and build all TypeScript packages
	cd packages/typescript/docrouter-sdk && npm install && npm run build
	cd packages/typescript/docrouter-mcp && npm install && npm run build
	cd packages/typescript/frontend && npm install

deploy:
	# Use .env for runtime env vars without baking them into images
	docker compose down ; \
	docker compose --env-file .env up -d --build

tests: setup
	. .venv/bin/activate && pytest -n auto packages/python/tests/

tests-scale: setup
	. .venv/bin/activate && pytest packages/python/tests_scale

tests-all: tests tests-scale

setup-ui:
	cd tests-ui && npm install

tests-ui: setup-ui
	cd tests-ui && npm run test:ui

tests-ui-debug: setup-ui
	cd tests-ui && npm run test:ui:debug

tests-ts:
	cd packages/typescript/docrouter-sdk && npm install && npm run test:all
	cd packages/typescript/docrouter-mcp && npm install && npm run test

clean:
	rm -rf .venv

.PHONY: dev tests setup tests-ts install
