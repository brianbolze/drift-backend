# Handoff: Missing Bullet Grain Weight Variants

## Problem

100 of 270 cartridges (37%) are linked to the wrong bullet because the correct grain weight variant doesn't exist in the DB. The resolver falls back to closest-match, causing mismatches up to 100gr.

## Root Cause

The bullets were never added to the manifest, so they were never fetched/extracted/stored. There is no pipeline bug — the extraction and store logic work fine for all bullet types.

## Two Buckets

### Bucket 1: Ammo-Only Bullets (~10) → Curation Patches

These don't exist as reloading components — no manufacturer product page to scrape. They need `data/patches/` YAML entries.

| Bullet | Why |
|--------|-----|
| Hornady .224 55gr CX | Components are 50/65/70gr only |
| Hornady .172 17gr V-MAX | Smallest component is 20gr |
| Hornady .224 30gr V-MAX | .22 WMR only, not sold separately |
| Hornady .357 150gr InterLock | .350 Legend only, component is 170gr |
| Hornady .308 155gr FTX | Critical Defense, not sold as component |
| Barnes .224 78gr TSX | Doesn't exist; max .224 TSX is 70gr |
| Federal .264 120gr Fusion | 6.5 Grendel ammo-only |
| Federal .277 115gr Fusion | 6.8 SPC ammo-only |
| Federal .284 150gr Fusion | 7mm Rem Mag ammo-only |
| Federal .284 170gr Terminal Ascent | 7mm PRC ammo-only |

For these, you have two options:
- **Create stub bullets** via curation patch (weight, diameter, manufacturer, `data_source="manual"`) so the resolver can link cartridges correctly. BC data may be available from the ammo product page or CoWork research.
- **Re-link cartridges** to the closest real component bullet and accept the weight mismatch as known/expected for factory-ammo-only loads.

### Bucket 2: Component Bullets (~40 combos) → Pipeline

These have manufacturer product pages. The CoWork research output is at:
```
data/pipeline/missing_grain_weights_research.json   # 64 entries
```

**Workflow:**
```bash
# 1. Merge CoWork results into manifest
python scripts/merge_cowork_results.py data/pipeline/missing_grain_weights_research.json --dry-run
python scripts/merge_cowork_results.py data/pipeline/missing_grain_weights_research.json

# 2. Run pipeline
make pipeline-fetch
make pipeline-extract
make pipeline-store          # dry-run first!
make pipeline-store-commit   # commit to DB

# 3. Verify mismatches decreased
python3 -c "
import sqlite3
conn = sqlite3.connect('data/drift.db')
ct = conn.execute('''
  SELECT COUNT(*) FROM cartridge c JOIN bullet b ON c.bullet_id = b.id
  WHERE ABS(c.bullet_weight_grains - b.weight_grains) > 1.0
''').fetchone()[0]
print(f'Weight mismatches: {ct} (was 100)')
"
```

## Key Priority Tiers (from CoWork research prompt)

1. **Hornady CX** — 10 weight variants, 20 cartridge mismatches
2. **Hornady V-MAX** — 9 variants, 14 mismatches
3. **Hornady ELD-X** — 4 variants, 11 mismatches
4. **Hornady SST** — 5 variants, 10 mismatches
5. **Barnes TSX** — 8 variants, 9 mismatches
6. **Federal Fusion + Trophy Bonded Tip** — 7 variants, 10 mismatches
7. **Hornady misc** (InterLock, ECX, FTX, Sub-X, ELD Match) — ~10 one-offs
8. **Federal Terminal Ascent** — 2 variants, 4 mismatches
9. **Large bore** (.458 500gr) — 2 mismatches

## Files to Know

| File | Purpose |
|------|---------|
| `data/pipeline/missing_grain_weights_research.json` | CoWork URL research output (64 entries) |
| `data/cowork_prompts/grain_weight_gap_research.md` | Original research prompt with all gaps enumerated |
| `data/data_qa/report_2026-03-07.md` | Latest QA report (C1 = this issue) |
| `data/patches/` | YAML curation patches (numbered, idempotent) |
| `src/drift/curation.py` | Curation patch applier |
| `scripts/merge_cowork_results.py` | Merges CoWork JSON into `url_manifest.json` |
| `TODO.md` | Tech debt tracker with related items |

## Other Open Issues (not this task, but FYI)

- **C5/C7**: Two Hornady International cartridges with metric barrel length (9.45" should be 24") — need curation patches
- **C6**: Bad Sierra TMK record (b137e0fa) needs deletion via curation patch
- **W1**: 7 cartridges with MV=0 (Hornady Intl pages don't publish velocity)
- **W2**: 6 bullets missing all BC data (Lapua/Lehigh don't publish)
- **.350 Legend diameter**: DB has 0.357" which is correct — CoWork note about 0.355" was wrong (that's 9mm)

## Curation Patch Format

See existing patches in `data/patches/` and `src/drift/curation.py` for the YAML schema. Key ops: `create_bullet`, `update_cartridge`, `add_bc_source`, `add_entity_alias`. All created records get `data_source="manual"` + `is_locked=True` automatically. Run `make curate` for dry-run, `make curate-commit` to apply.
