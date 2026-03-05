.PHONY: install test lint format migrate new-migration seed reset-seed describe-db
.PHONY: pipeline-install pipeline-shopping-list pipeline-validate pipeline-fetch
.PHONY: pipeline-extract pipeline-store pipeline-store-commit pipeline-review
.PHONY: pipeline-status pipeline-all

VENV := .venv/bin

install:
	python3 -m venv .venv
	$(VENV)/pip install -e ".[dev]"
	$(VENV)/alembic upgrade head

test:
	$(VENV)/pytest tests/ -v

lint:
	$(VENV)/black --check src/ tests/ scripts/
	$(VENV)/isort --check src/ tests/ scripts/
	$(VENV)/flake8 src/ tests/ scripts/

format:
	$(VENV)/isort src/ tests/ scripts/
	$(VENV)/black src/ tests/ scripts/

migrate:
	$(VENV)/alembic upgrade head

new-migration:
	@read -p "Migration message: " msg; \
	$(VENV)/alembic revision --autogenerate -m "$$msg"

seed:
	$(VENV)/python scripts/seed_db.py

reset-seed:
	$(VENV)/python scripts/seed_db.py --reset

describe-db:
	$(VENV)/python scripts/describe_db.py

# ── Pipeline targets ─────────────────────────────────────────────────────

pipeline-install:
	$(VENV)/pip install -e ".[dev,pipeline]"

pipeline-shopping-list:
	$(VENV)/python scripts/generate_shopping_list.py

pipeline-validate:
	$(VENV)/python scripts/validate_manifest.py

pipeline-fetch:
	$(VENV)/python scripts/pipeline_fetch.py

pipeline-extract:
	$(VENV)/python scripts/pipeline_extract.py

pipeline-store:
	$(VENV)/python scripts/pipeline_store.py

pipeline-store-commit:
	$(VENV)/python scripts/pipeline_store.py --commit

pipeline-review:
	$(VENV)/python scripts/pipeline_review.py --list

pipeline-status:
	$(VENV)/python scripts/pipeline_status.py --verbose

pipeline-all: pipeline-shopping-list pipeline-validate pipeline-fetch pipeline-extract pipeline-store
	@echo "Pipeline complete (dry-run). Run 'make pipeline-store-commit' to write to DB."
