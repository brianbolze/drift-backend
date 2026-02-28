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
make seed       # load reference data (idempotent)
make reset-seed # wipe all data tables and reload from scratch
```

## Code Style

Formatting: **Black** (line-length 120). Linting: **flake8** + bugbear. Import sorting: **isort** (black profile). All configured in `pyproject.toml` and `.flake8`.

VS Code: settings are in `.vscode/settings.json` — format-on-save is enabled.

## Seed Data

All reference data (manufacturers, calibers, chambers, platforms, rankings, etc.) lives in `data/seed.sql` — a single SQL file dumped from the verified database. The seed is idempotent (`INSERT OR IGNORE`) and handles FK ordering automatically.

To regenerate `seed.sql` after making changes to the database:

```bash
python scripts/dump_seed.py   # (or manually: sqlite3 data/drift.db .dump)
```

Archived curation scripts and JSON files from the original data build-out are in `scripts/_archive/` and `data/_archive/`.

## Project Structure

```
src/drift/
├── models/         # SQLAlchemy models (Manufacturer, Caliber, Bullet, etc.)
├── schemas/        # Pydantic schemas
├── pipeline/       # Scraping + extraction pipeline
└── cli/            # Human review tooling
scripts/
├── seed_db.py      # Load/reset seed data
└── dump_seed.py    # Regenerate seed.sql from drift.db
data/
├── drift.db        # SQLite database (source of truth)
└── seed.sql        # Seed data (auto-generated from drift.db)
docs/               # Design docs, research, domain reference
alembic/            # Database migrations
```

## Key Docs

- `docs/engineering_overview.md` — Domain primer and architecture
- `docs/wi2_design_proposal.md` — Schema spec and pipeline design (source of truth)
- `docs/wi2-doro-learnings.md` — Pipeline patterns from prior system
- `docs/python-code-patterns.md` — Code style preferences
