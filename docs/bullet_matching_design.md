# Bullet Matching Improvements: Design Proposal

**Status**: Draft — requesting review
**Date**: 2026-03-06
**Authors**: Brian, Claude Agent

---

## 1. Problem Statement

Cartridge-to-bullet resolution fails for ~100+ cartridges because the resolver can't match short product-line names extracted from cartridge pages to full product names stored in the bullet table.

**Extracted from cartridge pages** (short):
```
"ELD-X", "SST®", "Fusion Soft Point", "Trophy Copper",
"Barnes Triple-Shock X Bullet (TSX)", "Berger Hybrid"
```

**Stored in bullet table** (full product names):
```
"30 Cal .308 178 gr ELD-X®"
"6.5MM 140 GR HPBT MatchKing (SMK)"
"Fusion Component Bullet, .308, 180 Grain"
"0.284" 7MM TSX BT 140 GR"
```

The current resolver uses Jaccard/containment string similarity, which works well when names overlap significantly but breaks down for asymmetric names. Even the containment scoring (which strips noise words) produces low scores for 1-2 word product names against 8-10 word DB names.

### Failure Analysis

From 751 cartridges with extracted `bullet_name`, the top extracted values are:

| Count | Extracted bullet_name | What it should match |
|---|---|---|
| 44 | `FTX®` | Hornady FTX bullets (not in DB yet) |
| 41 | `ELD-X` | `{cal} {dia} {wt} gr ELD-X®` (works sometimes, inconsistent) |
| 40 | `Fusion Soft Point` | `Fusion Component Bullet, .{dia}, {wt} Grain` |
| 40 | `Jacketed Soft Point` | Generic — no specific bullet family |
| 35 | `CX®` | `{cal} {dia} {wt} gr CX®` |
| 17 | `Trophy Copper` | Not in DB yet |
| 17 | `Barnes Triple-Shock X Bullet (TSX)` | `0.{dia}" {cal} TSX BT {wt} GR` |
| 17 | `Terminal Ascent` | `Terminal Ascent Component Bullet, .{dia}, {wt} Grain` |
| 15 | `Trophy Bonded Tip` | `Trophy Bonded Tip Component Bullet, .{dia}, {wt} Grain` |

Failure modes:
1. **Short vs long name mismatch** — "ELD-X" vs "30 Cal .308 178 gr ELD-X®" (asymmetric)
2. **Trademark symbols** — ®, ™, unicode dashes (‑ vs -)
3. **Missing bullet records** — FTX, Trophy Copper, Swift A-Frame don't exist in DB at all
4. **Generic types** — "Soft Point", "FMJ", "HP" match too many candidates
5. **Cross-product-line false positives** — "Barnes TSX 160gr" matches "ELD-X 162gr" when no TSX exists

---

## 2. Current Matching Architecture

The resolver (`src/drift/pipeline/resolution/resolver.py`) uses tiered matching:

