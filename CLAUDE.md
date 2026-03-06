# Drift Ballistics Backend

Data pipeline + SQLite bundled DB for a precision ballistics iOS app.
Offline-first: LLM extraction at ingestion time, no inference at query time.

## Commands

```bash
make test                     # Run full test suite
make lint                     # Check style (black, isort, flake8)
make format                   # Auto-format code
make curate                   # Preview curation patches (dry-run)
make curate-commit            # Apply curation patches to database
make pipeline-status          # Pipeline execution status
make pipeline-store           # Dry-run resolve (preview DB changes)
make pipeline-store-commit    # Commit resolved data to DB
python scripts/describe_db.py # Database schema + row counts
```

IMPORTANT: Always run `make format && make lint && make test` before committing.

## Architecture

```
MANIFEST -> FETCH -> REDUCE -> EXTRACT -> RESOLVE -> STORE
```

- **Models**: `src/drift/models/` (SQLAlchemy 2.0 ORM)
- **Schemas**: `src/drift/schemas/` (Pydantic 2.0 validation)
- **Pipeline**: `src/drift/pipeline/` (scraping, extraction, resolution)
- **Scripts**: `scripts/` (CLI entry points, called via Makefile)
- **Curation**: `src/drift/curation.py` (YAML patch applier), `data/patches/` (numbered YAML patches)
- **Database**: `data/drift.db` (SQLite, source of truth)
- **Pipeline cache**: `data/pipeline/{fetched,reduced,extracted,review,batches}/`

## Code Style

- Black, 120-char line length. isort with black profile.
- Python 3.11+, SQLAlchemy 2.0, Pydantic 2.0
- Use `Session.scalars()` not `Session.execute().scalars()`
- Pydantic schemas use localized `Fields` class pattern (see `docs/python-code-patterns.md`)

## Domain Gotchas

- **Bullet is canonical** -- Cartridge and UserLoadProfile reference Bullet, not the reverse.
- **bullet_diameter_inches is a FLOAT, not an FK** -- it's a physical measurement. Caliber compatibility is derived: `bullet.bullet_diameter_inches == caliber.bullet_diameter_inches`.
- **Chamber != Caliber** -- .223 Wylde is a chamber (rifle property), not a cartridge/caliber.
- **Manufacturer names vary** -- "Hornady Inc" vs "Hornady Inc." vs "Hornady Manufacturing". Always use EntityAlias table for normalization, never raw string matching.
- **BC values**: G1 range 0.1-0.8, G7 range 0.05-0.45. Values outside these are likely extraction errors.
- **BulletBCSource** provides audit trail for BC observations across sources. Don't store BCs directly on Bullet without also creating a BulletBCSource record.

## Key References

Read these docs when working in specific areas:

- `docs/engineering_overview.md` -- ballistics domain primer (read before BC, DOPE, or solver work)
- `docs/wi2_design_proposal.md` -- full schema spec (read when modifying models), albeit slightly outdated
- `docs/pipeline_working_notes.md` -- pipeline pain points and current state (read before pipeline debugging)
- `docs/pipeline_README.md` -- pipeline workflow and stage documentation
- `docs/python-code-patterns.md` -- Pydantic Fields pattern, base schema config

## Pipeline Quick Reference

```bash
# Extraction (provider auto-detected from env)
make pipeline-extract                           # Default
make pipeline-extract PIPELINE_MODEL=claude-sonnet-4-6  # Specific model
make pipeline-extract PIPELINE_LIMIT=5          # Limit for testing

# Store workflow: ALWAYS dry-run first
make pipeline-store           # Preview
make pipeline-store-commit    # Commit
```

Env vars: `PIPELINE_PROVIDER` (anthropic|openai), `PIPELINE_MODEL`, `PIPELINE_LIMIT`

## Data Curation Quick Reference

YAML patches in `data/patches/` for manual data fixes (missing bullets, BC corrections, aliases). Replaces one-off scripts.

```bash
make curate           # Dry-run preview
make curate-commit    # Write to DB
```

- Patches are numbered (`001_`, `002_`, ...) and applied in order
- All created records get `data_source="manual"` + `is_locked=True` automatically
- Operations: `create_bullet`, `create_cartridge`, `create_rifle`, `update_bullet`, `update_cartridge`, `add_bc_source`, `add_entity_alias`
- Name resolution uses EntityAlias table (same as pipeline)
- Idempotent: safe to re-run — existing records are skipped
- See `curation_plan.md` for full design and YAML format spec

## TODO.md — Tech Debt Backlog

`TODO.md` in the project root is a lightweight backlog for tech debt, engineering improvements, and issues discovered during work. Features and large items go in Linear.

When you discover an issue, improvement opportunity, or tech debt during your work:
- Append it to the appropriate section in `TODO.md`
- Format: `- [ ] Short description — context (source: agent/human, YYYY-MM-DD)`
- Don't duplicate items already listed
- If an item grows beyond a quick fix (>1 hour), it should move to Linear. Notify the user about these.

## User Preferences

- Concise communication, no fluff
- Senior engineer level -- don't over-explain basics
- Prefer direct action over lengthy explanation
