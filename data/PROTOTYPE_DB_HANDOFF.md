# Prototype Database Handoff — `drift_prototype.db`

**Date:** 2026-03-10
**File:** `data/drift_prototype.db` (1.4 MB, SQLite)
**Source:** Sanitized copy of the production pipeline DB

## What's In It

| Table | Rows | Description |
|---|---|---|
| `caliber` | 117 | Cartridge calibers (.308 Win, 6.5 CM, etc.) |
| `bullet` | 640 | Component bullets with BC data |
| `cartridge` | 263 | Factory-loaded ammunition with muzzle velocity |
| `manufacturer` | 86 | Ammo/bullet manufacturers |
| `bullet_bc_source` | 805 | Audit trail for BC observations (not needed for prototype) |
| `entity_alias` | — | Name normalization (not needed for prototype) |

## Tables You Care About

### `caliber`
The starting point for the flow. User picks a caliber, everything else follows.

Key columns:
- `name` — display name (e.g., "6.5 Creedmoor", ".308 Winchester")
- `bullet_diameter_inches` — used to find matching bullets (e.g., 0.264 for 6.5mm)
- `action_length` — "short", "long", or NULL. Useful for bolt-action defaults.
- `saami_test_barrel_length_inches` — SAAMI standard test barrel length for the caliber

43 of 117 calibers have zero cartridge data. These are less common calibers and will naturally exercise the sparse-data path.

### `bullet`
Component bullets. Queried by diameter + weight to resolve bullet type and BC.

Key columns:
- `bullet_diameter_inches` — match to `caliber.bullet_diameter_inches`
- `weight_grains` — bullet weight
- `product_line` — bullet family (e.g., "ELD Match", "MatchKing", "Hybrid Target")
- `bc_g1_published`, `bc_g7_published` — ballistic coefficients. 604/640 have at least G1.
- `tip_type`, `base_type`, `construction` — bullet construction details (partially populated)
- `manufacturer_id` → `manufacturer.name`

### `cartridge`
Factory-loaded ammunition. Provides grain weight options and muzzle velocity per caliber.

Key columns:
- `caliber_id` → `caliber.id`
- `bullet_weight_grains` — the loaded bullet weight
- `muzzle_velocity_fps` — all records have MV > 0 in this export
- `test_barrel_length_inches` — barrel length the MV was measured at (NULL for some)
- `bullet_id` → `bullet.id` — **NULLABLE.** See note below.
- `bc_g1`, `bc_g7` — cartridge-level BC (sometimes present even when bullet_id is NULL)
- `manufacturer_id` → `manufacturer.name`

**Important: `bullet_id` is nullable in this export.** ~97 cartridges have `bullet_id = NULL` because our pipeline linked them to the wrong bullet. Their weight + MV + caliber data is correct and usable — the bullet linkage just isn't trustworthy for those records. See "Recommended Query Pattern" below.

### `manufacturer`
- `name` — display name ("Hornady", "Federal", "Berger Bullets", etc.)
- `website_url`, `country`

## Recommended Query Patterns

### 1. Get grain weight options + velocity for a caliber

This is the core query for populating defaults. Works with all 263 cartridges regardless of bullet_id.

```sql
SELECT
  CAST(c.bullet_weight_grains AS INT) AS weight_gr,
  COUNT(*) AS load_count,
  CAST(AVG(c.muzzle_velocity_fps) AS INT) AS avg_mv,
  MIN(c.muzzle_velocity_fps) AS min_mv,
  MAX(c.muzzle_velocity_fps) AS max_mv
FROM cartridge c
JOIN caliber cal ON c.caliber_id = cal.id
WHERE cal.name = '6.5 Creedmoor'
GROUP BY CAST(c.bullet_weight_grains AS INT)
ORDER BY load_count DESC;
```

Example result for 6.5 Creedmoor:

| weight_gr | load_count | avg_mv | min_mv | max_mv |
|---|---|---|---|---|
| 140 | 3 | 2693 | 2675 | 2715 |
| 130 | 3 | 2833 | 2800 | 2875 |
| 143 | 2 | 2700 | 2700 | 2700 |
| 120 | 2 | 2912 | 2900 | 2925 |
| 95 | 2 | 3300 | 3300 | 3300 |
| 147 | 1 | 2695 | 2695 | 2695 |
| 129 | 1 | 2810 | 2810 | 2810 |

### 2. Get bullet types + BC for a caliber + weight

