---
name: data-quality
description: Data quality checks, BC validation, manufacturer resolution, and bullet name normalization for the ballistics database
---

# Data Quality

## Quick Checks

```bash
python scripts/describe_db.py              # Schema + row counts
make pipeline-status                       # Pipeline stage counts
python scripts/crosscheck_manifest.py        # Manifest vs DB cross-check
python scripts/crosscheck_manifest.py --json # + write JSON report
```

## Tracking & Recording Findings

All QA findings must be recorded — the system uses three interconnected files:

- **`data/data_qa/known_issues.json`** — structured issue tracker. Each finding gets an ID (C1, W1, etc.), severity, status, and notes. Update existing entries when status changes; add new ones for new findings.
- **`TODO.md`** (project root) — lightweight action items. Reference known_issues IDs for cross-linking. Items >1 hour should graduate to Linear.
- **`data/data_qa/report_YYYY-MM-DD.md`** — point-in-time QA reports. These are snapshots; don't update old reports.

**Workflow**: Run queries → record findings in `known_issues.json` → add actionable items to `TODO.md` → fix via curation patch or pipeline re-run → update status in both files.

**Severity levels** (used in both known_issues.json and QA reports):
- **CRITICAL**: Wrong BC values, incorrect entity linkages, diameter mismatches — directly affects solver accuracy
- **WARNING**: Missing BC data, potential duplicates, implausible values — degrades UX but doesn't corrupt calculations
- **INFO**: Cosmetic issues (name quality), expected gaps, coverage stats

QA prompt spec: `data/data_qa/PROMPT.md`

## BC Range Expectations

| Drag Model | Typical Range | Error Threshold | Notes |
|---|---|---|---|
| G1 | 0.100 - 0.800 | < 0.050 or > 1.200 | Heavy .375/.50 BMG can legitimately exceed 1.0 |
| G7 | 0.050 - 0.450 | < 0.020 or > 0.600 | Same large-caliber caveat applies |

Values outside the **error threshold** are almost certainly extraction errors. Values outside the **typical range** but within thresholds should be reviewed with bullet diameter context — pistol bullets and heavy magnum/ELR bullets legitimately fall outside the typical range.

Common extraction errors:
- G1/G7 values swapped (G7 value stored as G1 — detectable when both present and G7 > G1)
- Decimal point errors (0.473 recorded as 4.73)
- Sectional density stored instead of BC

## Key SQL Queries

### Referential Integrity
```sql
-- Bullets referencing non-existent manufacturer
SELECT b.id, b.name, b.manufacturer_id
FROM bullet b LEFT JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE m.id IS NULL;

-- Cartridges referencing non-existent bullet
SELECT c.id, c.name, c.bullet_id
FROM cartridge c LEFT JOIN bullet b ON c.bullet_id = b.id
WHERE b.id IS NULL;

-- Cartridges referencing non-existent caliber
SELECT c.id, c.name, c.caliber_id
FROM cartridge c LEFT JOIN caliber cal ON c.caliber_id = cal.id
WHERE cal.id IS NULL;

-- Cartridges referencing non-existent manufacturer
SELECT c.id, c.name, c.manufacturer_id
FROM cartridge c LEFT JOIN manufacturer m ON c.manufacturer_id = m.id
WHERE m.id IS NULL;

-- BulletBCSources referencing non-existent bullet
SELECT bcs.id, bcs.bullet_id
FROM bullet_bc_source bcs LEFT JOIN bullet b ON bcs.bullet_id = b.id
WHERE b.id IS NULL;

-- Entity aliases pointing to non-existent entities
SELECT ea.id, ea.entity_type, ea.alias, ea.entity_id
FROM entity_alias ea
WHERE (ea.entity_type = 'manufacturer' AND ea.entity_id NOT IN (SELECT id FROM manufacturer))
   OR (ea.entity_type = 'caliber'      AND ea.entity_id NOT IN (SELECT id FROM caliber))
   OR (ea.entity_type = 'bullet'       AND ea.entity_id NOT IN (SELECT id FROM bullet));
```

