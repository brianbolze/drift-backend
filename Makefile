# ═══════════════════════════════════════════════════════════════════════════
# Shooting Data Management System - Makefile
# ═══════════════════════════════════════════════════════════════════════════

# Configuration
VENV := .venv/bin
PYTHON := python3

# Pipeline Configuration (can be overridden via environment)
PIPELINE_PROVIDER ?=
PIPELINE_MODEL ?=
PIPELINE_LIMIT ?= 0
PIPELINE_PRIORITY_MAX ?= 0

# Default target
.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════════════════
# Phony targets
# ═══════════════════════════════════════════════════════════════════════════

.PHONY: help
.PHONY: install test lint format clean
.PHONY: migrate new-migration seed reset-seed describe-db
.PHONY: pipeline-install pipeline-models pipeline-shopping-list pipeline-validate pipeline-fetch
.PHONY: pipeline-sitemap-watch pipeline-sitemap-watch-dry pipeline-maintenance-digest pipeline-refresh
.PHONY: bc-reconcile bc-reconcile-commit
.PHONY: pipeline-extract pipeline-extract-batch pipeline-extract-sync
.PHONY: pipeline-extract-openai pipeline-extract-anthropic
.PHONY: pipeline-extract-gpt-5 pipeline-extract-gpt-5-nano pipeline-extract-claude-4
.PHONY: pipeline-extract-parallel pipeline-extract-poll pipeline-env-check
.PHONY: pipeline-store pipeline-store-commit pipeline-review
.PHONY: pipeline-status pipeline-all pipeline-clean
.PHONY: curate curate-commit
.PHONY: export-production-db publish-db publish-db-commit

# ═══════════════════════════════════════════════════════════════════════════
# Help & Documentation
# ═══════════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo "═══════════════════════════════════════════════════════════════════════════"
	@echo " Shooting Data Management System - Available Commands"
	@echo "═══════════════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Pipeline Workflow (typical flow):"
	@echo "  1. Generate shopping list     → make pipeline-shopping-list"
	@echo "  2. Generate CoWork prompts    → make pipeline-cowork-prompts"
	@echo "  3. Run CoWork research        → Copy prompts to CoWork, save JSON output"
	@echo "  4. Merge CoWork results       → make pipeline-merge-cowork"
	@echo "  5. Validate manifest          → make pipeline-validate"
	@echo "  6. Fetch HTML from URLs       → make pipeline-fetch"
	@echo "  7. Extract structured data    → make pipeline-extract"
	@echo "  8. Review flagged items       → make pipeline-review"
	@echo "  9. Store in database          → make pipeline-store-commit"
	@echo ""
	@echo "See docs/pipeline_README.md for detailed workflow documentation."
	@echo ""
	@echo "Setup & Development:"
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | grep -v pipeline | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Database Management:"
	@grep -E '^(migrate|new-migration|seed|reset-seed|describe-db):.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Data Curation:"
	@grep -E '^curate[a-z-]*:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Production Export & Publish:"
	@grep -E '^(export|publish)-[a-z-]*:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Data Pipeline:"
	@grep -E '^pipeline-[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Pipeline Environment Variables:"
	@echo "  PIPELINE_PROVIDER    LLM provider: anthropic (default) or openai"
	@echo "  PIPELINE_MODEL       Specific model to use (see 'make pipeline-models')"
	@echo "  PIPELINE_LIMIT       Max URLs to process (0 = all, default: 0)"
	@echo "  PIPELINE_PRIORITY_MAX  Only process entries with priority <= N (0 = no filter)"
	@echo ""
	@echo "Pipeline Examples:"
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
	$(VENV)/pip install -e ".[dev,pipeline,openai]"
	@echo "✓ Pipeline dependencies installed"

pipeline-models: ## List available LLM models for each provider
	$(VENV)/python scripts/list_models.py

pipeline-shopping-list: ## Generate shopping list for data sources
	$(VENV)/python scripts/generate_shopping_list.py

pipeline-cowork-prompts: ## Generate CoWork research prompts for URL discovery
	$(VENV)/python scripts/generate_cowork_prompts.py

pipeline-merge-cowork: ## Merge CoWork research results into URL manifest (prompts for file)
	@read -p "CoWork JSON file path: " file; \
	$(VENV)/python scripts/merge_cowork_results.py "$$file"

pipeline-sitemap-watch: ## Diff manufacturer sitemaps for newly-published URLs
	$(VENV)/python scripts/sitemap_watch.py $(if $(SITEMAP_SLUG),--slug $(SITEMAP_SLUG))

pipeline-sitemap-watch-dry: ## Dry-run sitemap watcher (no snapshot/discovery files written)
	$(VENV)/python scripts/sitemap_watch.py --dry-run $(if $(SITEMAP_SLUG),--slug $(SITEMAP_SLUG))

