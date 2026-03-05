## Data Pipeline - Working Notes
Issues, weaknesses, quirks and ideas for the data pipeline.

### URL Manifest / Discovery

- *Idea*: Manually curate "url schemes" per manufacturer — what do their product pages look like? What about their category / product-family pages? Could use this to feed the URL manifest step, validate URLs, and eventually auto-discover new products by crawling category pages.
- A Claude Code research agent (Task tool) without web/browser permissions was useless for URL discovery — it just mined our codebase and guessed URL patterns. A Cowork agent with actual Chrome access was far more effective (70/71 valid URLs).
- The Cowork agent also surfaced real domain knowledge: Hornady's .25 cal 110gr ELD Match doesn't exist (it's 134gr), the Berger 200gr LRHT is discontinued (replaced by 220gr/245gr), Lapua's 140gr Scenar-L may only exist as factory ammo not component bullets.
- Barnes uses multi-weight pages (one URL, multiple bullet weights via dropdown). The extraction prompt asks for all entities on a page, so this should work — but worth watching.

### Bullets Data Model

- Bullets are FK'd to a specific `caliber_id` (e.g. "6.5 Creedmoor"), but physically a bullet works in any cartridge sharing that diameter. The `caliber_id` on bullet effectively acts as a "diameter group reference" — the cartridge table has its own `caliber_id`. Not a bug, but potentially confusing.

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
- Need to enforce naming guidelines, right now it's really messy. Examples from first run:
-- `12,0 g / 185 gr Scenar OTM GB432`
-- `30 CAL 175 GR HPBT MATCHKING (SMK)` -- All caps, includes caliber
-- `30 Cal .308 178 gr ELD® Match`
-- `30 Caliber 185 Grain Juggernaut Target Rifle Bullet` -- Really long
-- `338 Caliber 300 Grain Hybrid OTM Tactical Rifle Bullet` -- Really long
-- `7 mm 190 Grain Long Range Hybrid Target Rifle Bullet`