# Data Curation

YAML patches in [`data/patches/`](../data/patches/) are how humans put data into Drift. They handle everything the pipeline can't: missing bullets, BC corrections, fuzzy-match aliases, mislink fixes, deletes.

## Mental Model

Curation is the manual sibling of the pipeline. They write to the same database with the same name resolution rules, but solve different problems:

| Use the pipeline when... | Use a curation patch when... |
|---|---|
| The data is on a manufacturer page you can scrape | The data is only in a PDF, load manual, or third-party source |
| You want to add many entities of the same kind | You're fixing a small number of records by hand |
| The extraction will be high-confidence | The pipeline got it wrong and needs a manual override |
| | You're adding aliases (`SMK` → `MatchKing`) so the pipeline matches better next time |
| | You're deleting duplicates or repairing FK links |

**Two invariants** make patches safe to keep around forever:

1. **Idempotent** — every `create_*` checks if the record already exists (by SKU first, then `(manufacturer_id, lower(name))`); already-present records are skipped, not duplicated. Re-running the full patch directory is always safe.
2. **Locked on write** — all created records get `data_source = "manual"` and `is_locked = 1`. The pipeline store will never overwrite them. If you later realize the curated value was wrong, you have to fix it with another patch.

**Patches are numbered** (`001_`, `002_`, ...) and applied in order. Once committed, they live in version control as a permanent audit trail of every manual data decision. Don't edit a patch that's already been applied — write a new one.

---

## Quick Start

```bash
# 1. Create a new numbered patch file
$EDITOR data/patches/034_my_change.yaml

# 2. Preview (validates schema + shows what would happen, no DB writes)
make curate

# 3. Apply
make curate-commit

# 4. Re-run the production export so the iOS app picks up the change
make export-production-db
```

Single-patch mode (useful while iterating on a new patch):

```bash
python scripts/curate.py --patch 034_my_change            # dry-run
python scripts/curate.py --patch 034_my_change --commit   # apply
```

---

## File Format

Every patch is a YAML file with two top-level keys:

```yaml
patch:
  id: "034_short_descriptive_id"      # Must match filename (without .yaml). Pattern: NNN_lowercase_snake
  author: "Brian Bolze"               # or "agent"
  date: "2026-04-22"                  # YYYY-MM-DD
  description: "One-line summary."    # Up to 500 chars; longer notes go in inline YAML comments

operations:
  - action: <op_name>
    # ... fields specific to this op
  - action: <op_name>
    # ... another op
```

**Naming convention**: `NNN_lowercase_snake_with_meaningful_suffix.yaml`. The numeric prefix orders application; the suffix tells reviewers what's inside at a glance. Examples: `015_black_hills_cartridges.yaml`, `024_cartridge_bc_and_bullet_fixes.yaml`.

**Validation is strict**: the file is parsed against [`PatchFile`](../src/drift/curation.py) (Pydantic). Validation errors abort the entire run before any DB writes — fix the schema error and re-run.

---

## Operations Reference

Ten operations, grouped by intent. All schemas live in [`src/drift/curation.py`](../src/drift/curation.py).

### Create operations

#### `create_caliber`

Add a new caliber (e.g., a recently introduced cartridge family). Most calibers are seeded; you'll rarely need this.

| Field | Required | Range / type |
|---|---|---|
| `name` | yes | str (1–255) |
| `bullet_diameter_inches` | yes | 0.172–0.700 |
| `alt_names` | no | list of str |
| `case_length_inches` | no | 0.5–5.0 |
| `coal_inches` | no | 0.5–6.0 |
| `max_pressure_psi` | no | 10000–100000 |
| `rim_type` | no | str |
| `action_length` | no | str |
| `year_introduced` | no | 1800–2030 |
| `is_common_lr` | no | bool, default false |
| `source_url` | no | str (≤500) |

**Idempotency**: skipped if a caliber with the same `lower(name)` exists.

#### `create_bullet`

Add a new component bullet. Also creates one or two `BulletBCSource` rows (one per BC value provided).

