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
-- 7 known zeros are Hornady International pages that don't publish MV
SELECT c.id, c.name, c.muzzle_velocity_fps, m.name AS mfr
FROM cartridge c JOIN manufacturer m ON c.manufacturer_id = m.id
WHERE c.muzzle_velocity_fps <= 0
   OR c.muzzle_velocity_fps > 5000;
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

-- Potential duplicate cartridges (same manufacturer + caliber + bullet weight)
SELECT m.name AS mfr, cal.name AS caliber, c.bullet_weight_grains,
       COUNT(*) AS cnt, GROUP_CONCAT(c.name, ' | ') AS names
FROM cartridge c
JOIN manufacturer m ON c.manufacturer_id = m.id
JOIN caliber cal ON c.caliber_id = cal.id
GROUP BY c.manufacturer_id, c.caliber_id, c.bullet_weight_grains
HAVING cnt > 1
ORDER BY cnt DESC;
```

### BC Validation
```sql
-- Likely BC extraction errors (outside hard error thresholds)
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

## Bullet Name Quality Issues

Common patterns to watch for:
- **ALL CAPS**: "30 CAL 175 GR HPBT MATCHKING" -- should be mixed case
- **Caliber in name**: "7mm 190 Grain Long Range Hybrid Target" -- caliber is redundant (derived from bullet_diameter_inches)
- **Metric weight prefix**: "12,0 g / 185 gr Scenar OTM" -- Lapua convention, metric weight redundant
- **Trademark symbols**: "ELD(R) Match", "ELD\u00ae Match" -- should be stripped
- **Pack counts**: "50 ct" or "100/Box" in name
- **Very long names**: >60 chars usually means redundant info included

## QA Reports

Daily automated reports: `data/data_qa/report_YYYY-MM-DD.md`
QA prompt spec: `data/data_qa/PROMPT.md`

Severity levels:
- **CRITICAL**: Wrong BC values, incorrect entity linkages, diameter mismatches
- **WARNING**: Missing BC data, potential duplicates, implausible values
- **INFO**: Cosmetic issues (name quality), expected gaps, coverage stats
