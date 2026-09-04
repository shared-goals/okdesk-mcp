.DEFAULT_GOAL := help

ENV_FILE ?= .env

.PHONY: help hep install run test format debug

help: ## Show available development targets.

	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-10s %s\n", $$1, $$2}'

hep: help ## Alias for help.

install: ## Create or update the uv environment and dependencies.
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync --upgrade

run: ## Run the Okdesk MCP server over stdio.
	uv run okdesk-mcp

test: ## Run the test suite.
	uv run pytest

format: ## Fix lint issues and format the project with Ruff.
	uv run ruff check --fix .
	uv run ruff format .

debug: ## Print live report counts directly via OkdeskClient (bypasses MCP/Hermes).
	@test -f "$(ENV_FILE)" || { echo "Env file not found: $(ENV_FILE) (copy .env.example to .env)" >&2; exit 1; }
	@set -a; . "$(ENV_FILE)"; set +a; uv run python scripts/debug_report.py