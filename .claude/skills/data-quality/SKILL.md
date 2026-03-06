---
name: data-quality
description: Data quality checks, BC validation, manufacturer resolution, and bullet name normalization for the ballistics database
---

# Data Quality

## Quick Checks

```bash
python scripts/describe_db.py              # Schema + row counts
make pipeline-status                       # Pipeline stage counts
python scripts/manifest_validate.py        # Manifest vs DB cross-check
python scripts/manifest_validate.py --json # + write JSON report
```

## BC Range Expectations

| Drag Model | Expected Range | Typical Values |
|---|---|---|
| G1 | 0.100 - 0.800 | Most bullets: 0.2-0.6 |
| G7 | 0.050 - 0.450 | Most bullets: 0.1-0.35 |

Values outside these ranges are almost certainly extraction errors. Common issues:
- G1/G7 values swapped (G7 value stored as G1)
- Decimal point errors (0.473 recorded as 4.73)
- Sectional density stored instead of BC

## Key SQL Queries

### Referential Integrity
```sql
-- Bullets without a manufacturer
SELECT id, name FROM bullet WHERE manufacturer_id NOT IN (SELECT id FROM manufacturer);

-- Cartridges referencing non-existent bullets
SELECT c.id, c.name FROM cartridge c LEFT JOIN bullet b ON c.bullet_id = b.id WHERE b.id IS NULL AND c.bullet_id IS NOT NULL;

-- BulletBCSources without a bullet
SELECT id, bullet_id FROM bullet_bc_source WHERE bullet_id NOT IN (SELECT id FROM bullet);
```

### Cross-Entity Consistency
```sql
-- Cartridge bullet_weight vs linked bullet weight (mismatches)
SELECT c.id, c.name, c.bullet_weight_grains AS cart_wt, b.weight_grains AS bullet_wt
FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
WHERE c.bullet_weight_grains IS NOT NULL AND b.weight_grains IS NOT NULL
AND ABS(c.bullet_weight_grains - b.weight_grains) > 1.0;

-- Cartridge caliber diameter vs linked bullet diameter (mismatches)
SELECT c.id, c.name, b.bullet_diameter_inches AS bullet_diam, cal.bullet_diameter_inches AS cal_diam
FROM cartridge c
JOIN bullet b ON c.bullet_id = b.id
JOIN caliber cal ON c.caliber_id = cal.id
WHERE ABS(b.bullet_diameter_inches - cal.bullet_diameter_inches) > 0.002;
```

### Duplicate Detection
```sql
-- Potential duplicate bullets (same manufacturer + weight + diameter)
SELECT manufacturer_id, weight_grains, bullet_diameter_inches, COUNT(*) AS cnt,
       GROUP_CONCAT(name, ' | ') AS names
FROM bullet
GROUP BY manufacturer_id, weight_grains, bullet_diameter_inches
HAVING cnt > 1;
```

### Coverage
```sql
-- Bullets missing any BC data
SELECT b.id, b.name, m.name AS mfr
FROM bullet b JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE b.id NOT IN (SELECT DISTINCT bullet_id FROM bullet_bc_source);

-- Manufacturer bullet counts
SELECT m.name, COUNT(b.id) AS bullet_count
FROM manufacturer m LEFT JOIN bullet b ON m.id = b.manufacturer_id
GROUP BY m.id ORDER BY bullet_count DESC;
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
