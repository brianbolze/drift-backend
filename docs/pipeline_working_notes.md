## Data Pipeline - Working Notes
Issues, weaknesses, quirks and ideas for the data pipeline.

### URL Manifest / Discovery

- **Manufacturer-centric approach works great**: Generated 62 prompts (12 bullet, 18 ammo, 32 rifle manufacturers) covering all calibers. CoWork discovered 449 URLs in first 3 runs (Barnes: 95, Berger: 145, Nosler: 209).
- **Multi-variant pages**: Barnes uses one URL for multiple bullet weights (e.g., LRX page lists 175gr, 190gr, 200gr, 208gr). Extraction engine handles this — prompts say "extract ALL entities from page" and return JSON arrays.
- **Spec location varies**: Nosler has BC data in separate load data section, not on product pages. Extraction will succeed but BCs will be null — items will be flagged for manual review.
- **Automated merge tool**: `scripts/merge_cowork_results.py` adds required fields (priority, source_type, discovery_method) and deduplicates against manifest.
- *TODO*: After bullets complete, review flagged items for missing BCs and cross-reference manufacturer load data if needed.

### Bullets Data Model

- Bullets use `bullet_diameter_inches` (float) — a physical property, not an FK. A .264" bullet works in 6.5 CM, .260 Rem, 6.5 PRC, etc. Compatibility is derived via `bullet.bullet_diameter_inches == caliber.bullet_diameter_inches`. Cartridges and rifles still FK to `caliber_id` / `chamber_id` since those are specific designations.

### Fetch & Reduce (first real run: 71 bullet URLs)

- **70/71 fetched successfully** (1 Hornady 404 — bad URL for 7mm 175gr ELD-X).
- All 70 fetched via plain httpx — no Firecrawl needed for any manufacturer site.
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
- SUPER slow. Constantly running into rate limits. Need to improve approach.
- Need to enforce naming guidelines, right now it's really messy. Examples from first run:
-- `12,0 g / 185 gr Scenar OTM GB432`
-- `30 CAL 175 GR HPBT MATCHKING (SMK)` -- All caps, includes caliber
-- `30 Cal .308 178 gr ELD® Match`
-- `30 Caliber 185 Grain Juggernaut Target Rifle Bullet` -- Really long
-- `338 Caliber 300 Grain Hybrid OTM Tactical Rifle Bullet` -- Really long
-- `7 mm 190 Grain Long Range Hybrid Target Rifle Bullet`