### Cross-Entity Consistency
```sql
-- Cartridge bullet_weight vs linked bullet weight (mismatches)
-- Production export filters out >1.0gr mismatches
SELECT c.id, c.name, c.bullet_weight_grains AS cart_wt, b.weight_grains AS bullet_wt,
       ABS(c.bullet_weight_grains - b.weight_grains) AS diff
FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
WHERE ABS(c.bullet_weight_grains - b.weight_grains) > 1.0;

-- Cartridge caliber diameter vs linked bullet diameter (mismatches)
-- Tolerance 0.002" accommodates real-world variance (.311 vs .312 bullets)
SELECT c.id, c.name, b.bullet_diameter_inches AS bullet_diam,
       cal.bullet_diameter_inches AS cal_diam, cal.name AS caliber
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN caliber cal ON c.caliber_id = cal.id
WHERE ABS(b.bullet_diameter_inches - cal.bullet_diameter_inches) > 0.002;

-- Cartridges with zero or implausible muzzle velocity
-- Known zeros: 8 Hornady ECX International (velocity unpublished) + 1 Nosler .300 Wby
SELECT c.id, c.name, c.muzzle_velocity_fps, m.name AS mfr
FROM cartridge c JOIN manufacturer m ON c.manufacturer_id = m.id
WHERE c.muzzle_velocity_fps <= 0
   OR c.muzzle_velocity_fps > 5000;
```

### Cartridge→Bullet Linkage Audit

The resolver matches bullets by weight/diameter, which creates two classes of mislink:

1. **Cross-manufacturer false positives** — cartridge linked to a bullet from the wrong manufacturer (e.g., Hornady load → Lapua bullet). Most common with 150gr/.308 where many manufacturers have bullets at the same weight/diameter.
2. **Same-manufacturer type confusion** — correct manufacturer but wrong bullet variant (e.g., ELD-X → ELD Match, BTSP → RN). Happens when the correct variant is missing from the DB.

```sql
-- Cross-manufacturer mislinks: cartridge mfr vs bullet mfr
-- Self-manufacturing brands (Hornady, Nosler, Barnes, Winchester) almost always
-- load their own bullets. Cross-mfr links for these are usually wrong.
-- Exception: Winchester loads Nosler BST bullets (Combined Technologies).
-- Federal, Black Hills, etc. legitimately load third-party bullets.
SELECT cm.name AS cart_mfr, bm.name AS bullet_mfr, COUNT(*) AS cnt,
       GROUP_CONCAT(c.name, ' | ') AS examples
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN manufacturer cm ON c.manufacturer_id = cm.id
JOIN manufacturer bm ON b.manufacturer_id = bm.id
WHERE cm.id != bm.id
GROUP BY cm.name, bm.name
ORDER BY cnt DESC;

-- Catch-all bullets: single bullet linked to many cartridges from different manufacturers
-- A bullet linked to 5+ cartridges across 2+ manufacturers is likely a resolver catch-all
SELECT b.id, b.name AS bullet, bm.name AS bullet_mfr, COUNT(*) AS cart_count,
       COUNT(DISTINCT c.manufacturer_id) AS mfr_count,
       GROUP_CONCAT(DISTINCT cm.name) AS cart_mfrs
FROM bullet b
JOIN cartridge c ON c.bullet_id = b.id
JOIN manufacturer bm ON b.manufacturer_id = bm.id
JOIN manufacturer cm ON c.manufacturer_id = cm.id
GROUP BY b.id
HAVING cart_count >= 5 AND mfr_count >= 2
ORDER BY cart_count DESC;

-- Same-manufacturer type confusion: cartridge name contains a bullet type keyword
-- that doesn't appear in the linked bullet name
-- Common pairs: ELD-X vs ELD Match, CX vs SST, BTSP vs RN, TMK vs SMK
SELECT c.name AS cart, b.name AS bullet, cm.name AS mfr,
       c.bc_g1 AS cart_bc, b.bc_g1_published AS bullet_bc
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN manufacturer cm ON c.manufacturer_id = cm.id
WHERE cm.id = b.manufacturer_id  -- same manufacturer
  AND (
    (c.name LIKE '%ELD-X%' AND b.name NOT LIKE '%ELD-X%' AND b.name NOT LIKE '%ELD_X%')
    OR (c.name LIKE '%ELD Match%' AND b.name NOT LIKE '%ELD%Match%')
    OR (c.name LIKE '% CX%' AND b.name NOT LIKE '% CX%')
    OR (c.name LIKE '% SST%' AND b.name NOT LIKE '%SST%')
    OR (c.name LIKE '%BTSP%' AND b.name NOT LIKE '%BTSP%' AND b.name NOT LIKE '%Boat%')
    OR (c.name LIKE '%TMK%' AND b.name NOT LIKE '%TMK%' AND b.name NOT LIKE '%Tipped%Match%')
    OR (c.name LIKE '%Partition%' AND b.name NOT LIKE '%Partition%')
    OR (c.name LIKE '%AccuBond%' AND b.name NOT LIKE '%AccuBond%')
  );

-- Hornady loads linked to non-Hornady bullets (almost always wrong)
SELECT c.name AS cart, b.name AS bullet, bm.name AS bullet_mfr,
       c.bullet_match_method, c.bullet_match_confidence
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN manufacturer bm ON b.manufacturer_id = bm.id
WHERE c.manufacturer_id IN (SELECT id FROM manufacturer WHERE name = 'Hornady')
  AND bm.name != 'Hornady';

-- Nosler loads linked to non-Nosler bullets (almost always wrong)
SELECT c.name AS cart, b.name AS bullet, bm.name AS bullet_mfr
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN manufacturer bm ON b.manufacturer_id = bm.id
WHERE c.manufacturer_id IN (SELECT id FROM manufacturer WHERE name = 'Nosler')
  AND bm.name != 'Nosler';
```

