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
make export-production-db     # Export production SQLite for iOS app
make publish-db               # Dry-run publish to R2 (preview only)
make publish-db-commit        # Upload production DB + manifest to R2
python scripts/describe_db.py # Database schema + row counts
```

IMPORTANT: Always run `make format && make lint && make test` before committing.

## Architecture

```
MANIFEST -> FETCH -> REDUCE -> EXTRACT -> NORMALIZE -> RESOLVE -> STORE
```

- **Models**: `src/drift/models/` (SQLAlchemy 2.0 ORM)
- **Pipeline**: `src/drift/pipeline/` (scraping, reduction, extraction, normalization, resolution)
- **Pydantic schemas**: `src/drift/curation.py`, `src/drift/pipeline/extraction/schemas.py`, `src/drift/pipeline/fetching/schemas.py`
- **Resolution helpers**: `src/drift/resolution/aliases.py` (`lookup_entity` shared by curation + pipeline)
- **Scripts**: `scripts/` (CLI entry points, called via Makefile)
- **Curation**: `src/drift/curation.py` (YAML patch applier), `data/patches/` (numbered YAML patches)
- **Database**: `data/drift.db` (SQLite, source of truth)
- **Production DB**: `data/production/drift.db` (stripped copy for iOS app)
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

- `docs/engineering_overview.md` -- ballistics domain primer + engineering glossary (read before BC, DOPE, or solver work)
- `docs/pipeline_README.md` -- pipeline workflow and stage documentation
- `docs/curation_README.md` -- YAML patch format and operations reference
- `docs/wi2_design_proposal.md` -- original schema spec (slightly outdated; cross-reference against current models)
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

## Production Export

`scripts/export_production_db.py` creates `data/production/drift.db` — a stripped-down copy of `drift.db` for the iOS app. Drops pipeline-only tables (`alembic_version`, `bullet_bc_source`), removes pipeline metadata columns (`data_source`, `is_locked`, `extraction_confidence`, etc.), filters out bad records (zero-MV, weight-mismatched, bogus-diameter), and VACUUMs.

```bash
make export-production-db                              # Default: data/production/drift.db
python scripts/export_production_db.py -o path.db      # Custom output path
```

Re-run after any data changes (curation patches, pipeline store, etc.) to keep the production DB current.

## OTA Publish

`scripts/publish_db.py` uploads `data/production/drift.db` + `manifest.json` to Cloudflare R2 (`data.driftballistics.com`). Validates primary key stability against the previous published version.

```bash
make publish-db CHANGELOG="Added 47 Berger bullets"          # Dry-run preview
make publish-db-commit CHANGELOG="Added 47 Berger bullets"   # Upload to R2
```

Requires `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL` in `.env`. Install deps: `pip install -e '.[publish]'`.

## TODO.md — Tech Debt Backlog

`TODO.md` in the project root is a lightweight backlog for tech debt, engineering improvements, and issues discovered during work. Features and large items go in Linear.

When you discover an issue, improvement opportunity, or tech debt during your work:
- Append it to the appropriate section in `TODO.md`
- Format: `- [ ] Short description — context (source: agent/human, YYYY-MM-DD)`
- Don't duplicate items already listed
- If an item grows beyond a quick fix (>1 hour), it should move to Linear. Notify the user about these.

## Product & Design Hub

`product/` (symlink → iCloud) is the product management, design, and research hub for Drift. Read relevant files here when working on product-adjacent tasks.

Key files and directories:
- `product/README.md` — hub overview and orientation
- `product/current-app-state.md` — current state of the iOS app
- `product/strategy/` — roadmap, product themes, monetization, v1 requirements
- `product/product design/` — feature specs, design tokens, UX flows (ammo step, profile creation, gear identity)
- `product/research/` — competitive analysis, user research, ballistics engine research, brand positioning
- `product/engineering/` — iOS package design, services API, OTA data, design system, WI2 spec
- `product/ops/` — Linear agent guide
- `product/brand assets/` — SVG logos, wordmarks, rifle silhouettes, visual identity
- `product/agent_prompts/` — reusable prompts for specific implementation tasks
- `product/data-pipeline/` — early pipeline research JSONs (historical, mostly superseded by DB)

## iOS App Repository

`ios/` (symlink → `/Users/brianbolze/Development/ios/Drift/`) is the Drift iOS app (SwiftUI). When working in this backend repo, treat `ios/` as **read-only** — use it for reference only, never edit or create files under it.

Key reference files:
- `ios/CLAUDE.md` — iOS-specific agent instructions
- `ios/agent_docs/` — architecture, domain primer, file map, SwiftUI patterns, known issues
- `ios/docs/` — feature specs, design system, implemented features, engineering overview
- `ios/current-app-state.md` — current iOS app state
- `ios/Drift/` — SwiftUI source (Views, Models, Services, DesignSystem)

## Search Tips

- For backend work, scope searches to `src/`, `scripts/`, `tests/`, `data/`, `docs/` — `ios/` and `product/` are large external directories that will pollute results if searched broadly
- `data/pipeline/` is generated cache, not source code — rarely useful to read directly
- Prefer searching `src/` over repo root for Python symbol lookups

## User Preferences

- Concise communication, no fluff
- Senior engineer level -- don't over-explain basics
- Prefer direct action over lengthy explanation
