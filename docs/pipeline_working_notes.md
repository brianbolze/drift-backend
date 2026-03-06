## Data Pipeline — Working Notes
Issues, weaknesses, quirks, and ideas for the data pipeline.

*Last updated: March 2026*

---

### Current State (March 2026)

| | Count |
|---|---|
| Manifest URLs | 2,637 (1,803 bullets, 834 cartridges) |
| Fetched pages | 2,370 |
| Extracted | 2,118 |
| **DB: Manufacturers** | **86** |
| **DB: Calibers** | **116** |
| **DB: Bullets** | **547** |
| **DB: BulletBCSources** | **679** |
| **DB: Cartridges** | **237** |
| **DB: Rifles** | **0** (no rifle URLs in manifest yet) |

Last store commit stats (bullets): 78 created, 790 matched, 523 flagged.
Last store commit stats (cartridges): 8 created, 437 matched, 21 updated, 363 flagged.

### Validation

`scripts/manifest_validate.py` cross-checks manifest metadata against DB records (joined on `source_url`). Latest run:
- 0 manufacturer mismatches, 0 caliber mismatches, 0 diameter mismatches
- 1 weight mismatch (CoWork agent error on 17 Cal NTX: wrote 5gr, actual 15.5gr)
- 7 zero-velocity cartridges (Hornady International pages don't publish velocity)
- 0 BC data loss or value mismatches

---

### URL Manifest / Discovery

- **Manufacturer-centric approach works great**: CoWork discovered 2,637 URLs across ~30 manufacturers.
- **Two manifest files**: `url_manifest.json` (bullets) and `url_manifest_cartridges.json` (cartridges + some overlapping bullet entries). Merge/dedup is handled by `scripts/merge_cowork_results.py`.
- **Multi-variant pages**: Barnes uses one URL for multiple bullet weights (e.g., LRX page lists 175gr, 190gr, 200gr, 208gr). Extraction engine handles this — prompts say "extract ALL entities from page" and return JSON arrays.
- **Spec location varies**: Nosler has BC data in separate load data section, not on product pages. Extraction will succeed but BCs will be null — items flagged for manual review.

### Bullets Data Model

- Bullets use `bullet_diameter_inches` (float) — a physical property, not an FK. A .264" bullet works in 6.5 CM, .260 Rem, 6.5 PRC, etc. Compatibility is derived via `bullet.bullet_diameter_inches == caliber.bullet_diameter_inches`. Cartridges and rifles still FK to `caliber_id` / `chamber_id` since those are specific designations.

### Fetch & Reduce

- 2,370/2,637 fetched successfully. All via plain httpx — no Firecrawl needed.
- Reduction quality varies wildly by manufacturer:

| Manufacturer | Reduced Size | Under 30KB Target? | Notes |
|---|---|---|---|
| Lapua | ~27KB | ✅ Yes | Cleanest HTML of all manufacturers |
| Hornady | 23-53KB | Most yes, A-Tip pages no | Angular SPA — reducer struggles with template content |
| Berger Bullets | ~35KB | Barely over | 87% reduction ratio — good but just misses target |
| Hammer Bullets | ~37KB | Slightly over | Consistent sizing |
| Sierra Bullets | ~70KB | ❌ No | Very bloated HTML, consistent 37% reduction |
| Nosler | ~69KB | ❌ No | Similar to Sierra |
| Barnes Bullets | 69-80KB | ❌ No | Multi-weight pages are bigger |
| Cutting Edge | ~200KB | ❌ Way over | Massively bloated — worst of all sites |

- The 30KB reducer target was tuned for Haiku's context window. Pages over target will still extract but cost more tokens. The Sierra/Nosler/Barnes ~70KB pages are 2-3x over but should still fit in context. Cutting Edge at 200KB is a real problem.
- *Idea*: Per-manufacturer reducer hints (e.g. CSS selectors for the product spec section) could dramatically improve reduction for bloated sites.


### Extraction
- Batch extraction via Anthropic Batch API (`pipeline_extract_batch.py`) is the primary method — 50% cheaper than sync. Sync fallback (`pipeline_extract.py`) available with exponential backoff retries.
- Bullet name normalization still inconsistent across manufacturers. Examples from DB:
  - `12,0 g / 185 gr Scenar OTM GB432` (Lapua — includes metric weight)
  - `30 CAL 175 GR HPBT MATCHKING (SMK)` (Sierra — all caps, includes caliber)
  - `30 Cal .308 178 gr ELD® Match` (Hornady — includes caliber and registered trademark)
  - `7 mm 190 Grain Long Range Hybrid Target Rifle Bullet` (Berger — very long)

#### Cartridge extraction issues (resolved)
- 26 Pydantic validation failures: `bullet_weight_grains`, `muzzle_velocity_fps`, `caliber` were non-nullable but LLM returns null for missing fields. **Fix**: made these fields `ExtractedValue[T | None]` in schemas.py.
- 1 JSON parse error: LLM copied raw JSON-LD from Federal page into `source_text`, breaking the JSON structure. **Fix**: added extraction prompt rule to keep `source_text` under 80 chars, plain text only.

### Resolution

The resolver (`src/drift/pipeline/resolution/resolver.py`) has a tiered matching strategy for each entity type.

#### Manufacturer matching
- Uses `_normalize()` (lowercase, strip punctuation, collapse whitespace) plus exact match against `Manufacturer.name`, `Manufacturer.alt_names`, and `EntityAlias` table.
- Fuzzy tier uses word-overlap scoring for cases like "Hornady Manufacturing" vs "Hornady".

#### Caliber matching
- **Leading period mismatch**: DB uses `.308 Winchester`, LLM extracts `308 Win`. A caliber-specific `_normalize_caliber()` strips leading periods. Fixed ~144 cartridge failures.
- **EntityAlias table**: `resolve_caliber()` now checks `caliber.name`, `caliber.alt_names`, and `EntityAlias` table (40 curated aliases).
- **Remaining caliber gaps (~145)**: Mostly pistol calibers (9mm Luger, .357 Mag, .40 S&W), shotgun gauges (12 GA), and newer/exotic rifle calibers not seeded in the DB (.338 ARC, .22 ARC, .360 Buckhammer, etc.).

#### Bullet matching (from cartridge resolution)
- **Cross-manufacturer matching**: Factory ammo uses bullets from other companies (e.g., Federal loads Sierra MatchKings). `match_bullet()` passes `manufacturer_id=None` for cartridge bullet lookups. Diameter + weight narrow candidates; name picks the best.
- **Containment-based name scoring**: `_bullet_name_score()` strips noise words (gr, cal, bullet, manufacturer names, etc.) and checks what fraction of the extracted keywords appear in the DB name. Handles parenthetical expansions ("SST (Super Shock Tip)" → scores "SST" alone).
- **Abbreviation expansion**: Common abbreviations are expanded before scoring (HPBT → Hollow Point Boat Tail, OTM → Open Tip Match, SMK → Sierra MatchKing, etc.). See `_ABBREVIATION_MAP` in resolver.py.
- **Thresholds**: Tier 2 composite key (weight + name) requires `name_score > 0.55`. This prevents false matches like ELD-X → ELD Match at the same weight (score 0.5 falls below threshold).
- **Best-match selection**: Composite key tier picks the highest-scoring candidate, not the first above threshold.

#### Known issues & remaining gaps
- **~523 flagged bullets**: Mix of genuinely missing bullet types (V-MAX, Trophy Copper, Swift A-Frame, generic names like "Jacketed Soft Point"), low-confidence matches, and missing diameter/manufacturer refs.
- **~363 flagged cartridges**: ~212 low-confidence bullet rejections (bullet exists in DB but name match is weak), ~145 unresolved caliber refs (calibers not in DB), ~6 misc.
- **4 MatchKing→Nosler HPBT false matches**: DB completeness issue — Sierra MatchKing bullets are missing at certain weights, so HPBT abbreviation expansion + weight match hits Nosler HPBT instead. Will self-correct as Sierra bullets are added.
- **99 existing cartridges with wrong `bullet_id`**: From earlier pipeline commits before abbreviation expansion. Re-running `pipeline_store.py --commit` would fix these via the update path, but the correct bullets need to exist in DB first.
- **7 zero-velocity cartridges**: Hornady International product pages don't publish muzzle velocity. Not fixable at extraction level — need supplementary data source.

### Curation & Locking (March 2026)

Bullet, cartridge, and rifle_model tables now have `data_source` and `is_locked` columns (migration `d4e5f6a7b8c9`).

- `data_source` (str): "pipeline" (default), "cowork", or "manual" — tracks provenance
- `is_locked` (bool): when True, `pipeline_store.py` skips the record entirely (no updates)
- Extraction JSON envelope supports `"data_source": "cowork"` to tag CoWork-sourced entities
- All existing rows backfilled as `data_source='pipeline', is_locked=0`

Workflow: fix a record manually → set `is_locked = 1, data_source = 'manual'` → pipeline won't touch it again.

### Useful commands

```bash
# Pipeline status
make pipeline-status

# Run extraction (batch or sync)
make pipeline-extract-batch        # Anthropic batch API — cheaper
PYTHONPATH=src python scripts/pipeline_extract.py --limit 10  # sync, for debugging

# Store (resolve + write)
make pipeline-store                # dry-run: resolve and report
make pipeline-store-commit         # actually write to DB

# Manifest cross-validation
PYTHONPATH=src python scripts/manifest_validate.py          # stdout report
PYTHONPATH=src python scripts/manifest_validate.py --json   # + write JSON report

# Quality checks before committing code
make format && make lint && make test
```