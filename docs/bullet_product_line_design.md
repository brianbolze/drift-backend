# Bullet Product Line as First-Class Entity

**Status**: Phase 1-2 implemented, Phase 3 planned
**Date**: 2026-03-18 (updated)
**Authors**: Brian, Claude Agent
**Supersedes**: `docs/bullet_matching_design.md` (partially implemented — Tier 2 product-line matching exists, but product_line is still a bare string)

---

## 1. Motivation

Three problems converge on the same fix:

1. **iOS search aliases** — Users search "ELDM" or "SMK" and expect to find all ELD Match or MatchKing bullets. Currently zero bullet aliases exist. Per-bullet aliases (149 entries for initial coverage) don't scale; the abbreviation belongs to the *product line*, not any individual bullet.

2. **Cartridge→bullet resolution** — ~193 flagged cartridges, of which ~80 fail because the extracted `bullet_type` (e.g., "ELD-X", "TSX", "Fusion Soft Point") can't reliably match bullet names via string similarity. The resolver already has a Tier 2 product-line matching strategy, but it relies on normalizing extracted strings against the `bullet.product_line` VARCHAR — fragile, no alias support, no cross-manufacturer awareness.

3. **Product-line naming chaos** — The same product line appears differently across contexts: "ELD-X", "ELDX", "ELD‑X®", "Extremely Low Drag - eXpanding", "Hornady ELD-X". Currently each pipeline stage (extraction, normalization, resolution) handles this independently via regex and hardcoded maps.

**Core insight**: A product line is a real entity with a canonical identity, abbreviations, and variant spellings. Treating it as a string column forces every consumer to reinvent normalization.

---

## 2. Current State

### What exists

| Component | Status |
|---|---|
| `bullet.product_line` | VARCHAR(100), populated for 738/1,285 bullets (57%), 137 distinct values |
| `cartridge.product_line` | VARCHAR(255), populated for all 266 cartridges (ammo line, not bullet line) |
| `entity_alias` table | Supports `entity_type` in (manufacturer, caliber, chamber, bullet, cartridge). 40 caliber aliases, 0 bullet aliases |
| Resolver Tier 2 | `_normalize_product_line()` + match against `bullet.product_line` string. Confidence 0.93 (with weight) / 0.80 (without) |
| `_normalize_product_line()` | Strips trademarks, unicode dashes, manufacturer prefixes, generic suffixes. Extracts parenthetical abbreviations |
| Export script | Drops pipeline columns, doesn't touch `alt_names` or `entity_alias` for bullets |

### What's missing

- No way to alias "ELDM" → "ELD Match" → all Hornady ELD Match bullets
- No structured lookup for cartridge→bullet resolution (still fuzzy string matching)
- `alt_names` JSON on bullets is always NULL — never populated
- `entity_alias` doesn't support `bullet_product_line` as an entity type
- 547 bullets (43%) have NULL `product_line` — no backfill mechanism

### Flagged cartridge breakdown (193 total)

| Count | Root Cause | Would product_line entity help? |
|---|---|---|
| 53 | Product line exists, **wrong weight variant** in DB | **Yes** — structured match confirms product line, flags as "need weight variant" instead of generic failure |
| 27 | Product line exists, **wrong diameter** in DB | **Yes** — same as above |
| 47 | Product line **not in DB at all** (Fusion SP, Trophy Copper, etc.) | **Partially** — alias lookup fails cleanly, identifying the gap precisely |
| 54 | No `bullet_name` extracted, or caliber unresolvable | **No** — upstream extraction problem |
| 12 | Other (low confidence, ambiguous) | **Maybe** — structured match eliminates ambiguity |

---

## 3. Proposed Design

### 3.1 New table: `bullet_product_line`

```sql
CREATE TABLE bullet_product_line (
    id          VARCHAR(36) PRIMARY KEY,
    manufacturer_id VARCHAR(36) NOT NULL REFERENCES manufacturer(id),
    name        VARCHAR(100) NOT NULL,   -- canonical name: "ELD Match", "MatchKing", "TSX"
    slug        VARCHAR(100) NOT NULL,   -- normalized: "eld-match", "matchking", "tsx"
    category    VARCHAR(50),             -- "match", "hunting", "varmint", "tactical", "target", "general"
    is_generic  BOOLEAN DEFAULT FALSE,   -- TRUE for "Soft Point", "FMJ", etc.
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(manufacturer_id, slug)
);
CREATE INDEX ix_bpl_slug ON bullet_product_line(slug);
CREATE INDEX ix_bpl_manufacturer ON bullet_product_line(manufacturer_id);
```

**~137 rows** based on current `SELECT DISTINCT manufacturer_id, product_line FROM bullet`. Auto-seeded from existing data.