Query the bullet table directly by diameter, not through the cartridge FK.

```sql
SELECT b.name, b.weight_grains, b.product_line,
  b.bc_g1_published, b.bc_g7_published,
  m.name AS manufacturer
FROM bullet b
JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE b.bullet_diameter_inches = cal.bullet_diameter_inches  -- e.g., 0.264
  AND b.weight_grains BETWEEN :weight - 1 AND :weight + 1   -- float tolerance
ORDER BY b.bc_g7_published DESC NULLS LAST;
```

For 6.5mm / 140gr, this returns options like:
- Nosler RDF 140gr — G7 0.330
- Berger Hybrid Target 140gr — G7 0.311
- Sierra MatchKing 140gr — G7 0.264
- Hornady BTHP Match 140gr — G1 0.580
- etc.

### 3. Get MV adjusted for barrel length

Cartridges include `test_barrel_length_inches` when known. If the user's barrel length differs, the standard heuristic is ~25 fps per inch of difference.

```sql
SELECT c.name, c.muzzle_velocity_fps, c.test_barrel_length_inches,
  -- Adjusted MV for a 22" barrel (example)
  c.muzzle_velocity_fps + CAST((22.0 - c.test_barrel_length_inches) * 25 AS INT) AS adjusted_mv
FROM cartridge c
JOIN caliber cal ON c.caliber_id = cal.id
WHERE cal.name = '6.5 Creedmoor'
  AND c.test_barrel_length_inches IS NOT NULL
  AND CAST(c.bullet_weight_grains AS INT) = 140;
```

### 4. Browse all calibers with load data availability

For showing which calibers have rich vs. sparse data in the UI:

```sql
SELECT cal.name, cal.bullet_diameter_inches, cal.action_length,
  COUNT(c.id) AS load_count
FROM caliber cal
LEFT JOIN cartridge c ON c.caliber_id = cal.id
GROUP BY cal.id
ORDER BY load_count DESC;
```

## Caliber Coverage at a Glance

Top calibers and their data richness:

| Caliber | Loads | Full Bullet Link | MV+Weight Only |
|---|---|---|---|
| .308 Win | 19 | 14 | 5 |
| 6.5 CM | 14 | 13 | 1 |
| .30-06 | 14 | 10 | 4 |
| .223 Rem | 13 | 9 | 4 |
| .300 WM | 11 | 6 | 5 |
| .270 Win | 10 | 8 | 2 |
| .300 BLK | 8 | 4 | 4 |
| 6.5 PRC | 8 | 7 | 1 |
| .224 Valkyrie | 6 | 3 | 3 |
| 6.5 Grendel | 6 | 3 | 3 |
| 6mm CM | 6 | 6 | 0 |
| 7mm PRC | 5 | 3 | 2 |
| .338 Lapua | 4 | 4 | 0 |
| 6mm ARC | 4 | 4 | 0 |

"Full Bullet Link" = cartridge has a verified bullet_id you can follow to get BC.
"MV+Weight Only" = cartridge has good velocity and weight data, but no bullet link — resolve BC from the bullet table by diameter + weight instead.

## What Was Sanitized (vs. Production)

This is a cleaned export. Changes from the production `drift.db`:

1. **97 cartridges**: `bullet_id` set to NULL (were linked to wrong-weight bullets; their MV/weight/caliber data is correct)
2. **12 cartridges deleted**: zero muzzle velocity (7 Hornady International pages that don't publish MV + 5 Federal placeholder records with no data)
3. **3 cartridges fixed**: barrel length corrected from 9.45" to 24.0" (Hornady International metric conversion bug)
4. **1 bullet deleted**: Sierra TMK duplicate with wrong diameter (0.220 instead of 0.224)

## Known Limitations

- **No rifle model data** — the `rifle_model` table exists but has 0 rows. The flow cannot depend on it.
- **Bullet type tags are inconsistent** — `product_line` is the most reliable field for bullet family. The `tip_type`/`base_type`/`construction` columns are partially populated.
- **Bullet names contain cosmetic noise** — trademark symbols (Hornady), pack counts (Nosler), metric weight prefixes (Lapua). Fine for prototype, will be cleaned later.
- **43 calibers have zero load data** — they still have caliber specs (diameter, action length). Use these for testing the sparse-data flow.
- **BC coverage** — 604/640 bullets have at least G1 published. 188/640 have G7. The 36 without any BC are mostly Cutting Edge and Lehigh (niche manufacturers).
