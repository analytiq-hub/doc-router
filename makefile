setup:
	# Create and activate virtual environment if it doesn't exist
	if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..." ; \
		python3 -m venv .venv ; \
	fi
	source .venv/bin/activate ; \
	# Install uv if not already installed
	if ! command -v uv &> /dev/null; then \
		echo "Installing uv..." ; \
		curl -LsSf https://astral.sh/uv/install.sh | sh ; \
	fi ; \
	# Install build dependencies
	uv pip install hatchling ; \
	# Install packages in order
	uv pip install -r packages/requirements.txt ; \
	uv pip install -e packages/docrouter_sdk ; \
	uv pip install -e packages/docrouter_mcp ; \
	# Ensure test dependencies are installed
	uv pip install pytest-asyncio pytest-cov pytest-xdist

dev: setup
	./start-all.sh

deploy:
	docker compose down
	docker compose up -d --build

tests: setup
	. .venv/bin/activate && pytest -n auto packages/tests/

tests-ui:
	cd tests && npm run test:ui

tests-ui-debug:
	cd tests && npm run test:ui:debug

clean:
	rm -rf .venv

.PHONY: dev tests setup tests-ui tests-ui-debug