### Duplicate Detection
```sql
-- Potential duplicate bullets (same manufacturer + weight + diameter)
-- ROUND() on diameter avoids float grouping artifacts
SELECT m.name AS mfr, b.weight_grains, ROUND(b.bullet_diameter_inches, 3) AS diam,
       COUNT(*) AS cnt, GROUP_CONCAT(b.name, ' | ') AS names
FROM bullet b JOIN manufacturer m ON b.manufacturer_id = m.id
GROUP BY b.manufacturer_id, b.weight_grains, ROUND(b.bullet_diameter_inches, 3)
HAVING cnt > 1
ORDER BY cnt DESC;

-- Potential duplicate cartridges (same manufacturer + caliber + bullet + weight)
-- Legitimate dupes: different product lines at same weight (e.g., Outfitter vs Superformance)
-- True dupes: identical name/MV/source_url (e.g., double curation insert)
SELECT m.name AS mfr, cal.name AS caliber, c.bullet_weight_grains,
       b.name AS bullet, COUNT(*) AS cnt,
       GROUP_CONCAT(c.name, ' | ') AS names
FROM cartridge c
JOIN manufacturer m ON c.manufacturer_id = m.id
JOIN caliber cal ON c.caliber_id = cal.id
JOIN bullet b ON c.bullet_id = b.id
GROUP BY c.manufacturer_id, c.caliber_id, c.bullet_id, c.bullet_weight_grains
HAVING cnt > 1
ORDER BY cnt DESC;

-- Exact duplicate cartridges (same name + MV + source_url — definitely wrong)
SELECT c1.id AS id1, c2.id AS id2, c1.name, c1.muzzle_velocity_fps,
       c1.data_source, c1.source_url
FROM cartridge c1
JOIN cartridge c2 ON c1.name = c2.name
  AND c1.muzzle_velocity_fps = c2.muzzle_velocity_fps
  AND c1.id < c2.id;
```

