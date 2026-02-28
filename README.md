# Drift Ballistics Backend

Data pipeline and search backend for the Drift Ballistics app. Scrapes manufacturer product data, extracts structured ammo/firearms specs via LLM, and exports a bundled SQLite database for on-device search.

## Setup

```bash
make install    # creates venv, installs deps, runs migrations
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

## Common Commands

```bash
make test       # run tests
make lint       # black + isort + flake8 (check only)
make format     # black + isort (auto-fix)
make migrate    # run pending migrations
```

## Code Style

Formatting: **Black** (line-length 120). Linting: **flake8** + bugbear. Import sorting: **isort** (black profile). All configured in `pyproject.toml` and `.flake8`.

VS Code: settings are in `.vscode/settings.json` — format-on-save is enabled.

## Project Structure

```
src/drift/
├── models/         # SQLAlchemy models (Manufacturer, Caliber, Bullet, etc.)
├── schemas/        # Pydantic schemas
├── pipeline/       # Scraping + extraction pipeline
└── cli/            # Human review tooling
docs/               # Design docs, research, domain reference
alembic/            # Database migrations
```

## Key Docs

- `docs/engineering_overview.md` — Domain primer and architecture
- `docs/wi2_design_proposal.md` — Schema spec and pipeline design (source of truth)
- `docs/wi2-doro-learnings.md` — Pipeline patterns from prior system
- `docs/python-code-patterns.md` — Code style preferences
