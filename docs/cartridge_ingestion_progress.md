# Cartridge Ingestion — Session Progress

**Date:** 2026-03-18
**Status:** In progress — fetch running, resume tomorrow

## What Got Done

### Phase 0: Schema Migration (DONE)
- Added `overall_popularity_rank` + `lr_popularity_rank` (nullable INTEGER) to `bullet` and `cartridge` tables
- Alembic migration: `f1a2b3c4d5e6` (replaces old single `popularity_rank` column)
- Curation allowlists updated in `src/drift/curation.py`
- All 361 tests pass

### Phase 1: Popularity Research (DONE)
- Findings in `docs/popularity_research_findings.md`
- Sources: Midway USA popularity sort, PrecisionRifleBlog factory ammo testing, editorial reviews, PRS community data, Sniper's Hide forums
- Per-caliber top-15 rankings for .308, 6.5 CM, .223, .300 WM, .30-06, .270, 6.5 PRC, 7mm PRC, .338 Lapua
- Gap analysis identifying missing high-priority cartridges by manufacturer
- Bullet coverage confirmed excellent — all top 20 already in DB

### Phase 2: Berger Re-extraction (DONE)
- 34 Berger loaded ammo pages were already fetched but extracted as `bullet` — flipped to `cartridge`
- Updated `entity_type` in reduced JSON files, deleted stale extractions, re-ran batch extract
- **31 Berger cartridges stored** across .223, .260 Rem, 6mm CM, 6.5 CM, .300 NM, .300 WM, .308, .338 Lapua

### Phase 3A: Pipeline Ingestion — Barnes/Nosler/Winchester (IN PROGRESS)
- Firecrawl mapped all three manufacturer sites:
  - Barnes: 44 rifle ammo URLs (`data/pipeline/firecrawl_map_barnes_ammo.json`)
  - Nosler: 246 rifle ammo URLs (`data/pipeline/firecrawl_map_nosler_ammo.json`)
  - Winchester: 230 rifle ammo URLs (`data/pipeline/firecrawl_map_winchester_ammo.json`)
- All 520 URLs added to `data/pipeline/url_manifest_cartridges.json`
- **Fetch completed:** 520 fetched, 0 failed. All pages ready for extraction.

### Phase 3B: Black Hills Curation (DONE)
- Patch `015_black_hills_cartridges.yaml` — 22 cartridges committed
- Covers: .308 Win (11), .223 Rem (5), 6.5 CM (3), .338 Lapua (2), .300 WM (1)
- Source: black-hills.com product pages (muzzle velocities confirmed)

## What's Left

### Resume Steps (in order)

1. **Run extraction** — `set -a && source .env && set +a && python3 scripts/pipeline_extract.py --batch` (fetch already completed — 520/520 done)
3. **Run store** — `make pipeline-store` (dry-run first), then `make pipeline-store-commit`
4. **Build curation patches** for remaining manufacturers:
   - **Norma** — Golden Target + BondStrike (SPA pages, need manual research like Norma bullets gap-fill)
   - **Lapua** — Scenar .308 + .338 Lapua only (~5 loads, tiny catalog)
   - **Sig Sauer** — Elite Match + Elite Hunter Tipped (~5-10 loads)
   - **Remington** — Core-Lokt Tipped (~10 loads)
5. **Phase 4: Apply popularity rankings** — Build a curation patch using `update_cartridge`/`update_bullet` ops to set `overall_popularity_rank` and `lr_popularity_rank` on top ~50 of each, per the rankings in `docs/popularity_research_findings.md`
6. **Export production DB** — `make export-production-db`

## Current DB State

| Manufacturer | Cartridges |
|---|---|
| Hornady | 156 |
| Federal | 124 |
| Berger Bullets | 31 |
| Black Hills Ammunition | 22 |
| **Total** | **333** |

Target: ~500-550 after all ingestion complete.

## Key Files Modified/Created This Session

- `alembic/versions/f1a2b3c4d5e6_split_popularity_rank_into_overall_and_.py` — migration
- `src/drift/models/bullet.py` — new rank columns
- `src/drift/models/cartridge.py` — new rank columns
- `src/drift/curation.py` — rank fields added to update allowlists
- `data/patches/015_black_hills_cartridges.yaml` — Black Hills cartridges
- `data/pipeline/url_manifest_cartridges.json` — +520 entries for Barnes/Nosler/Winchester
- `data/pipeline/firecrawl_map_barnes_ammo.json` — Barnes URL map
- `data/pipeline/firecrawl_map_nosler_ammo.json` — Nosler URL map
- `data/pipeline/firecrawl_map_winchester_ammo.json` — Winchester URL map
- `docs/cartridge_coverage_plan.md` — coverage plan with pipeline inventory
- `docs/popularity_research_findings.md` — popularity rankings + gap analysis