### BC Validation
```sql
-- Likely BC extraction errors on BULLETS (outside hard error thresholds)
SELECT b.id, b.name, m.name AS mfr, b.bullet_diameter_inches AS diam,
       b.bc_g1_published AS g1, b.bc_g7_published AS g7
FROM bullet b JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE (b.bc_g1_published IS NOT NULL AND (b.bc_g1_published < 0.05 OR b.bc_g1_published > 1.2))
   OR (b.bc_g7_published IS NOT NULL AND (b.bc_g7_published < 0.02 OR b.bc_g7_published > 0.6));

-- BC values outside typical range — review with diameter context, not necessarily errors
SELECT b.id, b.name, m.name AS mfr, b.bullet_diameter_inches AS diam,
       b.bc_g1_published AS g1, b.bc_g7_published AS g7
FROM bullet b JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE (b.bc_g1_published IS NOT NULL AND (b.bc_g1_published < 0.1 OR b.bc_g1_published > 0.8))
   OR (b.bc_g7_published IS NOT NULL AND (b.bc_g7_published < 0.05 OR b.bc_g7_published > 0.45))
ORDER BY b.bullet_diameter_inches, b.bc_g1_published;

-- Likely BC extraction errors on CARTRIDGES (outside hard error thresholds)
SELECT c.id, c.name, m.name AS mfr, c.bc_g1, c.bc_g7,
       cal.name AS caliber
FROM cartridge c
JOIN manufacturer m ON c.manufacturer_id = m.id
JOIN caliber cal ON c.caliber_id = cal.id
WHERE (c.bc_g1 IS NOT NULL AND (c.bc_g1 < 0.05 OR c.bc_g1 > 1.2))
   OR (c.bc_g7 IS NOT NULL AND (c.bc_g7 < 0.02 OR c.bc_g7 > 0.6));

-- Cartridge BC vs linked bullet BC divergence (>15% relative difference)
-- Large divergence suggests wrong bullet linkage or extraction error on one side
SELECT c.name AS cart, b.name AS bullet,
       c.bc_g1 AS cart_g1, b.bc_g1_published AS bullet_g1,
       ROUND(ABS(c.bc_g1 - b.bc_g1_published) / b.bc_g1_published * 100, 1) AS g1_pct_diff
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
WHERE c.bc_g1 IS NOT NULL AND b.bc_g1_published IS NOT NULL
  AND ABS(c.bc_g1 - b.bc_g1_published) / b.bc_g1_published > 0.15
ORDER BY g1_pct_diff DESC;

-- G1/G7 likely swapped (G7 should always be < G1 for the same bullet)
SELECT b.id, b.name, b.bc_g1_published AS g1, b.bc_g7_published AS g7
FROM bullet b
WHERE b.bc_g1_published IS NOT NULL AND b.bc_g7_published IS NOT NULL
  AND b.bc_g7_published > b.bc_g1_published;

-- bullet_bc_source records outside error thresholds
SELECT bcs.id, bcs.bc_type, bcs.bc_value, bcs.source, b.name AS bullet
FROM bullet_bc_source bcs JOIN bullet b ON bcs.bullet_id = b.id
WHERE (bcs.bc_type = 'g1' AND (bcs.bc_value < 0.05 OR bcs.bc_value > 1.2))
   OR (bcs.bc_type = 'g7' AND (bcs.bc_value < 0.02 OR bcs.bc_value > 0.6));

-- Bullet published BC diverges from bc_source records (>10% relative difference)
-- Multi-source bullets (Barnes LRX) legitimately have spread; focus on single-source divergence
SELECT b.name, bcs.bc_type,
       b.bc_g1_published AS published, bcs.bc_value AS source_val,
       ROUND(ABS(b.bc_g1_published - bcs.bc_value) / b.bc_g1_published * 100, 1) AS pct_diff
FROM bullet b
JOIN bullet_bc_source bcs ON bcs.bullet_id = b.id AND bcs.bc_type = 'g1'
WHERE b.bc_g1_published IS NOT NULL
  AND ABS(b.bc_g1_published - bcs.bc_value) / b.bc_g1_published > 0.10
UNION ALL
SELECT b.name, bcs.bc_type,
       b.bc_g7_published, bcs.bc_value,
       ROUND(ABS(b.bc_g7_published - bcs.bc_value) / b.bc_g7_published * 100, 1)
FROM bullet b
JOIN bullet_bc_source bcs ON bcs.bullet_id = b.id AND bcs.bc_type = 'g7'
WHERE b.bc_g7_published IS NOT NULL
  AND ABS(b.bc_g7_published - bcs.bc_value) / b.bc_g7_published > 0.10
ORDER BY pct_diff DESC;
```

