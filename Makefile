# ═══════════════════════════════════════════════════════════════════════════
# Shooting Data Management System - Makefile
# ═══════════════════════════════════════════════════════════════════════════

# Configuration
VENV := .venv/bin
PYTHON := python3

# Pipeline Configuration (can be overridden via environment)
PIPELINE_PROVIDER ?= anthropic
PIPELINE_MODEL ?=
PIPELINE_LIMIT ?= 0

# Default target
.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════════════════
# Phony targets
# ═══════════════════════════════════════════════════════════════════════════

.PHONY: help
.PHONY: install test lint format clean
.PHONY: migrate new-migration seed reset-seed describe-db
.PHONY: pipeline-install pipeline-models pipeline-shopping-list pipeline-validate pipeline-fetch
.PHONY: pipeline-extract pipeline-extract-openai pipeline-extract-anthropic
.PHONY: pipeline-extract-gpt-5 pipeline-extract-gpt-5-nano pipeline-extract-claude-4
.PHONY: pipeline-extract-parallel pipeline-env-check
.PHONY: pipeline-store pipeline-store-commit pipeline-review
.PHONY: pipeline-status pipeline-all pipeline-clean

# ═══════════════════════════════════════════════════════════════════════════
# Help & Documentation
# ═══════════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo "═══════════════════════════════════════════════════════════════════════════"
	@echo " Shooting Data Management System - Available Commands"
	@echo "═══════════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Setup & Development:"
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | grep -v pipeline | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Database Management:"
	@grep -E '^(migrate|new-migration|seed|reset-seed|describe-db):.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Data Pipeline:"
	@grep -E '^pipeline-[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Pipeline Environment Variables:"
	@echo "  PIPELINE_PROVIDER    LLM provider: anthropic (default) or openai"
	@echo "  PIPELINE_MODEL       Specific model to use (see 'make pipeline-models')"
	@echo "  PIPELINE_LIMIT       Max URLs to process (0 = all, default: 0)"
	@echo ""
	@echo "Examples:"
	@echo "  make pipeline-models                      # List all available models"
	@echo "  make pipeline-extract-openai              # Use OpenAI (default: gpt-4.1-mini)"
	@echo "  make pipeline-extract-anthropic           # Use Anthropic (default: claude-haiku-4-5)"
	@echo "  make pipeline-extract PIPELINE_MODEL=claude-opus-4-6"
	@echo "  make pipeline-extract PIPELINE_MODEL=gpt-5-nano PIPELINE_LIMIT=5"
	@echo "  make pipeline-extract-parallel            # Run both providers in parallel"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════════════"

# ═══════════════════════════════════════════════════════════════════════════
# Setup & Development
# ═══════════════════════════════════════════════════════════════════════════

install: ## Install project dependencies and set up virtual environment
	$(PYTHON) -m venv .venv
	$(VENV)/pip install --upgrade pip
	$(VENV)/pip install -e ".[dev]"
	$(VENV)/alembic upgrade head
	@echo "✓ Installation complete"

test: ## Run test suite with verbose output
	$(VENV)/pytest tests/ -v

lint: ## Check code style and formatting (without modifying files)
	@echo "Running code quality checks..."
	$(VENV)/black --check src/ tests/ scripts/
	$(VENV)/isort --check src/ tests/ scripts/
	$(VENV)/flake8 src/ tests/ scripts/
	@echo "✓ All checks passed"

format: ## Auto-format code with black and isort
	@echo "Formatting code..."
	$(VENV)/isort src/ tests/ scripts/
	$(VENV)/black src/ tests/ scripts/
	@echo "✓ Code formatted"

clean: ## Remove build artifacts, cache files, and virtual environment
	rm -rf .venv
	rm -rf __pycache__ .pytest_cache .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Cleaned build artifacts"

# ═══════════════════════════════════════════════════════════════════════════
# Database Management
# ═══════════════════════════════════════════════════════════════════════════

migrate: ## Apply database migrations
	$(VENV)/alembic upgrade head
	@echo "✓ Migrations applied"

new-migration: ## Create a new database migration (interactive)
	@read -p "Migration message: " msg; \
	$(VENV)/alembic revision --autogenerate -m "$$msg"

seed: ## Seed database with sample data
	$(VENV)/python scripts/seed_db.py
	@echo "✓ Database seeded"

reset-seed: ## Reset database and re-seed with fresh data
	$(VENV)/python scripts/seed_db.py --reset
	@echo "✓ Database reset and seeded"

