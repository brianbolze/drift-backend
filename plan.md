# Plan: Collect G1/G7 BC and Bullet Specs for Cartridges

## Motivation

Cartridge product pages almost always republish the bullet's G1/G7 ballistic coefficients, weight, and length. Currently the pipeline only extracts BC data for `bullet` entity types and ignores it on cartridge pages. Collecting this from cartridge pages provides:

1. **Validation layer** — cross-check against the bullet's published values
2. **Bullet matching signal** — BC and weight exact-match help disambiguate which bullet a cartridge uses
3. **Coverage gap-fill** — if a bullet was ingested without BC data, the cartridge page can supply it

## Changes Required

### 1. DB Model: Add 4 columns to `Cartridge` (`src/drift/models/cartridge.py`)

Four new nullable float columns:

```python
# Bullet BC values as published on the cartridge product page
bc_g1: Mapped[float | None] = mapped_column(Float, nullable=True)
bc_g7: Mapped[float | None] = mapped_column(Float, nullable=True)

# Bullet physical specs as published on the cartridge product page
# (bullet_weight_grains already exists as a non-nullable column for the denormalized value)
bullet_length_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
```

Wait — `bullet_weight_grains` already exists as a non-nullable column on `Cartridge` (line 28). So the 4 new columns are:

- `bc_g1` (Float, nullable) — manufacturer-published G1 BC from the cartridge page
- `bc_g7` (Float, nullable) — manufacturer-published G7 BC from the cartridge page
- `bullet_length_inches` (Float, nullable) — bullet projectile length (NOT cartridge OAL)

That's only 3 new DB columns. `bullet_weight_grains` already exists — no schema change needed for it. But it does need to start flowing through extraction+resolution as a matching signal.

### 2. Alembic Migration

New migration file:

```python
op.add_column("cartridge", sa.Column("bc_g1", sa.Float(), nullable=True))
op.add_column("cartridge", sa.Column("bc_g7", sa.Float(), nullable=True))
op.add_column("cartridge", sa.Column("bullet_length_inches", sa.Float(), nullable=True))
```

### 3. Extraction Schema: Add BC + bullet_length fields to `ExtractedCartridge` (`src/drift/pipeline/extraction/schemas.py`)

```python
class ExtractedCartridge(BaseModel):
    ...  # existing fields
    bc_g1: ExtractedValue[float | None]
    bc_g7: ExtractedValue[float | None]
    bullet_length_inches: ExtractedValue[float | None]
```

(`bullet_weight_grains` already exists on `ExtractedCartridge`)

### 4. Extraction Engine: Update cartridge prompt and BC extraction (`src/drift/pipeline/extraction/engine.py`)

**4a. Update `CARTRIDGE_SCHEMA` prompt** — add `bc_g1`, `bc_g7`, and `bullet_length_inches` fields to the JSON template. Include the same OAL vs bullet-length disambiguation note from the bullet prompt.

**4b. Extend BC extraction to cartridges** — in `parse_response()`, change the `if entity_type == "bullet":` block to also handle `"cartridge"`:

```python
if entity_type in ("bullet", "cartridge"):
    for raw in raw_entities:
        bc_sources.extend(_extract_bc_sources(raw, entity_type=entity_type))
```