### Production Export Simulation

The iOS app only sees records that survive `scripts/export_production_db.py` filtering. Run these to see what users actually get:

```sql
-- Cartridges that will be REMOVED by production export
-- (zero MV, weight mismatch >1gr, no BC anywhere)
SELECT 'zero_mv' AS reason, COUNT(*) FROM cartridge WHERE muzzle_velocity_fps <= 0
UNION ALL
SELECT 'weight_mismatch', COUNT(*) FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
  WHERE c.muzzle_velocity_fps > 0 AND ABS(c.bullet_weight_grains - b.weight_grains) > 1.0
UNION ALL
SELECT 'no_bc_anywhere', COUNT(*) FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
  WHERE c.muzzle_velocity_fps > 0 AND ABS(c.bullet_weight_grains - b.weight_grains) <= 1.0
    AND (c.bc_g1 IS NULL AND c.bc_g7 IS NULL)
    AND (b.bc_g1_published IS NULL AND b.bc_g1_estimated IS NULL
         AND b.bc_g7_published IS NULL AND b.bc_g7_estimated IS NULL);

-- Surviving cartridge count (what users see)
SELECT COUNT(*) AS production_cartridges
FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
WHERE c.muzzle_velocity_fps > 0
  AND ABS(c.bullet_weight_grains - b.weight_grains) <= 1.0
  AND NOT ((c.bc_g1 IS NULL AND c.bc_g7 IS NULL)
    AND (b.bc_g1_published IS NULL AND b.bc_g1_estimated IS NULL
         AND b.bc_g7_published IS NULL AND b.bc_g7_estimated IS NULL));

-- Cartridges relying solely on bullet-level BC (no cart-level BC)
-- These are at risk if bullet linkage is wrong
SELECT COUNT(*) AS bullet_bc_only
FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
WHERE c.bc_g1 IS NULL AND c.bc_g7 IS NULL
  AND (b.bc_g1_published IS NOT NULL OR b.bc_g7_published IS NOT NULL);
```

### Coverage
```sql
-- Bullets missing any BC data (no bc_source AND no published BC on bullet row)
SELECT b.id, b.name, m.name AS mfr
FROM bullet b JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE b.bc_g1_published IS NULL AND b.bc_g7_published IS NULL
  AND b.id NOT IN (SELECT DISTINCT bullet_id FROM bullet_bc_source);

-- Calibers with no bullets (by diameter match)
SELECT cal.id, cal.name, cal.bullet_diameter_inches AS diam
FROM caliber cal
WHERE NOT EXISTS (
    SELECT 1 FROM bullet b
    WHERE ABS(b.bullet_diameter_inches - cal.bullet_diameter_inches) < 0.001
);

-- Calibers with no cartridges
SELECT cal.id, cal.name
FROM caliber cal
WHERE cal.id NOT IN (SELECT DISTINCT caliber_id FROM cartridge);

-- Manufacturer bullet counts
SELECT m.name, COUNT(b.id) AS bullet_count
FROM manufacturer m LEFT JOIN bullet b ON m.id = b.manufacturer_id
GROUP BY m.id ORDER BY bullet_count DESC;

-- Manufacturer cartridge counts
SELECT m.name, COUNT(c.id) AS cart_count
FROM manufacturer m LEFT JOIN cartridge c ON m.id = c.manufacturer_id
GROUP BY m.id ORDER BY cart_count DESC;

-- Bullets with published BC but no corresponding bc_source audit record
SELECT b.id, b.name, 'g1' AS bc_type, b.bc_g1_published AS value
FROM bullet b
WHERE b.bc_g1_published IS NOT NULL
  AND b.id NOT IN (SELECT bullet_id FROM bullet_bc_source WHERE bc_type = 'g1')
UNION ALL
SELECT b.id, b.name, 'g7', b.bc_g7_published
FROM bullet b
WHERE b.bc_g7_published IS NOT NULL
  AND b.id NOT IN (SELECT bullet_id FROM bullet_bc_source WHERE bc_type = 'g7');
```