| Field | Required | Range / type |
|---|---|---|
| `manufacturer` | yes | str — resolved via alias lookup |
| `name` | yes | str (1–255) |
| `weight_grains` | yes | 15–750 |
| `bullet_diameter_inches` | yes | 0.172–0.510 |
| `sku` | no | str (≤100) |
| `bc_g1`, `bc_g7` | no | 0.05–1.2 |
| `length_inches` | no | 0.2–3.0 (bullet length, not OAL) |
| `sectional_density` | no | 0.05–0.500 |
| `base_type` | no | `boat_tail`, `flat_base`, `rebated_boat_tail`, `hybrid` |
| `tip_type` | no | `polymer_tip`, `hollow_point`, `open_tip_match`, `fmj`, `soft_point`, `ballistic_tip`, `meplat` |
| `construction` | no | str (free text — e.g., `lead_core`, `bonded`, `monolithic`) |
| `is_lead_free` | no | bool, default false |
| `type_tags` | no | list of: `match`, `hunting`, `target`, `varmint`, `long_range`, `tactical`, `plinking` |
| `used_for` | no | list of: `competition`, `hunting_deer`, `hunting_elk`, `hunting_varmint`, `long_range`, `precision`, `self_defense`, `plinking` |
| `product_line` | no | str (≤100) — the product family (e.g., `MatchKing`, `ELD-X`) |
| `source_url` | no | str (≤500) |
| `bc_source` | no | default `"manufacturer"` — provenance tag for the auto-created BC source rows |
| `bc_source_methodology` | no | str — e.g., `"published"`, `"doppler_radar"` |
| `bc_source_notes` | no | str |

**Idempotency**: skipped if a bullet with the same SKU exists, or (lacking SKU) if `(manufacturer_id, lower(name))` matches.

**Example** (from [`001_sierra_matchking_30cal.yaml`](../data/patches/001_sierra_matchking_30cal.yaml)):

```yaml
- action: create_bullet
  manufacturer: "Sierra Bullets"
  name: "30 CAL 150 GR HPBT MATCHKING (SMK)"
  sku: "2190"
  weight_grains: 150.0
  bullet_diameter_inches: 0.308
  bc_g1: 0.417
  bc_g7: 0.199
  base_type: "boat_tail"
  tip_type: "hollow_point"
  construction: "lead_core"
  type_tags: ["match"]
  used_for: ["competition", "precision"]
  product_line: "MatchKing"
  source_url: "https://sierrabullets.com/30-cal-150-gr-hpbt-matchking-smk/"
  bc_source: "manufacturer"
  bc_source_methodology: "published"
  bc_source_notes: "Sierra product page, March 2026"
```

#### `create_cartridge`

Add a factory-loaded cartridge. Requires the bullet it uses to already exist (create the bullet earlier in the same patch if needed — operations within a patch run in order).

