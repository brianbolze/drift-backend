# Curation System — Implementation Plan

## Context

Manual data fixes (inserting missing bullets, correcting BCs, adding aliases) are currently done via one-off Python scripts. This doesn't scale — we have ~750 flagged bullets and ~200 flagged cartridges. We need a structured, idempotent, auditable system for data curation that's separate from Alembic (schema) and the pipeline (automated extraction).

## Approach

Numbered YAML patch files in `data/patches/`, applied by a single runner via `make curate` / `make curate-commit`. Pydantic validates each patch before any DB work. Idempotency via existence checks (no applied-patch tracking table). All created records get `data_source="manual"` and `is_locked=True` automatically.

## New Files

### 1. `src/drift/curation.py`

Single flat module containing both Pydantic schemas and applier logic. Promote to a package if/when it outgrows a single file.

**Schemas** — Pydantic models for YAML validation. Uses `Discriminator("action")` union for operation dispatch.

Operation types:
- `create_bullet` — creates Bullet + auto-generates BulletBCSource records from `bc_g1`/`bc_g7` fields
- `create_cartridge` — creates Cartridge, resolves caliber/bullet by name
- `create_rifle` — creates RifleModel, resolves chamber by name
- `update_bullet` — updates specific fields on existing bullet (allowlisted keys only)
- `update_cartridge` — updates specific fields on existing cartridge (allowlisted keys only)
- `add_bc_source` — adds BulletBCSource to existing bullet
- `add_entity_alias` — adds EntityAlias record

Validation: Pydantic type checks and DB constraints handle field validation. No separate controlled-vocab config layer — add later only if bad data becomes a problem.

Patch metadata: `id` (matches filename), `author`, `date`, `description`.

**Allowlisted update fields:**

`update_bullet`:
- `name`, `alt_names`, `sku`, `weight_grains`, `bullet_diameter_inches`
- `bc_g1_published`, `bc_g1_estimated`, `bc_g7_published`, `bc_g7_estimated`, `bc_source_notes`
- `length_inches`, `sectional_density`
- `type_tags`, `used_for`, `base_type`, `tip_type`, `construction`, `is_lead_free`
- `popularity_rank`, `source_url`

`update_cartridge`:
- `name`, `alt_names`, `sku`, `product_line`
- `bullet_weight_grains`, `bc_g1`, `bc_g7`, `bullet_length_inches`
- `muzzle_velocity_fps`, `test_barrel_length_inches`, `round_count`
- `popularity_rank`, `source_url`

Never updatable: `id`, `manufacturer_id`, `caliber_id`, `bullet_id`, `data_source`, `is_locked`, `created_at`, `updated_at`, `extraction_confidence`, `bullet_match_confidence`, `bullet_match_method`.

**Applier logic** — `discover_patches()`, `load_and_validate()`, `apply_patch()`.

- **Name resolution**: manufacturer, caliber, chamber, and bullet lookups query the `EntityAlias` table (not just the model's `name` field). Falls back to direct name match on the entity if no alias found. Case-insensitive.
- **Idempotency**: checks by `(manufacturer_id, name)` and optionally `sku` before creating.
- **BC source dedup**: checks `(bullet_id, bc_type, bc_value, source)` before adding.
- **Alias dedup**: catches `IntegrityError` from unique constraint.
- **Error handling**: savepoint per operation, skip-and-report on failure, continue to next op.
- **`session.flush()`** after each create so later operations in same patch can reference new records.
- **Patch ordering**: `discover_patches()` sorts by numeric filename prefix (lexicographic on zero-padded prefix).

Stats tracked: created, updated, skipped, errors — with detail messages.

### 2. `scripts/curate.py`

CLI entry point. Argparse with:
- No flags = dry-run (rollback at end)
- `--commit` = write to DB
- `--patch PATCH_ID` = apply single patch
- `--verbose` = per-operation detail

### 3. `data/patches/001_sierra_matchking_30cal.yaml`

Migration of the Sierra MatchKing script into first YAML patch. Three `create_bullet` operations for the 150gr, 155gr, 190gr .308 MatchKings.

### 4. `tests/test_curation.py`

Tests using `conftest.py` db fixture (in-memory SQLite). Coverage:
- Schema validation (valid/invalid YAML)
- Idempotency (create twice → skip second time)
- Name resolution (manufacturer lookup via EntityAlias, error on unknown)
- BC source auto-creation from `create_bullet`
- Update operations
- Dry-run mode (no records persisted)
- **Intra-patch forward references** (create bullet then create cartridge referencing it in same patch)
- **Partial failure** (op 2 of 3 fails → verify op 1 committed via savepoint, op 3 still runs)
- **Allowlist enforcement** (attempting to update `id` or `is_locked` → rejected)

## Modified Files

### 5. `pyproject.toml`

Add `pyyaml>=6.0` to main dependencies.

### 6. `Makefile`

Add `.PHONY: curate curate-commit` and two targets:

```makefile
curate:           ## Preview curation patches (dry-run)
curate-commit:    ## Apply curation patches to database
```

Add "Data Curation:" section to help output.

### 7. Delete `scripts/insert_sierra_matchking.py`

Replaced by `data/patches/001_sierra_matchking_30cal.yaml`. (Note: file is currently untracked — verify it was never committed before removing.)

## YAML Patch Format Example

```yaml
patch:
  id: "001_sierra_matchking_30cal"
  author: "Brian Bolze"
  date: "2026-03-06"
  description: "Add missing Sierra MatchKing 30 Cal bullets"

operations:
  - action: create_bullet
    manufacturer: "Sierra Bullets"
    name: "30 CAL 150 GR HPBT MATCHKING (SMK)"
    sku: "2190"
    weight_grains: 150.0
    bullet_diameter_inches: 0.308
    bc_g1: 0.417
    bc_g7: 0.199
    source_url: "https://sierrabullets.com/30-cal-150-gr-hpbt-matchking-smk/"
    base_type: "boat_tail"
    tip_type: "hollow_point"
    construction: "lead_core"
    type_tags: ["match"]
    used_for: ["competition", "precision"]
    bc_source: "manufacturer"
    bc_source_methodology: "published"
    bc_source_notes: "Sierra product page, March 2026"
```

## Key Design Decisions

1. **No applied-patch tracking table** — pure idempotent checks. Simpler, no migration needed, handles manual DB edits gracefully. Git log provides audit trail of when patches were added.
2. **Pydantic discriminated union on `action` field** — clean dispatch, each op validates independently, trivial to extend.
3. **`data_source="manual"` + `is_locked=True` set automatically** — every curated record is protected from pipeline overwrite.
4. **`session.flush()` after each create** — so later ops in same patch can reference newly created records.
5. **Allowlisted update fields** — prevents accidental overwrite of identity, provenance, and lock fields.
6. **Flat module** — single `src/drift/curation.py` file, not a package. Keeps complexity proportional to scope.
7. **No controlled-vocab config layer** — DB constraints + Pydantic types are sufficient validation. Add vocab validation later only if bad data becomes a real problem.
8. **Name resolution via EntityAlias** — consistent with project conventions, not just raw `name` field matching.

## Verification

1. `pip install -e ".[dev]"` to pick up pyyaml
2. `make format && make lint && make test` — all pass
3. `make curate` — dry-run shows 3 SKIPs for Sierra bullets (already in DB)
4. `make curate-commit` — commits, re-run shows all SKIPs (idempotent)
5. `make pipeline-store` — same results as before (753 flagged bullets, 12 skipped locked)