describe-db: ## Display database schema and statistics
	$(VENV)/python scripts/describe_db.py

# ═══════════════════════════════════════════════════════════════════════════
# Data Pipeline
# ═══════════════════════════════════════════════════════════════════════════

pipeline-install: ## Install pipeline-specific dependencies
	$(VENV)/pip install -e ".[dev,pipeline]"
	@echo "✓ Pipeline dependencies installed"

pipeline-models: ## List available LLM models for each provider
	$(VENV)/python scripts/list_models.py

pipeline-shopping-list: ## Generate shopping list for data sources
	$(VENV)/python scripts/generate_shopping_list.py

pipeline-validate: ## Validate pipeline manifest and configuration
	$(VENV)/python scripts/validate_manifest.py

pipeline-fetch: ## Fetch data from external sources
	$(VENV)/python scripts/pipeline_fetch.py

pipeline-extract: ## Extract and transform fetched data (use PIPELINE_PROVIDER env var)
	$(VENV)/python scripts/pipeline_extract.py \
		--provider $(PIPELINE_PROVIDER) \
		$(if $(PIPELINE_MODEL),--model $(PIPELINE_MODEL)) \
		$(if $(filter-out 0,$(PIPELINE_LIMIT)),--limit $(PIPELINE_LIMIT))

pipeline-extract-openai: ## Extract data using OpenAI models
	@$(MAKE) pipeline-extract PIPELINE_PROVIDER=openai

pipeline-extract-anthropic: ## Extract data using Anthropic models (Claude)
	@$(MAKE) pipeline-extract PIPELINE_PROVIDER=anthropic

pipeline-extract-gpt-5: ## Extract using GPT-5 (most capable OpenAI model)
	@$(MAKE) pipeline-extract PIPELINE_PROVIDER=openai PIPELINE_MODEL=gpt-5

pipeline-extract-gpt-5-nano: ## Extract using GPT-5-nano (fast & cost-effective)
	@$(MAKE) pipeline-extract PIPELINE_PROVIDER=openai PIPELINE_MODEL=gpt-5-nano

pipeline-extract-claude-4: ## Extract using Claude Opus 4.6 (most capable Anthropic)
	@$(MAKE) pipeline-extract PIPELINE_PROVIDER=anthropic PIPELINE_MODEL=claude-opus-4-6

pipeline-extract-parallel: ## Extract with both providers in parallel (compare results)
	@echo "Starting parallel extraction with OpenAI and Anthropic..."
	@$(MAKE) pipeline-extract-openai &
	@$(MAKE) pipeline-extract-anthropic &
	@wait
	@echo "✓ Parallel extraction complete"

pipeline-env-check: ## Check pipeline environment setup and API keys
	@echo "Checking pipeline environment..."
	@printf "  Python version: "
	@$(VENV)/python --version
	@printf "  OpenAI API key: "
	@if [ -n "$${OPENAI_API_KEY}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then echo "✓ Set"; else echo "✗ Not set"; fi
	@printf "  Anthropic API key: "
	@if [ -n "$${ANTHROPIC_API_KEY}" ] || grep -q "ANTHROPIC_API_KEY" .env 2>/dev/null; then echo "✓ Set"; else echo "✗ Not set"; fi
	@printf "  Pipeline deps: "
	@if $(VENV)/pip show anthropic >/dev/null 2>&1; then echo "✓ Installed"; else echo "✗ Not installed (run: make pipeline-install)"; fi

pipeline-store: ## Store processed data (dry-run mode)
	$(VENV)/python scripts/pipeline_store.py

pipeline-store-commit: ## Store processed data and commit to database
	$(VENV)/python scripts/pipeline_store.py --commit

pipeline-review: ## Review pipeline results and data quality
	$(VENV)/python scripts/pipeline_review.py --list

pipeline-status: ## Display detailed pipeline execution status
	$(VENV)/python scripts/pipeline_status.py --verbose

pipeline-all: pipeline-shopping-list pipeline-validate pipeline-fetch pipeline-extract pipeline-store ## Run complete pipeline (dry-run)
	@echo "═══════════════════════════════════════════════════════════════════════════"
	@echo "✓ Pipeline complete (dry-run mode)"
	@echo "  Run 'make pipeline-store-commit' to commit changes to database"
	@echo "═══════════════════════════════════════════════════════════════════════════"

pipeline-clean: ## Clean pipeline temporary files and cache
	rm -rf data/pipeline/cache/*
	rm -rf data/pipeline/tmp/*
	@echo "✓ Pipeline cache cleaned"