### 3.2 FK on bullet (nullable, backward-compatible)

```sql
ALTER TABLE bullet ADD COLUMN product_line_id VARCHAR(36) REFERENCES bullet_product_line(id);
CREATE INDEX ix_bullet_product_line_id ON bullet(product_line_id);
```

The existing `bullet.product_line` VARCHAR stays for now (used by display_name computation, extraction). The FK is populated via a backfill that joins on `(manufacturer_id, product_line)` → `bullet_product_line.slug`.

### 3.3 Entity aliases for product lines

Add `"bullet_product_line"` to the allowed `entity_type` values in `entity_alias`:

```yaml
# Curation patch example
- action: add_entity_alias
  entity_type: bullet_product_line
  entity_name: "ELD Match"       # resolves via bullet_product_line.name
  alias: "ELDM"
  alias_type: abbreviation

- action: add_entity_alias
  entity_type: bullet_product_line
  entity_name: "ELD Match"
  alias: "ELD-M"
  alias_type: abbreviation
```

**~30 aliases** covers all major abbreviations (ELDM, ELDX, SMK, TMK, TGK, ABLR, AB, VLD, LRHT, TTSX, LRX, Scenar-L, CC, RDF, SST, CX, A-Tip, etc.) — vs 149 per-bullet aliases in the current approach.

### 3.4 Resolver changes

**New resolution path** (replaces current Tier 2):

```
Extracted cartridge:
  bullet_type: "ELD-X"
  bullet_weight: 143
  caliber → bullet_diameter: 0.264

Step 1: Resolve product line
  normalize("ELD-X") → "eld-x"
  Query: bullet_product_line WHERE slug = "eld-x"
    OR: entity_alias WHERE entity_type = "bullet_product_line"
        AND lower(alias) = "eld-x"
  → bullet_product_line.id

Step 2: Structured bullet lookup
  SELECT b.id FROM bullet b
  WHERE b.product_line_id = :pl_id
    AND b.weight_grains BETWEEN 142.5 AND 143.5
    AND b.bullet_diameter_inches BETWEEN 0.263 AND 0.265
  → exact match (deterministic, no fuzzy scoring)

Step 3: Confidence
  product_line + weight + diameter: 0.95
  product_line + diameter (no weight): 0.80
  product_line only (ambiguous): 0.60
```

**Key difference from current Tier 2**: The alias lookup replaces `_normalize_product_line()` string comparison. Instead of normalizing both sides and comparing strings, we resolve to a canonical entity ID first, then do a structured query. This handles abbreviations, misspellings, and cross-format variations that string normalization can't.

**Cross-manufacturer matching** works naturally: extracted "SMK" → alias lookup → Sierra MatchKing product_line_id → bullet query. The cartridge manufacturer (Federal, for Gold Medal Match) is irrelevant to the bullet product line lookup.

### 3.5 Export: flatten aliases into `alt_names`

At export time (`scripts/export_production_db.py`):

1. For each bullet, look up its `product_line_id`
2. Query `entity_alias WHERE entity_type = 'bullet_product_line' AND entity_id = :pl_id`
3. Collect all alias strings
4. Write as JSON array into `bullet.alt_names`

```sql
-- Example: every Hornady ELD Match bullet gets alt_names = ["ELDM", "ELD-M"]
UPDATE bullet SET alt_names = '["ELDM", "ELD-M"]'
WHERE product_line_id = (SELECT id FROM bullet_product_line WHERE slug = 'eld-match');
```

**The `bullet_product_line` table itself is NOT exported** — it's a backend-only entity. The iOS app sees:
- `bullet.alt_names` JSON with abbreviation strings (for search)
- `entity_alias` table with bullet_product_line entries (queryable for advanced search)
- No new tables or schema changes on the iOS side

Actually, reconsider: we should **drop** `bullet_product_line` from the export (add to `PIPELINE_ONLY_TABLES` in export script). The iOS app doesn't need it — the aliases are baked into `alt_names`.

Alternatively, we **do** export it as a lightweight lookup for the iOS app to group bullets by product line in the UI. This is a nice-to-have, not a requirement. Decision: export it. It's small (~137 rows) and useful for filtering/grouping.

### 3.6 Curation system changes

Add to `AddEntityAliasOp.entity_type` literal:

```python
entity_type: Literal["manufacturer", "caliber", "chamber", "bullet", "cartridge", "bullet_product_line"]
```

Add `_resolve_entity` support for `bullet_product_line`:

```python
_ENTITY_TYPE_MODEL = {
    ...
    "bullet_product_line": BulletProductLine,
}
```

No new curation operation needed — `add_entity_alias` already handles it once the entity type is registered.

---