Update `_extract_bc_sources()` to accept an optional `entity_type` param. For cartridges, use the `bullet_name` field (if present) as the `bullet_name` on the `ExtractedBCSource`, falling back to the cartridge `name`. Set `source="cartridge_page"` (distinct from `"manufacturer"` which means the bullet's own page).

### 5. Entity Resolver: Use BC + weight as bullet-matching confidence signals (`src/drift/pipeline/resolution/resolver.py`)

In `resolve()` for `entity_type == "cartridge"`, after resolving the bullet FK via name/weight/diameter, use extracted values as confirmation signals:

- **Exact `bullet_weight_grains` match** (±0.5gr tolerance already used in composite key) → boost confidence
- **Exact `bc_g1` match** — if the matched bullet has `bc_g1_published` and it exactly equals the extracted cartridge `bc_g1` → boost confidence
- **Exact `bc_g7` match** — same for G7
- Disagreement on BC adds a warning to `resolution.warnings` but does NOT disqualify the match

This logic goes in the cartridge branch of `resolve()`, after `match_bullet()` returns a candidate. The confidence boost is additive (e.g., +0.05 per exact-matching signal), capped at 1.0.

### 6. Pipeline Store: Persist cartridge BC values (`scripts/pipeline_store.py`)

**6a. Update `_make_cartridge()`** to set the new fields:

```python
bc_g1=_safe_float(_get_value(entity, "bc_g1")),
bc_g7=_safe_float(_get_value(entity, "bc_g7")),
bullet_length_inches=_safe_float(_get_value(entity, "bullet_length_inches")),
```

**6b. Create `BulletBCSource` rows from cartridge-sourced BC data.** When a cartridge has BC values and a resolved `bullet_id`, create `BulletBCSource` entries with:
- `bullet_id` = the resolved bullet
- `source` = `"cartridge_page"`
- `source_url` = the cartridge page URL
- `notes` = cartridge name/SKU for traceability

### 7. `scripts/describe_db.py`: Update cartridge table display

Add BC columns (`bc_g1`, `bc_g7`) to the Full Cartridge List table so they appear in `docs/db_summary.md`.

### 8. Tests

**8a. `tests/test_models.py`** — update `_seed()` to include `bc_g1`, `bc_g7`, `bullet_length_inches` on the test Cartridge; verify round-trip.

**8b. `tests/pipeline/test_pipeline_components.py`**:
- Update `TestExtractionSchemas.test_extracted_cartridge` to include `bc_g1`, `bc_g7`, `bullet_length_inches`
- Add test in `TestExtractBCSources` verifying cartridge entities produce BC sources with `source="cartridge_page"` and `bullet_name` from the cartridge's `bullet_name` field

**8c. `tests/pipeline/test_batch_extraction.py`**:
- Add a `MINIMAL_CARTRIDGE` fixture with BC fields
- Add test that `parse_response("cartridge")` produces `bc_sources`

**8d. `tests/test_resolver.py`**:
- Add test verifying exact BC match boosts bullet match confidence
- Add test verifying exact weight match boosts confidence
- Add test verifying BC disagreement adds a warning but doesn't disqualify

## Files Changed

| File | Change |
|------|--------|
| `src/drift/models/cartridge.py` | Add `bc_g1`, `bc_g7`, `bullet_length_inches` columns |
| `alembic/versions/xxxx_add_bc_to_cartridge.py` | New migration (3 columns) |
| `src/drift/pipeline/extraction/schemas.py` | Add `bc_g1`, `bc_g7`, `bullet_length_inches` to `ExtractedCartridge` |
| `src/drift/pipeline/extraction/engine.py` | Update `CARTRIDGE_SCHEMA` prompt; extend BC extraction to cartridges |
| `src/drift/pipeline/resolution/resolver.py` | BC + weight exact-match confidence boost for bullet resolution |
| `scripts/pipeline_store.py` | Persist cartridge BC + bullet_length; create `BulletBCSource` rows from cartridge data |
| `scripts/describe_db.py` | Add BC columns to cartridge display table |
| `tests/test_models.py` | Cartridge BC fields in model smoke test |
| `tests/pipeline/test_pipeline_components.py` | Schema + BC extraction tests for cartridges |
| `tests/pipeline/test_batch_extraction.py` | Cartridge BC parsing tests |
| `tests/test_resolver.py` | BC/weight confidence boost tests |

## What This Does NOT Change

- **Bullet model** — no changes; bullet remains the canonical BC source of truth
- **`BulletBCSource` model** — no schema change; we add rows with `source="cartridge_page"`
- **Validation ranges** — BC range (0.05–1.2) already applies; `validate_ranges()` covers cartridge BC fields by field name. Add `bullet_length_inches` to `VALIDATION_RANGES` in config.py with the same range as `length_inches`.
- **Batch extraction** — no structural change; `BatchExtractor` delegates to `parse_response()` which handles the new fields automatically
- **`bullet_weight_grains`** — already exists on `Cartridge` model and `ExtractedCartridge`; no schema change needed, just use it in resolution
