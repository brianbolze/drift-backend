# Drift Ballistics Backend

Data pipeline and bundled SQLite database for the Drift Ballistics iOS app. Scrapes manufacturer product pages, extracts structured ammo and rifle specs via LLM, resolves entities against a canonical reference set, and publishes a stripped-down SQLite file over the air.

Offline-first: all LLM extraction happens at ingestion time. The iOS app never calls an inference API.

## Architecture

```
MANIFEST → FETCH → REDUCE → EXTRACT → NORMALIZE → RESOLVE → STORE
                                                              │
                                                              ▼
                                              data/drift.db (source of truth)
                                                              │
                                                ┌─────────────┴─────────────┐
                                                ▼                           ▼
                                   data/patches/*.yaml             export-production-db
                                   (manual curation)               data/production/drift.db
                                                                            │
                                                                            ▼
                                                                       publish-db
                                                              Cloudflare R2 (data.driftballistics.com)
```

Two data flows feed `data/drift.db`:

- **Pipeline** — automated scrape + LLM extraction for bulk coverage. See [docs/pipeline_README.md](docs/pipeline_README.md).
- **Curation patches** — human-authored YAML for fixes, gap-fills, and protected records. See [docs/curation_README.md](docs/curation_README.md).

Everything downstream (production export, OTA publish) runs from `data/drift.db`.

## Setup

```bash
make install    # creates venv, installs deps, runs migrations
```

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

For pipeline work add the LLM extras:

```bash
make pipeline-install   # installs anthropic + openai SDKs
```

## Common Commands

```bash
make help                       # prints organized command reference
make test                       # run test suite
make format && make lint        # required before committing

# Database
make migrate                    # apply pending migrations
make describe-db                # schema + row counts
make seed                       # load reference data from data/seed.sql (idempotent)

# Pipeline (see docs/pipeline_README.md)
make pipeline-fetch             # download HTML for manifest URLs
make pipeline-extract           # LLM extraction (provider auto-detected)
make pipeline-store             # dry-run resolve and preview DB changes
make pipeline-store-commit      # write resolved data to drift.db

# Curation (see docs/curation_README.md)
make curate                     # preview YAML patches
make curate-commit              # apply patches to drift.db

# Production
make export-production-db       # build stripped iOS DB at data/production/drift.db
make publish-db CHANGELOG="…"   # dry-run upload to R2
make publish-db-commit CHANGELOG="…"   # upload production DB + manifest to R2
```

LLM provider is selected via `PIPELINE_PROVIDER` (`anthropic` | `openai`); model via `PIPELINE_MODEL`. See `make help` for the full list.

## Project Structure

```
src/drift/
├── models/             # SQLAlchemy 2.0 ORM (Bullet, Cartridge, RifleModel, EntityAlias, …)
├── pipeline/           # Scrape → reduce → extract → normalize → resolve → store
│   ├── fetching/
│   ├── reduction/
│   ├── extraction/
│   ├── normalization.py
│   ├── resolution/     # EntityResolver, ResolutionConfig, MatchResult
│   └── config.py       # validation ranges, enum allowlists, reducer hints
├── resolution/
│   └── aliases.py      # lookup_entity — shared by curation + pipeline
├── curation.py         # YAML patch loader + applier
├── display_name.py     # canonical display-name builders
└── database.py         # engine + session factory

scripts/                # CLI entry points (pipeline_*, curate, export_production_db, publish_db, …)
data/
├── drift.db            # SQLite source of truth
├── seed.sql            # reference data dump (manufacturers, calibers, chambers, platforms)
├── patches/            # numbered YAML curation patches (001_, 002_, …)
├── production/drift.db # iOS-bundled DB (generated)
└── pipeline/           # generated cache: fetched/, reduced/, extracted/, review/, batches/

alembic/                # migrations
tests/                  # pytest
docs/                   # design docs and references (see below)
sql/                    # ad-hoc queries
```

## Code Style

- **Black** (line length 120), **isort** (black profile), **flake8 + bugbear**. Configured in `pyproject.toml` and `.flake8`.
- Python 3.11+, SQLAlchemy 2.0 (`session.scalars(select(...))`), Pydantic 2.0.
- See [docs/python-code-patterns.md](docs/python-code-patterns.md) for the Pydantic Fields pattern and base schema config.
- VS Code format-on-save is enabled via `.vscode/settings.json`.

Always run `make format && make lint && make test` before committing.

## Key Docs

| Doc | When to read |
| --- | --- |
| [docs/engineering_overview.md](docs/engineering_overview.md) | Ballistics domain primer (BC, DOPE, solver concepts) |
| [docs/pipeline_README.md](docs/pipeline_README.md) | Full pipeline workflow and stage-by-stage reference |
| [docs/curation_README.md](docs/curation_README.md) | YAML patch format and operations reference |
| [docs/python-code-patterns.md](docs/python-code-patterns.md) | Pydantic Fields pattern and base schema config |
| [docs/wi2_design_proposal.md](docs/wi2_design_proposal.md) | Original schema spec (slightly outdated; cross-reference against current models) |
| [docs/db_summary.md](docs/db_summary.md) | Snapshot of current row counts and coverage |
| [CLAUDE.md](CLAUDE.md) | Agent instructions, gotchas, command quick-reference |