## 4. Implementation Plan

### Phase 1: Schema + Seed + Aliases + Export — COMPLETE

1. ~~Create `BulletProductLine` model in `src/drift/models/`~~
2. ~~Alembic migration (`b3f4a5c6d7e8`): create table + add `bullet.product_line_id` FK~~
3. ~~Seed script (`scripts/seed_product_lines.py`): 139 product lines from existing data~~
4. ~~Backfill: 738 bullets linked via `product_line_id`~~
5. ~~Register `bullet_product_line` in curation system (`entity_alias` + `_ENTITY_TYPE_MODEL`)~~
6. ~~Curation patch `014_bullet_product_line_aliases.yaml`: 30 aliases applied~~
7. ~~Export script: flatten aliases into `bullet.alt_names`, drop `bullet_product_line` + `product_line_id` from production~~
8. ~~All 361 tests pass~~

**Decision on Q2**: `bullet_product_line` table is NOT exported — dropped alongside `bullet_bc_source`. Aliases are baked into `alt_names`. If iOS needs product line grouping later, we can revisit.

### Phase 2: Resolver integration — PLANNED (next)

9. Add alias-based product line resolution to `match_bullet()`
10. Replace current Tier 2 string-comparison with structured `product_line_id` lookup
11. Keep Tiers 3-4 as fallback for bullets without product_line_id
12. Dry-run pipeline-store and measure improvement on flagged cartridges

### Phase 3: Backfill gaps — FUTURE

13. Backfill `product_line` for remaining ~547 bullets (LLM re-extraction or regex)
14. Identify product lines that exist in cartridge extractions but not in `bullet_product_line` table (Fusion Soft Point, Trophy Copper, etc.) — create stubs for future bullet ingestion

---

## 5. Open Questions

### Q1: Keep `bullet.product_line` string column?

**Recommendation: Yes, keep both.** The string is used by `compute_bullet_display_name()` in the export script and is human-readable. The FK provides structured lookup. They serve different purposes. Eventually the string could be derived from the FK, but that's a future cleanup.

### Q2: Export `bullet_product_line` table to iOS?

**Recommendation: Yes.** It's 137 rows, adds useful grouping/filtering capability. Drop `created_at`/`updated_at` columns per standard export practice. The iOS app can show "ELD Match (12 bullets)" as a filter category.

### Q3: How to handle generics ("Soft Point", "FMJ", "HP")?

Set `is_generic = TRUE` on these product lines. The resolver skips generics in the structured lookup path (they'd match too many bullets). Generics fall through to the existing fuzzy Tiers 3-4. This matches the `_generic_` prefix convention from the earlier design doc.

### Q4: Should the resolver cache product line lookups?

**Yes.** `bullet_product_line` + its aliases are static during a pipeline run. Load once into a `dict[str, str]` mapping `(normalized_alias | slug) → product_line_id` at resolver init. No per-entity DB queries.

### Q5: What about the 547 bullets with NULL product_line?

Three strategies, in order of preference:
1. **Regex extraction** from bullet name (the `derive_product_line()` approach from the earlier design doc) — covers ~80% of these
2. **LLM re-extraction** — re-run extraction on the source pages with updated prompts asking for product_line explicitly
3. **Manual curation** — for the remaining long tail

Phase 5 handles this. The system works without it — those bullets just don't benefit from structured matching.

---

## 6. Expected Impact

### Alias coverage (iOS search)

| Before | After |
|---|---|
| 0 bullet aliases | ~30 product-line aliases covering all 738 bullets with product_lines |
| Search "ELDM" → no results | Search "ELDM" → all ELD Match bullets across all calibers |

### Cartridge resolution improvement

| Flagged category | Count | Expected outcome |
|---|---|---|
| Wrong weight variant | 53 | **Improved flagging**: "ELD-X resolved, need 117gr .257 variant" instead of generic "unresolved bullet" |
| Wrong diameter | 27 | Same — precise gap identification |
| Product line not in DB | 47 | **Clean failure**: "product_line 'fusion-soft-point' resolved but no bullets exist" — actionable for curation |
| No bullet_name extracted | 54 | No change (upstream problem) |

**Net**: ~80 cartridges get better diagnostics, ~47 get actionable failure messages. The actual *resolution* improvement depends on bullet coverage — the structured lookup is only better than fuzzy when the right bullet exists in the DB. The bigger win is turning opaque "low confidence / unresolved" failures into precise "need X bullet at Y weight" signals.

### Data quality

- Single source of truth for product line identity (instead of string matching across 3 pipeline stages)
- Aliases managed via curation patches (no code changes to add new abbreviations)
- Foundation for future product-line-level metadata (marketing description, BC range, intended use, etc.)