pipeline-maintenance-digest: ## Generate weekly pipeline-maintenance digest (current ISO week)
	$(VENV)/python scripts/pipeline_maintenance_digest.py $(if $(DIGEST_WEEK),--week $(DIGEST_WEEK))

pipeline-refresh: ## Re-parse cached HTML and report drift vs cached extractions
	$(VENV)/python scripts/pipeline_refresh.py $(if $(REFRESH_DOMAIN),--domain $(REFRESH_DOMAIN)) $(if $(filter-out 0,$(REFRESH_LIMIT)),--limit $(REFRESH_LIMIT))

bc-reconcile: ## Reconcile canonical BC values from BulletBCSource rows (dry-run)
	$(VENV)/python scripts/bc_reconcile.py

bc-reconcile-commit: ## Reconcile canonical BC values and commit to DB
	$(VENV)/python scripts/bc_reconcile.py --commit

pipeline-validate: ## Validate pipeline manifest and configuration
	$(VENV)/python scripts/validate_manifest.py

pipeline-fetch: ## Fetch data from external sources
	$(VENV)/python scripts/pipeline_fetch.py \
		$(if $(filter-out 0,$(PIPELINE_LIMIT)),--limit $(PIPELINE_LIMIT)) \
		$(if $(filter-out 0,$(PIPELINE_PRIORITY_MAX)),--priority-max $(PIPELINE_PRIORITY_MAX))

pipeline-extract: ## Extract data (batch for Anthropic, sync for OpenAI — auto-detected)
	$(VENV)/python scripts/pipeline_extract.py \
		$(if $(PIPELINE_PROVIDER),--provider $(PIPELINE_PROVIDER)) \
		$(if $(PIPELINE_MODEL),--model $(PIPELINE_MODEL)) \
		$(if $(filter-out 0,$(PIPELINE_LIMIT)),--limit $(PIPELINE_LIMIT)) \
		$(if $(filter-out 0,$(PIPELINE_PRIORITY_MAX)),--priority-max $(PIPELINE_PRIORITY_MAX))

pipeline-extract-batch: ## Extract using Anthropic batch API (50% cheaper, no rate limits)
	$(VENV)/python scripts/pipeline_extract.py --batch \
		$(if $(PIPELINE_MODEL),--model $(PIPELINE_MODEL)) \
		$(if $(filter-out 0,$(PIPELINE_LIMIT)),--limit $(PIPELINE_LIMIT)) \
		$(if $(filter-out 0,$(PIPELINE_PRIORITY_MAX)),--priority-max $(PIPELINE_PRIORITY_MAX))

pipeline-extract-sync: ## Extract sequentially with retries (for small runs or OpenAI)
	$(VENV)/python scripts/pipeline_extract.py --sync \
		$(if $(PIPELINE_PROVIDER),--provider $(PIPELINE_PROVIDER)) \
		$(if $(PIPELINE_MODEL),--model $(PIPELINE_MODEL)) \
		$(if $(filter-out 0,$(PIPELINE_LIMIT)),--limit $(PIPELINE_LIMIT)) \
		$(if $(filter-out 0,$(PIPELINE_PRIORITY_MAX)),--priority-max $(PIPELINE_PRIORITY_MAX))

pipeline-extract-poll: ## Poll/collect results from a pending batch (prompts for batch ID)
	@read -p "Batch ID: " bid; \
	$(VENV)/python scripts/pipeline_extract.py --poll $$bid

pipeline-extract-openai: ## Extract data using OpenAI models (sync mode)
	@$(MAKE) pipeline-extract-sync PIPELINE_PROVIDER=openai

pipeline-extract-anthropic: ## Extract data using Anthropic models (batch mode)
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
	rm -rf data/pipeline/fetched/*
	rm -rf data/pipeline/reduced/*
	rm -rf data/pipeline/extracted/*
	rm -rf data/pipeline/review/*
	rm -rf data/pipeline/batches/*
	@echo "✓ Pipeline cache cleaned"

# ═══════════════════════════════════════════════════════════════════════════
# Data Curation
# ═══════════════════════════════════════════════════════════════════════════

curate: ## Preview curation patches (dry-run)
	$(VENV)/python scripts/curate.py

curate-commit: ## Apply curation patches to database
	$(VENV)/python scripts/curate.py --commit

# ═══════════════════════════════════════════════════════════════════════════
# Production Export
# ═══════════════════════════════════════════════════════════════════════════

export-production-db: ## Export production-ready SQLite DB for iOS app
	$(VENV)/python scripts/export_production_db.py

publish-db: ## Dry-run publish production DB to R2 (preview only)
	$(VENV)/python scripts/publish_db.py --dry-run --changelog "$(CHANGELOG)"

publish-db-commit: ## Upload production DB + manifest to R2
	$(VENV)/python scripts/publish_db.py --changelog "$(CHANGELOG)"