| Tier | Method | Confidence | Filters |
|---|---|---|---|
| 1 | Exact SKU | 1.0 | `Bullet.sku == extracted.sku` |
| 2 | Composite key | 0.86-0.95 | manufacturer + diameter(±0.001") + weight(±0.5gr) + name_score > 0.55 |
| 3 | Fuzzy name | score × 0.8 | name similarity > 0.5, weight agreement bonus |

For **cartridge→bullet** resolution specifically (the main failure point):
- `bullet_name` from cartridge extraction is wrapped in a synthetic stub: `{"name": bullet_name, "weight_grains": weight}`
- `match_bullet()` is called with `manufacturer_id=None` (cross-manufacturer) and `bullet_diameter_inches` from the resolved caliber
- Only filters: diameter + weight + fuzzy name scoring

The name scoring has 13 abbreviation expansions (HPBT, FMJ, etc.) but no product-line awareness.

### What Already Works Well
- SKU matching: ~60% of bullets match by exact SKU (1.0 confidence)
- Same-manufacturer cartridges (Hornady loads using Hornady bullets): name overlap is sufficient
- The Bullet model already has `base_type`, `tip_type`, `type_tags` fields (~70-80% populated), but **none are used in matching**

---

## 3. Proposed Solution: Product Line Matching

### Core Idea

Add a `product_line` field to the Bullet model representing the bullet's product family (e.g., "eld-x", "matchking", "tsx", "fusion"). Then add a new matching tier that matches by `product_line + weight + diameter` with high confidence, bypassing name similarity entirely.

### 3.1 New Column: `bullet.product_line`

A normalized, lowercase, hyphenated identifier for the bullet's product family.

```sql
ALTER TABLE bullet ADD COLUMN product_line VARCHAR(100);
CREATE INDEX ix_bullet_product_line ON bullet(product_line);
```

Examples:

| Bullet Name | product_line |
|---|---|
| `30 Cal .308 178 gr ELD-X®` | `eld-x` |
| `6.5MM 140 GR HPBT MatchKing (SMK)` | `matchking` |
| `0.308" 30 CAL TSX BT 168 GR` | `tsx` |
| `Fusion Component Bullet, .308, 180 Grain` | `fusion` |
| `338 Caliber 225gr Partition (50ct)` | `partition` |
| `30 Caliber 185 Grain Hybrid Target Rifle Bullet` | `hybrid-target` |
| `22 Cal .224 55 gr SP Boattail with Cannelure` | `null` (generic) |

### 3.2 Product Line Alias Map

A dictionary mapping normalized extracted names → canonical product_line values. This is the critical piece — it bridges the vocabulary gap between extraction and DB.

```python
_PRODUCT_LINE_ALIASES: dict[str, str] = {
    # Hornady
    "eld-x": "eld-x",
    "eld match": "eld-match",
    "eld® match": "eld-match",
    "sst": "sst",
    "sst (super shock tip)": "sst",
    "cx": "cx",
    "v-max": "v-max",
    "hornady® v-max®": "v-max",
    "ftx": "ftx",
    "interlock": "interlock",
    "interlock sp": "interlock-sp",
    "a-tip match": "a-tip",
    "ntx": "ntx",
    "monoflex": "monoflex",
    # ... ~120 entries covering all known product lines

    # Sierra
    "matchking": "matchking",
    "sierra matchking": "matchking",
    "sierra matchking boat-tail hollow point": "matchking",
    "gameking": "gameking",
    "varmintking": "varmintking",
    # ...

    # Barnes
    "tsx": "tsx",
    "barnes tsx": "tsx",
    "barnes triple-shock x bullet (tsx)": "tsx",
    "ttsx": "ttsx",
    "lrx": "lrx",
    # ...

    # Nosler
    "partition": "partition",
    "nosler partition": "partition",
    "accubond": "accubond",
    "ballistic tip": "ballistic-tip",
    # ...

    # Federal
    "fusion soft point": "fusion",
    "fusion tipped": "fusion-tipped",
    "trophy bonded tip": "trophy-bonded-tip",
    "terminal ascent": "terminal-ascent",
    "trophy copper": "trophy-copper",
    # ...

    # Berger
    "berger hybrid": "hybrid",
    "hybrid hunter": "hybrid-hunter",
    "hybrid target": "hybrid-target",
    # ...

    # Generic types — tagged differently, used as tiebreaker only
    "soft point": "_generic_sp",
    "jacketed soft point": "_generic_jsp",
    "fmj": "_generic_fmj",
    "hp": "_generic_hp",
    # ...
}
```

### 3.3 Normalization Function

Before alias lookup, normalize the extracted name:
- Strip trademark symbols: ®, ™, ©
- Normalize unicode dashes: ‑ → -
- Lowercase
- Collapse whitespace
- Try both with and without parenthetical content

### 3.4 New Matching Tier: "Tier 1.5 — Product Line Match"

Inserted between SKU (Tier 1) and composite key (Tier 2):

```
Tier 1:   Exact SKU          → confidence 1.0
Tier 1.5: Product line match  → confidence 0.95 (with weight) or 0.80 (without)
Tier 2:   Composite key       → confidence 0.86-0.95
Tier 3:   Fuzzy name          → confidence score × 0.8
```

Logic:
1. Normalize the extracted name and look up in `_PRODUCT_LINE_ALIASES`
2. If a non-generic product_line is found:
   - Filter candidates where `bullet.product_line == resolved_product_line`
   - If weight also matches (±0.5gr): confidence = 0.95
   - If no weight: confidence = 0.80
3. Generic types (prefixed with `_generic_`) are not used in Tier 1.5 but could inform Tier 2/3 tiebreaking

This gives deterministic, high-confidence matches that don't depend on string similarity at all.

### 3.5 Populating product_line for Existing Bullets

A `derive_product_line(name: str) -> str | None` function that pattern-matches known product keywords in bullet names:

```python
# Ordered from specific to generic (check "TTSX" before "TSX")
_PRODUCT_LINE_PATTERNS = [
    (r"\beld[\s\u2010\u2011-]?x\b", "eld-x"),
    (r"\beld[\s\u2010\u2011-]?match\b", "eld-match"),
    (r"\beld[\s\u2010\u2011-]?vt\b", "eld-vt"),
    (r"\bttsx\b", "ttsx"),
    (r"\btsx\b", "tsx"),
    (r"\blrx\b", "lrx"),
    (r"\bmatchking\b", "matchking"),
    (r"\bgameking\b", "gameking"),
    (r"\bpartition\b", "partition"),
    (r"\baccubond\b", "accubond"),
    (r"\bfusion\b", "fusion"),
    # ... etc
]

def derive_product_line(name: str) -> str | None:
    normalized = name.lower()
    normalized = normalized.replace("®", "").replace("™", "")
    for pattern, product_line in _PRODUCT_LINE_PATTERNS:
        if re.search(pattern, normalized):
            return product_line
    return None
```

Run via a backfill script for existing 641 bullets, and auto-applied when creating new bullets in pipeline_store.

---

## 4. Open Questions for Review

### Q1: Should product_line be a normalized string or a FK to a reference table?

**Option A: String column** (proposed above)
- Simple, no migration burden, easy to add new values
- Risk: typos, inconsistency across manual entries

**Option B: ProductLine reference table with FK**
- Enforced consistency, can attach metadata (manufacturer_id, description)
- More migration work, harder to add new lines on the fly
- Could hold the alias mappings instead of a Python dict

**Option C: Hybrid — string column + validation in Pydantic/curation**
- Simple storage, but validate against known values at write time
- Best of both worlds?

### Q2: Where should the alias map live?

**Option A: Python dict in resolver.py** (proposed above)
- Fast, no DB queries, easy to test
- Adding new aliases requires code changes + deploy

**Option B: EntityAlias table** (currently 0 bullet aliases, supports entity_type)
- Already exists, curation patches can add entries
- Requires DB query at resolution time (cacheable)
- Aliases can be managed without code changes

**Option C: Both** — Python dict for well-known aliases, EntityAlias for edge cases
- More complex but most flexible

### Q3: How to handle generic types?

"Soft Point", "FMJ", "HP" appear in 40+ cartridges but aren't specific enough to uniquely identify a bullet. Options:
- Ignore them in Tier 1.5 (current proposal — prefix with `_generic_`)
- Use them as a tiebreaker in Tier 2/3 scoring
- Match on `tip_type` / `base_type` fields in combination with weight + diameter

### Q4: InterLock sub-variants

Hornady InterLock comes in SP, SP-RP, BTSP, RN variants. Should these be separate product_lines or one?
- Separate: `interlock-sp`, `interlock-sp-rp`, `interlock-btsp`, `interlock-rn`
- Combined: all `interlock`, rely on weight+diameter to disambiguate
- Hybrid: `interlock` as primary, sub-variant as optional qualifier

### Q5: Impact on canonical name / search in the iOS app

The user mentioned wanting a canonical name system for the app UI. Should `product_line` serve double duty as a user-facing label, or should that be a separate `display_name` field? product_line as designed is a machine-friendly slug ("eld-x"), not a display string ("ELD-X").

---

## 5. Expected Impact

### Matching improvements (estimated)

| Extracted bullet_name | Count | Current result | After product_line |
|---|---|---|---|
| `ELD-X` | 41 | Inconsistent (works for some weights) | Deterministic match via product_line=eld-x |
| `Fusion Soft Point` | 40 | Fails (no name overlap) | Match via product_line=fusion |
| `CX®` | 35 | Fails (trademark symbol) | Match via product_line=cx |
| `SST (Super Shock Tip)` | 17+14 | Partial (parenthetical helps) | Deterministic via product_line=sst |
| `Barnes Triple-Shock X Bullet (TSX)` | 17 | Fails (long name, different format) | Match via product_line=tsx |
| `Terminal Ascent` | 17 | Fails (no overlap with Federal name format) | Match via product_line=terminal-ascent |
| `Trophy Bonded Tip` | 15 | Partial | Deterministic via product_line=trophy-bonded-tip |
| `Berger Hybrid` | 11 | Ambiguous (multiple hybrid variants) | Match via product_line=hybrid + weight |
| `Nosler Partition` | 11 | Fails (no overlap with Nosler naming) | Match via product_line=partition |

**Conservative estimate**: This unblocks 200+ cartridge-bullet matches that currently fail or produce low-confidence results. The remaining ~40 unresolvable ones are generic types ("Soft Point", "FMJ") and bullets that simply don't exist in the DB yet.

### What this does NOT solve

1. **Missing bullet records** — FTX (44 cartridges), Trophy Copper (17), Swift A-Frame (8), etc. still need curation patches to create the bullets first
2. **Generic types** — "Jacketed Soft Point" (40 cartridges) can't be uniquely matched to a specific bullet product
3. **Bullets with no product line** — generic SP/FMJ/HP bullets (like Hornady "22 Cal .224 55 gr SP Boattail") don't belong to a named product family

---

## 6. Missing BC Data — Separate Workstream

22+ bullets have no BulletBCSource records. This requires manual research from manufacturer websites. A separate doc (`docs/bc_research_prompt.md`) will provide a structured prompt for a CoWork research agent to systematically gather BC values from:

- Sierra: BCs on product pages
- Nosler: BCs in load data section (not product pages)
- Hornady: Both G1 and G7 on product pages
- Barnes: G1 on product pages
- Berger: G1 and G7 on product pages
- Federal: Often no BC published (may need third-party sources)

---

## 7. Implementation Sketch

1. Add `product_line` column + migration
2. Add alias map + normalization + Tier 1.5 to resolver
3. Create `derive_product_line()` utility + backfill script
4. Update pipeline_store.py and curation.py to support the new field
5. Run backfill, then dry-run pipeline-store to measure impact
6. Write BC research prompt (separate PR)

Total estimated effort: ~1-2 days for Part 1, ~0.5 day for Part 2.