### Curation & Provenance
```sql
-- All locked (manually curated) records
SELECT 'bullet' AS type, id, name, data_source FROM bullet WHERE is_locked = 1
UNION ALL
SELECT 'cartridge', id, name, data_source FROM cartridge WHERE is_locked = 1
UNION ALL
SELECT 'rifle', id, model, data_source FROM rifle_model WHERE is_locked = 1;

-- Records by data_source
SELECT 'bullet' AS type, data_source, COUNT(*) AS cnt FROM bullet GROUP BY data_source
UNION ALL
SELECT 'cartridge', data_source, COUNT(*) FROM cartridge GROUP BY data_source
UNION ALL
SELECT 'rifle', data_source, COUNT(*) FROM rifle_model GROUP BY data_source;

-- Manual records that forgot to lock
SELECT 'bullet' AS type, id, name FROM bullet WHERE data_source = 'manual' AND is_locked = 0
UNION ALL
SELECT 'cartridge', id, name FROM cartridge WHERE data_source = 'manual' AND is_locked = 0;
```

## Manufacturer Resolution

### EntityAlias Table
The `entity_alias` table maps variant names to canonical entities. Always check this table first before doing string matching.

```sql
-- See all manufacturer aliases
SELECT ea.alias, m.name AS canonical
FROM entity_alias ea JOIN manufacturer m ON ea.entity_id = m.id
WHERE ea.entity_type = 'manufacturer';
```

### Common Name Variants
- "Hornady" / "Hornady Inc" / "Hornady Inc." / "Hornady Manufacturing"
- "Sierra" / "Sierra Bullets" / "Sierra Bullets, L.L.C."
- "Nosler" / "Nosler Inc" / "Nosler, Inc."
- "Barnes" / "Barnes Bullets"

When adding data: always resolve through `EntityAlias` + `resolver.py`, never insert with raw extracted names.

### Self-Manufacturing Ammo Brands

These brands manufacture their own bullets — cross-manufacturer linkages for their cartridges are almost always resolver errors:

- **Hornady** — loads only Hornady bullets (ELD-X, ELD Match, SST, CX, InterLock, V-MAX, A-Tip, FTX, GMX, etc.)
- **Nosler** — loads only Nosler bullets (Partition, AccuBond, Ballistic Tip, RDF, Custom Competition, E-Tip)
- **Barnes** — loads only Barnes bullets (TTSX, LRX, TSX). VOR-TX is a cartridge line name, not a bullet type.

These brands commonly load third-party bullets — cross-mfr links may be legitimate but should be verified:

- **Federal** — loads Sierra, Nosler, Berger, Barnes, Speer, Swift, and proprietary (Fusion, Power-Shok, Terminal Ascent, Trophy Bonded)
- **Black Hills** — loads Hornady, Sierra, Berger, Barnes
- **Winchester** — loads Nosler (Ballistic Silvertip = Nosler BST via Combined Technologies), and own bullets (Power-Point, FMJ)
- **Norma** — loads Berger, Sierra (MatchKing in competition lines), and own bullets (ECOSTRIKE, Bondstrike, Tipstrike)

## Fixing Issues: Curation Patches

When QA finds data issues, the fix path is **curation patches** — numbered YAML files in `data/patches/`. All curated records automatically get `data_source="manual"` + `is_locked=True` (protected from pipeline overwrites).

```bash
make curate           # Dry-run — preview changes without writing
make curate-commit    # Apply patches to drift.db
```

### YAML Patch Format

```yaml
patch:
  id: "025_descriptive_name"          # NNN_ prefix, snake_case
  author: agent                        # or "brian"
  date: "2026-03-25"
  description: >
    One-line summary of what this patch fixes and why.
operations:
  - action: <operation_type>
    # ... operation-specific fields
```

### Available Operations

