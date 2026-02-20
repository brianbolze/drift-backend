.PHONY: install test lint format migrate new-migration

VENV := .venv/bin

install:
	python3 -m venv .venv
	$(VENV)/pip install -e ".[dev]"
	$(VENV)/alembic upgrade head

test:
	$(VENV)/pytest tests/ -v

lint:
	$(VENV)/black --check src/ tests/
	$(VENV)/isort --check src/ tests/
	$(VENV)/flake8 src/ tests/

format:
	$(VENV)/isort src/ tests/
	$(VENV)/black src/ tests/

migrate:
	$(VENV)/alembic upgrade head

new-migration:
	@read -p "Migration message: " msg; \
	$(VENV)/alembic revision --autogenerate -m "$$msg"