| Field | Required | Range / type |
|---|---|---|
| `manufacturer` | yes | str — resolved via alias lookup |
| `name` | yes | str (1–500) |
| `caliber` | yes | str — resolved via alias lookup |
| `bullet` | yes | str — bullet name; resolved against `bullet_manufacturer` (or `manufacturer` if unset) |
| `bullet_weight_grains` | yes | 15–750 |
| `muzzle_velocity_fps` | yes | 400–4000 |
| `bullet_manufacturer` | no | str — defaults to `manufacturer` (use when a cartridge wraps another company's bullet) |
| `sku` | no | str (≤100) |
| `bc_g1`, `bc_g7` | no | 0.05–1.2 — published BC for *this loading*, not the bullet's free-flight BC |
| `test_barrel_length_inches` | no | 10–34 |
| `product_line` | no | str |
| `round_count` | no | int (typically 20) |
| `source_url` | no | str (≤500) |

The created cartridge gets `bullet_match_confidence = 1.0`, `bullet_match_method = "manual"`.

**Idempotency**: same SKU → skip; else `(manufacturer_id, lower(name))` → skip.

#### `create_rifle`

Add a factory rifle model.

| Field | Required | Range / type |
|---|---|---|
| `manufacturer` | yes | str |
| `model` | yes | str (1–255) |
| `chamber` | yes | str — resolved via alias lookup (note: chamber, not caliber — `.223 Wylde`, `5.56 NATO`) |
| `barrel_length_inches` | no | 10–34 |
| `twist_rate` | no | str (e.g., `"1:8"`) |
| `weight_lbs` | no | 2–20 |
| `barrel_material`, `barrel_finish`, `model_family` | no | str |
| `source_url` | no | str (≤500) |

**Idempotency**: `(manufacturer_id, lower(model))` → skip.

### Update operations

#### `update_bullet` / `update_cartridge`

Mutate fields on an existing record. Identified by `(manufacturer, name)`. The `set` map lists fields to change.

```yaml
- action: update_bullet
  manufacturer: "Hornady"
  name: "6.5mm .264 140 gr ELD® Match"
  set:
    bc_g7: 0.326
    is_lead_free: false
```

**Allowlisted fields** (validated by Pydantic; anything else fails with `Cannot update fields: [...]`):

- **Bullet**: `name`, `alt_names`, `sku`, `weight_grains`, `bullet_diameter_inches`, `bc_g1_published`, `bc_g7_published`, `bc_g1_estimated`, `bc_g7_estimated`, `length_inches`, `sectional_density`, `base_type`, `tip_type`, `construction`, `type_tags`, `used_for`, `is_lead_free`, `product_line`, `source_url`, `overall_popularity_rank`, `lr_popularity_rank`
- **Cartridge**: `bc_g1`, `bc_g7`, `bullet`, `bullet_manufacturer`, `bullet_length_inches`, `bullet_weight_grains`, `muzzle_velocity_fps`, `test_barrel_length_inches`, `round_count`, `product_line`, `source_url`, `sku`, `overall_popularity_rank`, `lr_popularity_rank`

**Re-linking a cartridge to a different bullet**: set `bullet` (and optionally `bullet_manufacturer` if the new bullet belongs to another company). The patch will update `bullet_id` and tag the FK with `bullet_match_confidence = 1.0`, `bullet_match_method = "manual"`. If the FK doesn't actually change, those metadata fields are left alone — so no-op relinks won't churn audit data.

**No-op detection**: if every field in `set` already matches, the op is reported as `SKIP ... (already up to date)` — not counted as an update.

**Errors**: if the target record doesn't exist, the op fails with `Bullet not found: <name>` (and is rolled back; see *Failure handling* below).

#### Updating BC values — the right way

`update_bullet` writes `bc_g1_published` / `bc_g7_published` directly on the bullet row. **It does not create a `BulletBCSource` audit row.** If you're correcting an existing BC, that's fine. If you're adding a *new* BC observation (e.g., from Applied Ballistics doppler data), use `add_bc_source` instead — it preserves multi-source history.

### Delete operations

#### `delete_bullet`

Removes a bullet (and cascades to its `BulletBCSource` rows). **Refuses if any cartridge references the bullet** — re-link cartridges first, then delete.

| Field | Required | Description |
|---|---|---|
| `manufacturer` | yes | str |
| `name` | yes | str |
| `id` | no | UUID — required when multiple bullets share the same name |
| `reason` | yes | str (1–500) — recorded in the patch log; explain why this is being deleted |

#### `delete_cartridge`

Same shape as `delete_bullet`. No FK guard (nothing references cartridges in the dev schema).

```yaml
- action: delete_cartridge
  manufacturer: "Federal"
  name: "Premium 308 Win 168gr Sierra MatchKing"
  reason: "Duplicate of '308 Winchester 168 GR Gold Medal Match' (id=abc123); kept the canonical one"
```

### BC sources

#### `add_bc_source`

Append a `BulletBCSource` row — additional BC observation for a bullet from a different source.

| Field | Required | Range / type |
|---|---|---|
| `manufacturer` | yes | str |
| `bullet_name` | yes | str — resolved against the manufacturer |
| `bc_type` | yes | `g1` or `g7` |
| `bc_value` | yes | 0.05–1.2 |
| `source` | no | default `"manufacturer"`. Common values: `manufacturer`, `cartridge_page`, `applied_ballistics`, `doppler_radar`, `independent_test`, `estimated` |
| `source_url` | no | str (≤500) |
| `source_methodology` | no | str |
| `notes` | no | str |

**Idempotency**: skipped if a row with the same `(bullet_id, bc_type, bc_value, source)` already exists.

### Aliases

#### `add_entity_alias`

Teach the resolver that `<alias>` means `<entity_name>`. After this runs, both the curation tooling and the pipeline resolver will hit the deterministic alias path instead of relying on fuzzy matching.

| Field | Required | Description |
|---|---|---|
| `entity_type` | yes | One of: `manufacturer`, `caliber`, `chamber`, `bullet`, `cartridge`, `bullet_product_line` |
| `entity_name` | yes | The canonical name to alias *to* |
| `alias` | yes | The new name to recognize (≤255) |
| `alias_type` | yes | Free text classification (≤50). Conventional values: `abbreviation`, `alternate_name`, `full_name`, `predecessor`, `informal` |
| `manufacturer` | conditional | **Required for `bullet_product_line`** to disambiguate (Hornady's `Match` ≠ Federal's `Match`) |

**Example** (from [`014_bullet_product_line_aliases.yaml`](../data/patches/014_bullet_product_line_aliases.yaml)):

```yaml
- action: add_entity_alias
  entity_type: bullet_product_line
  entity_name: MatchKing
  manufacturer: Sierra Bullets
  alias: SMK
  alias_type: abbreviation

- action: add_entity_alias
  entity_type: bullet_product_line
  entity_name: ELD Match
  manufacturer: Hornady
  alias: ELDM
  alias_type: abbreviation
```

**Idempotency**: skipped if `(entity_type, entity_id, alias)` already exists.

**When to add an alias**: whenever you see the pipeline store flag a `fuzzy_name` match in the report and you'd like that match to be deterministic next time. The store also surfaces alias *suggestions* in `data/pipeline/store_report.json` — these are good candidates to formalize in a patch.

---

## Name Resolution

Every patch field that takes a name string (`manufacturer`, `caliber`, `chamber`, `bullet`, `entity_name`) goes through [`drift.resolution.aliases.lookup_entity()`](../src/drift/resolution/aliases.py) — the **same resolver the pipeline uses**. So if a name works in one place it works in the other.

Lookup order (deterministic; no fuzzy matching):

1. Exact match on canonical `name` (case-insensitive)
2. Exact match in `alt_names` JSON array on the entity row
3. Exact match in `EntityAlias.alias` (created by `add_entity_alias`)

If all three miss, the operation fails with `<entity_type> not found: <name>`. **The fix is almost always to add an alias** rather than rename the canonical record.

For `bullet` lookups, resolution is scoped by `manufacturer_id` — so `"Partition"` resolves correctly against Nosler even if Federal also stocks a "Partition" loading.

---

## Failure Handling

Each operation runs inside its own SAVEPOINT ([`apply_patch` in curation.py](../src/drift/curation.py)). If op #5 fails:

- The savepoint for op #5 rolls back (no partial state from that op)
- Ops #1–4 stay applied; ops #6+ continue
- The error is logged with op index and reason
- The final summary shows `errors: N` separate from `created/updated/skipped`

This means **a typo in one op doesn't block the rest of the patch**, but you should still treat any nonzero error count as a failure to investigate before moving on.

**Validation errors** are different — they happen *before* any op runs (Pydantic schema-checks the whole file). The script exits non-zero with the exact field that failed validation.

**Dry-run safety**: even without `--commit`, the entire patch executes inside a transaction; the rollback happens at the end. So dry-run runs *will* hit `_resolve_*` lookups, savepoints, and `flush()` calls — but nothing persists. This means a dry-run reliably catches "bullet not found" or "alias not found" errors without any DB risk.

---

## Cookbook

Common patterns drawn from the existing patch corpus.

### Add a bullet that the pipeline can't extract

For SPAs, PDFs, or sites the reducer can't handle.

```yaml
- action: create_bullet
  manufacturer: Norma
  name: "Norma Golden Target 6.5mm 130gr"
  weight_grains: 130
  bullet_diameter_inches: 0.264
  bc_g1: 0.595
  bc_g7: 0.300
  product_line: "Golden Target"
  source_url: "https://www.norma-ammunition.com/..."
  bc_source: manufacturer
  bc_source_notes: "Pulled from Norma JSON-LD; SPA reducer can't parse the page body."
```

### Fix a wrong BC value

Use `update_bullet` for the canonical value; `add_bc_source` if you also want to record where the corrected value came from.

```yaml
- action: update_bullet
  manufacturer: Sako
  name: "TRG Precision .308 175gr"
  set:
    bc_g1: 0.467
    weight_grains: 175.0     # was 174 — caliber spec rounding error
```

### Re-link a cartridge to the right bullet

Common when the resolver fuzzy-matched to a sibling weight or wrong manufacturer.

```yaml
- action: update_cartridge
  manufacturer: Winchester
  name: "Match 308 Win 168gr BTHP"
  set:
    bullet: "30 Cal .308 168 gr Sierra MatchKing"
    bullet_manufacturer: "Sierra Bullets"
```

### Add an alias so the next pipeline run matches deterministically

```yaml
- action: add_entity_alias
  entity_type: manufacturer
  entity_name: "Hornady"
  alias: "Hornady Manufacturing"
  alias_type: full_name
```

### Delete a duplicate

Always re-link any cartridges first, then delete:

```yaml
- action: update_cartridge
  manufacturer: "Federal"
  name: "Gold Medal 308 168gr SMK"
  set:
    bullet: "30 Cal .308 168 gr Sierra MatchKing"   # the one you're keeping

- action: delete_bullet
  manufacturer: "Federal"
  name: "Sierra MatchKing 168gr (Federal repackage)"
  reason: "Duplicate of canonical Sierra entry; kept Sierra's bullet, re-linked Federal cartridge above."
```

### Bulk-fix data quality across many records

Use one patch with many ops. The savepoint-per-op model means partial success is fine. See [`002_data_qa_fixes.yaml`](../data/patches/002_data_qa_fixes.yaml) and [`018_data_qa_fixes.yaml`](../data/patches/018_data_qa_fixes.yaml) for examples.

---

## Interaction with the Pipeline

A few invariants worth keeping in mind when both workflows are in use:

- **`is_locked = 1` is sticky**. The pipeline store explicitly checks `is_locked` before any update — locked records are skipped with action `skipped_locked`. So once curated, a record stays curated.
- **`data_source` tracks origin**. `manual` (curation), `pipeline` (LLM extraction), `cowork` (CoWork-tagged extraction). Useful for `WHERE` clauses when auditing.
- **Curation runs in the dev DB only**. The production DB is built downstream by [`scripts/export_production_db.py`](../scripts/export_production_db.py), which strips `is_locked` and `data_source` before VACUUM-ing. After every curation run, re-export and re-publish to ship the change.
- **Aliases benefit both sides**. `add_entity_alias` immediately improves both pipeline resolution (next run) and future curation patches (which use the same lookup).

---

## After Applying a Patch

```bash
make curate-commit                            # apply
make export-production-db                     # rebuild data/production/drift.db
make publish-db CHANGELOG="..."               # dry-run preview
make publish-db-commit CHANGELOG="..."        # ship to R2
```

Don't forget the export step — the iOS app reads from the production DB, not `drift.db`.

---

## Reference

| Command | Behavior |
|---|---|
| `make curate` | Dry-run all patches in `data/patches/` |
| `make curate-commit` | Apply all patches |
| `python scripts/curate.py --patch <id>` | Dry-run a single patch (id without `.yaml`) |
| `python scripts/curate.py --patch <id> --commit` | Apply a single patch |

| Path | Purpose |
|---|---|
| [`src/drift/curation.py`](../src/drift/curation.py) | Pydantic schemas, name resolution, operation handlers |
| [`scripts/curate.py`](../scripts/curate.py) | CLI runner |
| [`src/drift/resolution/aliases.py`](../src/drift/resolution/aliases.py) | Shared name lookup (used by both curation and pipeline) |
| [`data/patches/`](../data/patches/) | Numbered YAML patches (the audit trail) |
| [`docs/pipeline_README.md`](pipeline_README.md) | The automated counterpart workflow |