| Action | Use Case | Key Fields |
|--------|----------|------------|
| `create_bullet` | Missing bullet needed for cartridge linkage | `manufacturer`, `name`, `weight_grains`, `bullet_diameter_inches`, `bc_g1`/`bc_g7`, `source_url` |
| `create_cartridge` | Add factory load manually | `manufacturer`, `name`, `caliber`, `bullet`, `bullet_weight_grains`, `muzzle_velocity_fps` |
| `create_caliber` | Missing caliber for cartridge creation | `name`, `bullet_diameter_inches` |
| `create_rifle` | Add rifle model | `manufacturer`, `model`, `chamber` |
| `update_bullet` | Fix BC, weight, diameter, name, source_url | `manufacturer`, `name`, `set: {field: value}` |
| `update_cartridge` | Fix BC, MV, relink bullet, fix weight | `manufacturer`, `name`, `set: {field: value}` |
| `delete_bullet` | Remove bad/duplicate bullet | `manufacturer`, `name`, `reason` (required). Optional `id` for disambiguation. |
| `delete_cartridge` | Remove bad/duplicate cartridge | `manufacturer`, `name`, `reason` (required). Optional `id` for disambiguation. |
| `add_bc_source` | Add audit trail for BC value | `manufacturer`, `bullet_name`, `bc_type`, `bc_value`, `source` |
| `add_entity_alias` | Add name variant for resolution | `entity_type`, `entity_name`, `alias`, `alias_type` |

### Relinking a Cartridge to a Different Bullet

Use `update_cartridge` with `bullet` (and optionally `bullet_manufacturer`) in the `set` dict. The curation system resolves the bullet name to its ID:

```yaml
- action: update_cartridge
  manufacturer: Winchester
  name: "308 Winchester, 168 Grain Ballistic Silvertip"
  set:
    bullet: "30 Caliber 168gr Ballistic Silvertip (50ct)"
    bullet_manufacturer: Nosler          # required if bullet mfr ≠ cartridge mfr
```

### Updatable Fields

**Bullet**: `name`, `alt_names`, `sku`, `weight_grains`, `bullet_diameter_inches`, `bc_g1_published`, `bc_g7_published`, `bc_g1_estimated`, `bc_g7_estimated`, `length_inches`, `sectional_density`, `base_type`, `tip_type`, `construction`, `type_tags`, `used_for`, `is_lead_free`, `product_line`, `source_url`, `overall_popularity_rank`, `lr_popularity_rank`

**Cartridge**: `bc_g1`, `bc_g7`, `bullet`, `bullet_manufacturer`, `bullet_length_inches`, `bullet_weight_grains`, `muzzle_velocity_fps`, `test_barrel_length_inches`, `round_count`, `product_line`, `source_url`, `sku`, `overall_popularity_rank`, `lr_popularity_rank`

### Conventions

- **Numbering**: next patch is one higher than the highest existing file (check `data/patches/`)
- **Idempotent**: safe to re-run — creates skip if record exists, updates skip if already at target value
- **Per-operation savepoints**: one bad operation doesn't roll back the whole patch
- **Name resolution**: uses EntityAlias table, same as pipeline. Use canonical manufacturer names (e.g., "Hornady" not "Hornady Inc.")
- **Always dry-run first**: `make curate` before `make curate-commit`
- **Re-export after curation**: run `make export-production-db` to update the iOS production DB

### Common Fix Patterns

**Missing bullet causing mislink** (most common):
1. `create_bullet` with BCs from manufacturer page
2. `update_cartridge` with `set: {bullet: "new bullet name", bullet_manufacturer: "..."}` to relink

**BC correction**:
1. `update_bullet` with `set: {bc_g1_published: 0.xxx}`
2. `add_bc_source` for audit trail

**Duplicate deletion**:
1. `delete_cartridge` (or `delete_bullet`) with `id` field for disambiguation and `reason` explaining why

## Bullet Name Quality Issues

Common patterns to watch for:
- **ALL CAPS**: "30 CAL 175 GR HPBT MATCHKING" -- should be mixed case
- **Caliber in name**: "7mm 190 Grain Long Range Hybrid Target" -- caliber is redundant (derived from bullet_diameter_inches)
- **Metric weight prefix**: "12,0 g / 185 gr Scenar OTM" -- Lapua convention, metric weight redundant
- **Trademark symbols**: "ELD(R) Match", "ELD® Match" -- should be stripped
- **Pack counts**: "50 ct" or "100/Box" in name
- **Very long names**: >60 chars usually means redundant info included
