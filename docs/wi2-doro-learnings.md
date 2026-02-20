**# WI-2: What We Learned at Doro (and How It Applies Here)**

***\*Context:\**** This document is for the engineers working on the Ammo & Firearms Data Library. It distills lessons from the Doro codebase — a structured data pipeline we built for PE deal intelligence — into concrete suggestions for the RangeFinder data model, pipeline architecture, and search system. Doro solved a structurally similar problem (scrape messy web sources, extract structured specs, deduplicate across sources, serve fast search), and several of its patterns transfer directly.

Read this alongside `wi2_goals_and_strategy.md`. That doc has the right product instincts. This one fills in the engineering details from having built something like it before.

\---

**## The Core Insight: AI at Ingestion, Structure for Retrieval**

Doro's most important architectural decision was moving AI processing to ingestion time rather than query time. Instead of embedding everything and hoping an LLM figures out structure on every search, we used LLMs to extract, classify, and normalize data **once** when it enters the system. Queries then hit pre-structured, pre-reconciled data — fast, deterministic, and auditable.

This maps directly to the ammo pipeline. Manufacturer product pages are messy — specs buried in marketing copy, inconsistent formats across manufacturers, JS-rendered tables, PDF spec sheets. The pipeline should use LLMs to extract structured fields (BC, MV, bullet weight, caliber) at scrape time, reconcile conflicts across sources, and export a clean SQLite snapshot. The on-device search never touches an LLM — it queries pre-structured data.

This is the difference between "search that works offline in 50ms" and "search that needs a network call and 2 seconds."

\---

**## Data Model Feedback**

The four-entity model (Caliber, Bullet, Cartridge, RifleModel) is the right call. A few observations from having built a similar multi-entity system:

**### On the Bullet-as-Canonical-Unit Decision**

This is correct and important. The Bullet entity is the single source of truth for projectile properties, and the Cartridge entity combines a Bullet's ballistic properties with loading-specific data (MV, test barrel length). This is the right decomposition.

***\*One thing to watch:\**** The link between a Cartridge and its Bullet is inferred, not declared by manufacturers. The goals doc acknowledges this. At Doro, we learned that inferred entity links need their own confidence tracking. I'd suggest:

\```

cartridge.bullet_id          -- FK to Bullet

cartridge.bullet_match_confidence  -- Float 0-1

cartridge.bullet_match_method      -- "exact_sku" | "name_weight_caliber" | "manual" | "llm_inferred"

\```

When the match method is `name_weight_caliber` (the common case), confidence might be 0.90. When it's `exact_sku` (rare — manufacturers don't usually publish this), it's 1.0. When it's `manual` (human review), it's 0.98. This metadata costs almost nothing to store and saves you when a match turns out to be wrong — you can query "all cartridges with bullet_match_confidence < 0.95" for review.

**### On the Caliber Entity**

The decision to store .308 Win and 7.62x51 NATO as separate records with cross-reference aliases is correct. At Doro, we handled similar ambiguity with company entities (e.g., "Alphabet" vs "Google" — same parent, different entities with a relationship). The alias layer resolves the search UX; the data model preserves the distinction.

***\*Suggested addition to the Caliber entity:\****

\```

caliber.military_designation     -- e.g., "7.62x51mm NATO" (nullable)

caliber.commercial_equivalent_id -- FK to another Caliber (nullable, bidirectional)

caliber.saami_designation        -- Official SAAMI name (nullable)

caliber.cip_designation          -- European CIP name (nullable)

\```

This handles the `.223 Rem / 5.56 NATO` and `.308 Win / 7.62x51` cases cleanly without overloading the alias table with relationships that have structural meaning.

**### Should We Use Datapoints? (The Bigger Architectural Question)**

Before getting into BC sources specifically, there's a more fundamental question: should this pipeline have a datapoint layer at all?

***\*What datapoints are in Doro:\**** At Doro, entity records (like `SharedCompany`) are **not** the source of truth — they're materialized caches. The actual source of truth is a table of immutable `DataPoint` records, each representing a single observation from a single source about a single field. A company's employee count isn't a column on the company — it's a query that gathers all `employee_count` datapoints for that company, runs reconciliation logic (weighted by source quality, freshness, and cross-source consistency), and picks the best value.

This architecture exists because Doro had a specific set of problems:

\- Multiple sources per entity that frequently conflicted (LinkedIn says 150 employees, Crunchbase says 200, expert call says 127)

\- Sources of varying and changing reliability (an expert could be discredited after the fact)

\- Need for retroactive correction (re-extract from a source with a better prompt, old datapoints preserved)

\- Complete audit trail requirements (PE firms making $50M decisions need to trace every number)

***\*The honest question for this pipeline:\**** Do you have those problems?

For most ammo fields — ***\*no, not really.\**** A bullet's weight is 140 grains. It's on the manufacturer page. Nobody disputes it. There's one source, and it's authoritative. Storing `bullet_weight_gr = 140.0` directly on the Bullet entity is fine. You don't need an immutable observation layer between "the Hornady page says 140gr" and "the database says 140gr."

For BC values — ***\*yes, absolutely.\**** This is the one field where the Doro datapoint pattern genuinely applies. The Hornady bullet page says G7 BC 0.326. The Hornady ammo page says 0.315 (a known discrepancy — they sometimes round down on ammo pages). Bryan Litz measured it at 0.305. A community member tested at 0.311. These are real, conflicting observations from sources with different reliability. You want to store all of them, know where each came from, and have a principled way to pick the canonical value.

For muzzle velocity — ***\*maybe.\**** Factory MV is measured from a specific test barrel. That's one authoritative source. But if you ever incorporate independent chronograph data or user-reported velocities, you'd want the same multi-source pattern.

***\*My recommendation: Don't implement a general-purpose datapoint layer. Do implement it for BC, and structure other provenance tracking at the entity level.\****

Concretely:

\```

Bullet entity:

​    bc_g1: Float?              -- The "chosen" / canonical G1 BC (what the solver uses)

​    bc_g7: Float?              -- The "chosen" / canonical G7 BC

​    bc_source: String?         -- Where the canonical value came from

​    source_url: String         -- Provenance for the entity record as a whole

​    source_scraped_at: Date    -- When we last scraped it

​    last_verified_at: Date?    -- When a human last reviewed it

BulletBCSource (the datapoint-like table, scoped to BC only):

​    id: UUID

​    bullet_id: UUID              -- FK to Bullet

​    bc_type: "g1" | "g7"

​    bc_value: Float

​    source: "manufacturer" | "applied_ballistics" | "sierra" | "community" | "litz_book"

​    source_url: String?          -- Provenance link

​    source_date: Date?           -- When published/measured

​    source_quality: Float        -- 0-1 (AB measured = 0.95, manufacturer = 0.85, community = 0.5)

​    notes: String?               -- e.g., "From 6th Edition AB book, measured at 2,600 fps"

\```

The Bullet's `bc_g1` and `bc_g7` are the reconciled values — what the solver uses. The `BulletBCSource` table stores the full picture. Advanced users can see "manufacturer says 0.326 G7, Bryan Litz measured 0.305 G7." And when a manufacturer updates their published BC (Hornady has done this), you add a new `BulletBCSource` row, re-reconcile, and the Bullet's canonical value updates.

This also solves open question #2 (Hornady BC discrepancy between pages) cleanly: store both page scrapes as separate `BulletBCSource` rows, mark the bullet/component page as higher quality, and the reconciliation logic picks the right one.

***\*The reconciliation rule for BCs would be simple:\****

\- If Applied Ballistics measured value exists → use it (highest quality, independently measured)

\- Else if manufacturer bullet page value exists → use it (canonical source)

\- Else if manufacturer ammo page value exists → use it (lower quality, sometimes rounded)

\- Flag any case where sources disagree by more than 5% for human review

At Doro, we encode this kind of per-field logic in a `ReconciliationConfig`:

\```python

\# Doro pattern — field-specific reconciliation rules

bc_config = ReconciliationConfig(

​    strategy=ReconciliationStrategy.HIGHEST_QUALITY,  # Pick from best source

​    weights=ScoreWeightConfig(

​        source_quality=0.7,   # Source reputation matters most for BC

​        freshness=0.2,        # Newer measurements slightly preferred

​        consistency=0.1,      # Cross-source agreement is a signal

​    ),

​    numeric_consistency=NumericConsistencyConfig(

​        relative_tolerance=0.05,  # 5% difference = flag for review

​    ),

)

\```

You don't need the full reconciliation engine for V1 — the dataset is small and hand-reviewed. But the `BulletBCSource` table means you **can** add automated reconciliation later without a migration. And even without automation, the table is immediately useful: the human reviewer can see all BC sources side-by-side when approving a bullet record.

***\*Why not use datapoints for everything?\**** Because the overhead isn't free. Doro's datapoint layer adds real complexity: every entity query requires a join against the datapoints table (or maintaining a cache that's kept in sync), every write is two operations (write datapoint + update entity cache), and every new field needs reconciliation config. For a dataset of ~300 records where most fields have a single authoritative source, that's over-engineering. For BC — where the multi-source problem is real, the stakes of getting it wrong are high (a bad BC produces a bad ballistic solution), and the data naturally arrives from multiple sources — it's justified.

***\*If you want to keep the door open:\**** Structure provenance tracking at the entity level (source_url, source_scraped_at, extraction_confidence per field) and implement the full datapoint pattern only for BC. If you later discover that muzzle velocity or another field needs multi-source reconciliation, you can add a `CartridgeMVSource` table following the same pattern as `BulletBCSource`. You're not locked out of anything — you just don't pay for complexity you don't need yet.

**### On Aliasing:** **`alt_names`** **Column, Not a Separate Table**

The goals doc proposes a `SearchAlias` table as a separate entity mapping aliases to records. Having built the equivalent system at Doro, I'd recommend against a separate table. ***\*Use an** **`alt_names`** **text array column directly on each entity instead.\****

This is what Doro does. Every entity that needs alias search has:

\```python

\# On the database model (PostgreSQL)

alt_names = Column(JSONB, nullable=True)  # ["ELDM", "ELD-M", "ELD Match 140"]

\# Computed lowercase column for case-insensitive trigram search

alt_names_ci = Column(

​    Computed("lower(coalesce(alt_names::text, ''))", persisted=True)

)

\# GIN trigram index on the computed column

Index("ix_entity_alt_names_ci_trgm", "alt_names_ci",

​      postgresql_using="gin", postgresql_ops={"alt_names_ci": "gin_trgm_ops"})

\```

Doro's `NamesSearchStrategy` then searches across `name`, `legal_name`, and `alt_names` in a single query with scored relevance tiers — exact match on `alt_names` scores 0.90, vs 0.98 for exact match on primary `name`. The search uses PostgreSQL's `@>` (JSONB containment) operator for exact alt_name matches and `pg_trgm` similarity on the computed lowercase column for fuzzy matches. It's one query, no joins.

***\*Why this is better than a separate alias table for this use case:\****

1. ***\*Locality.\**** When you export to the bundled SQLite, each entity row carries its own aliases. No join needed at query time. For a 300-record dataset, this matters more for simplicity than performance.
2. ***\*Editability.\**** When reviewing a bullet in the CLI, you see its aliases inline: `alt_names: ["ELDM", "ELD-M", "ELD Match 140"]`. Adding an alias is editing one field on one record, not inserting a row in a separate table with an FK.
3. ***\*No orphan/sync issues.\**** A separate alias table can get out of sync with the entities it references — deleted entity, dangling alias. With `alt_names` on the entity, they're always consistent.
4. ***\*FTS5 integration is simpler.\**** When building the SQLite FTS5 index, you concatenate `alt_names` into the search content directly:

\```sql

-- At export time, build the FTS5 content with aliases baked in

INSERT INTO ammo_search(manufacturer, product_line, bullet_name, caliber_name, search_terms)

SELECT

​    manufacturer,

​    product_line,

​    bullet_name,

​    caliber_name,

​    -- Concatenate alt_names into a space-separated searchable string

​    name || ' ' || coalesce(group_concat(alt_name, ' '), '')

FROM bullet

LEFT JOIN json_each(bullet.alt_names) AS alt_name

GROUP BY bullet.id;

\```

***\*What goes in** **`alt_names`** **per entity type:\****

\```

Caliber.alt_names:

​    "6.5 Creedmoor" → ["6.5 CM", "6.5 Creed", "Creedmore", "6.5CM"]

​    ".308 Winchester" → [".308 Win", "308 Win", "308", ".308"]

​    "7.62x51mm NATO" → ["7.62x51", "7.62 NATO", "7.62mm"]

Bullet.alt_names:

​    "ELD Match" → ["ELDM", "ELD-M", "ELDMatch"]

​    "MatchKing" → ["SMK", "Sierra MatchKing", "Sierra MK"]

​    "Hybrid Target" → ["Berger Hybrid", "Hybrid"]

Cartridge.alt_names:

​    "Gold Medal Match" → ["GMM", "Gold Medal", "Federal GMM"]

​    "M118LR" → ["M118 LR", "M118 Long Range"]

Manufacturer (as extracted name):

​    "Hornady" → ["Hornaday", "Hornady Mfg"]  (common misspellings)

​    "Berger" → ["Burger", "Berger Bullets"]

\```

The misspelling aliases ("Hornaday", "Creedmore", "Burger") are the kind of editorial curation the goals doc correctly emphasizes. They're curated alongside the entity data, not in a separate table that could drift.

***\*The one case where a separate lookup might help:\**** Pre-search alias expansion for abbreviations that span multiple entities. If the user types "BTHP", you might want to expand that to "Boat Tail Hollow Point" before even hitting FTS5, because BTHP describes a bullet **type**, not a specific bullet. You could handle this with a small in-memory lookup dictionary in the Swift search layer — hardcoded or loaded from a simple key-value table:

\```swift

let abbreviationExpansions: [String: String] = [

​    "BTHP": "Boat Tail Hollow Point",

​    "OTM": "Open Tip Match",

​    "FMJ": "Full Metal Jacket",

​    "SP": "Soft Point",

​    "HP": "Hollow Point",

​    // ... ~30-50 entries

]

\```

This is distinct from per-entity aliases (which go in `alt_names`) — it's a global abbreviation dictionary for the search layer. A simple constant or a single-column table in the bundled SQLite. Not a full `SearchAlias` entity with FKs.

**### On Velocity-Banded BCs**

Storing Sierra-style stepped BCs and Hornady Mach-number data as JSON metadata on the Bullet is the right V1 call. One suggestion: define a schema for this JSON now, even if the solver doesn't consume it yet.

\```json

{

​    "type": "velocity_banded",

​    "model": "g1",

​    "source": "sierra",

​    "bands": [

​        {"velocity_fps_above": 2800, "bc": 0.535},

​        {"velocity_fps_above": 2400, "bc": 0.525},

​        {"velocity_fps_above": 2000, "bc": 0.505},

​        {"velocity_fps_above": 1600, "bc": 0.480}

​    ]

}

\```

This is strictly informational for V1 but having the schema defined means the solver team knows what to expect when they add multi-BC support.

\---

**## Pipeline Architecture: What Worked at Doro**

**### The Flow That Works**

Doro's enrichment pipeline follows a consistent flow that maps directly to the ammo use case:

\```

Doro's flow (full datapoint architecture):

1. DISCOVER    → Find sources (manufacturer URLs, product pages)
2. FETCH       → Retrieve page content (Firecrawl for JS-heavy sites, httpx for simple ones)
3. REDUCE      → Strip HTML to essential content (progressive reduction to ~30KB)
4. EXTRACT     → LLM extracts structured fields from reduced content
5. NORMALIZE   → Validate and standardize extracted values
6. RESOLVE     → Match to existing entities (dedup)
7. STORE       → Persist as immutable datapoints with provenance
8. RECONCILE   → Pick best values across sources, update entity cache

\```

For the ammo pipeline, the same flow but lighter on steps 7-8 (see "Should We Use Datapoints?" above — most fields store directly on the entity, only BC uses the multi-source datapoint pattern):

\```

1. DISCOVER    → Manufacturer product catalog URLs (Hornady /ammunition/ pages, etc.)
2. FETCH       → Firecrawl the product page (many manufacturer sites are JS-rendered)
3. REDUCE      → Strip to product specs section
4. EXTRACT     → LLM extracts AmmoProductStub fields
5. NORMALIZE   → Standardize caliber names, validate numeric ranges, expand abbreviations
6. RESOLVE     → Match bullet to existing Bullet entity; match cartridge to existing Cartridge
7. STORE       → Upsert entity record with source URL + scrape date; for BC, also store BulletBCSource row
8. RECONCILE   → For BC only: if multiple sources exist, pick best value and update Bullet.bc_g1/bc_g7

\```

**### Fetching: Use Firecrawl, It's Worth It**

At Doro, we tried three fetching tiers:

\- ***\*Lightweight\**** (httpx + BeautifulSoup): ~$0.001/page, 70% accuracy. Fine for simple HTML.

\- ***\*Balanced\**** (Trafilatura): ~$0.005/page. Good for articles, bad for product pages.

\- ***\*Premium\**** (Firecrawl v2): ~$0.008/page, high accuracy. JS rendering, main-content extraction.

For manufacturer sites, you'll want Firecrawl. Hornady's product pages are JS-rendered. Berger's site has dynamic content loading. Firecrawl handles this and returns clean markdown + metadata. At ~$0.008/page and ~500 products, that's $4 for the entire initial scrape. Monthly re-scrapes are the same. This is a rounding error.

Key Firecrawl parameters from our integration:

\```python

result = firecrawl_client.scrape(

​    url=product_url,

​    formats=["markdown", "html", "metadata"],

​    fast_mode=True,          # Faster queue, fine for product pages

​    only_main_content=True,  # Skip nav/footer, get product specs

)

\```

The `only_main_content=True` flag is important — it strips navigation and footer chrome, giving you just the product content. This makes the LLM extraction step much cleaner.

**### HTML Reduction: Progressive Stripping**

One of Doro's better inventions is the progressive HTML reducer. When sending page content to an LLM for extraction, you want ~30KB of relevant content, not 200KB of full-page HTML. The reducer applies steps in order until the target size is reached:

1. Remove scripts/styles
2. Remove heavy media (images, video embeds)
3. Remove comments and hidden elements
4. Clean data attributes
5. Simplify tables
6. Trim long text blocks
7. Strip non-critical attributes

For manufacturer product pages, you probably don't need this — Firecrawl's `only_main_content` does most of the work. But if you find yourself scraping retailer sites (MidwayUSA, Brownells) where product specs are buried in dense pages, the progressive reducer is useful. The Doro implementation is at `services/app/src/app/services/web_search/nav_extraction/html_reduction/implementations/reducer_v4.py`.

**### LLM Extraction: Send Schema, Get Structure**

Doro's extraction pattern: send reduced HTML/markdown to an LLM with a target schema, get structured JSON back. The schema definition doubles as the extraction prompt.

For Doro's company extraction, the schema looks like this (simplified):

\```python

class CompanyStub(BaseModel):

​    name: Optional[str]           # "Conversational name, NOT legal name"

​    description: Optional[str]    # "160-220 chars, [What] + [How] + [Differentiator]"

​    primary_industry: Optional[str]  # "Must be one of: [enum values]"

​    founding_year: Optional[int]

​    \# ... ~25 fields total

\```

Each field has a docstring that tells the LLM what to extract and how to format it. Enum fields list the valid values. This is remarkably effective — extraction accuracy is 85-95% for well-structured product pages.

For ammo extraction, the equivalent schema:

\```python

class AmmoProductStub(BaseModel):

​    """Schema for LLM-assisted extraction from ammunition product pages."""

​    manufacturer: Optional[str]         # "Company that manufactures the loaded cartridge"

​    product_line: Optional[str]         # "Product family name, e.g., 'ELD Match', 'Gold Medal'"

​    bullet_name: Optional[str]          # "Bullet/projectile name, e.g., 'ELD Match', 'MatchKing'"

​    bullet_manufacturer: Optional[str]  # "Bullet manufacturer if different from cartridge manufacturer"

​    caliber: Optional[str]              # "Cartridge name, e.g., '6.5 Creedmoor', '.308 Winchester'"

​    bullet_weight_gr: Optional[float]   # "Bullet weight in grains"

​    bullet_diameter_in: Optional[float] # "Bullet diameter in inches, e.g., 0.264"

​    bc_g1: Optional[float]              # "G1 ballistic coefficient, dimensionless, typically 0.1-0.8"

​    bc_g7: Optional[float]              # "G7 ballistic coefficient, dimensionless, typically 0.1-0.5"

​    muzzle_velocity_fps: Optional[float]  # "Factory muzzle velocity in feet per second"

​    test_barrel_length_in: Optional[float] # "Barrel length used for MV testing, in inches"

​    sectional_density: Optional[float]  # "Sectional density, dimensionless"

​    item_number: Optional[str]          # "Manufacturer SKU or item number, e.g., '81500'"

​    upc: Optional[str]                  # "UPC barcode number"

​    source_url: Optional[str]           # "URL of the page this data was extracted from"

\```

***\*Important lesson from Doro:\**** Make all fields `Optional`. LLM extraction is inherently partial — a product page might have BC but not sectional density, or MV but not test barrel length. Treating missing data as null (not as an extraction failure) is critical. You store what you get, flag what's missing, and fill gaps from other sources.

**### Normalization: The Underrated Step**

At Doro, normalization catches extraction errors before they enter the database. Each field has a `normalization_state` that tracks whether it's been validated:

\```python

ReviewState = Literal["pending", "valid", "invalid", "failed"]

\# After extraction, all fields start as "pending"

\# Normalization validates each field and sets state to "valid" or "invalid"

\# Invalid fields get discarded (optionally)

\```

For the ammo pipeline, normalization should handle:

***\*Caliber normalization\**** — The single most important normalization step. LLMs will extract caliber strings in various formats:

\```

"6.5 Creedmoor" → "6.5 Creedmoor"     (canonical)

"6.5mm Creedmoor" → "6.5 Creedmoor"

"6.5 CM" → "6.5 Creedmoor"

".308 Win." → ".308 Winchester"

"308 Winchester" → ".308 Winchester"    (add leading dot)

"7.62x51" → "7.62x51mm NATO"

\```

Build a caliber normalization map (aliases → canonical name) and run every extracted caliber through it. This is the same pattern Doro uses for industry classification — a lookup table that standardizes messy extracted values into clean enum values.

***\*Numeric range validation\**** — BC values should be 0.05-0.90. Muzzle velocity should be 1,500-4,500 fps. Bullet weight should be 15-750 grains. Anything outside these ranges is almost certainly an extraction error. Flag it, don't store it.

***\*Unit normalization\**** — Occasionally an LLM will extract velocity in m/s instead of fps, or weight in grams instead of grains. A simple heuristic catches this: if `muzzle_velocity < 500`, it's probably m/s; multiply by 3.281. If `bullet_weight < 5`, it's probably grams; multiply by 15.432.

**### Entity Resolution: The Composite Key Approach**

At Doro, entity resolution uses a tiered strategy chain (most confident first, fall through to fuzzier methods):

\```python

strategies = [

​    ("uuid",          confidence=1.00),  # Direct ID match

​    ("exact_domain",  confidence=1.00),  # Domain match

​    ("exact_name",    confidence=0.97),  # Exact name match

​    ("fuzzy_name",    confidence=0.45-0.95),  # RapidFuzz similarity

]

\```

For ammo entity resolution, the tiers:

\```

Bullet resolution:

1. exact_id           (1.00) — UUID match (re-scrape of known product)
2. manufacturer_sku   (0.98) — Item number match (#30313 → Hornady 140 ELD Match)
3. composite_key      (0.95) — (manufacturer + weight + caliber + product_line)
4. fuzzy_name         (0.70) — RapidFuzz on (manufacturer + bullet name)

Cartridge resolution:

1. exact_id           (1.00)
2. upc                (0.99) — UPC barcode match
3. manufacturer_sku   (0.98)
4. composite_key      (0.93) — (manufacturer + caliber + bullet_weight + product_line)
5. fuzzy_name         (0.70)

\```

The composite key (tier 3/4) is where most matches will happen. "Hornady" + "140gr" + "6.5 Creedmoor" + "ELD Match" is unambiguous. The entity resolver confirms or creates the record.

***\*Key lesson from Doro:\**** Track which resolution method was used. When you later find a bad match, you can query "all entities resolved via fuzzy_name with confidence < 0.85" to find other potential problems. This is cheap insurance.

**### Provenance: Store the Source URL and Scrape Date**

Every piece of data in the bundled database should be traceable to a URL and a date. At Doro, this is enforced architecturally — every datapoint has a `research_artifact_id` linking to the source document, which has a URL and timestamp.

For V1 of the ammo pipeline, you don't need the full artifact abstraction. But you do need:

\```

bullet.source_url          -- URL of the page this data came from

bullet.source_scraped_at   -- When we last scraped it

bullet.last_verified_at    -- When a human last reviewed it (nullable)

cartridge.source_url

cartridge.source_scraped_at

cartridge.last_verified_at

\```

This directly serves Goal 2 (correctness over coverage). When a user reports "your BC for the 140 ELD Match is wrong," you can check: where did we get that number? When? Has the manufacturer page changed since? This turns a support ticket into a 30-second investigation.

\---

**## Search Architecture: What Transferred and What Doesn't**

**### What Transfers: Strategy-Based Search**

Doro uses a search strategy registry — multiple search strategies execute in parallel, results merge with deduplication:

\```python

strategies = [

​    DomainSearchStrategy(relevance=1.00),    # Exact domain match

​    NameSearchStrategy(relevance=0.95),      # Exact name

​    INameSearchStrategy(relevance=0.93),     # Case-insensitive name

​    PgFullTextSearchStrategy(relevance=0.85), # FTS on tsvector

]

\```

Each strategy returns `(entity_id, relevance_score)` pairs. The orchestrator merges results, keeping the highest relevance per entity, deduplicates, applies filters/sorts, and returns paginated results.

For the backend ammo search API, the same pattern:

\```

CaliberExactStrategy(relevance=1.00)       -- "6.5 Creedmoor" exact

ManufacturerExactStrategy(relevance=0.95)  -- "Hornady" exact

SKUStrategy(relevance=0.98)                -- "#81500" item number

CompositeKeyStrategy(relevance=0.93)       -- caliber + weight + manufacturer

FTSStrategy(relevance=0.85)                -- Full-text across all fields

AliasStrategy(relevance=0.90)              -- "ELDM" → "ELD Match" alias lookup

\```

**### What Doesn't Transfer: PostgreSQL FTS → SQLite FTS5**

Doro's on-server search uses PostgreSQL features that don't exist in SQLite:

\- ***\*Trigram indexes\**** (`pg_trgm`) for fuzzy matching — no SQLite equivalent

\- ***\*****`ts_rank`*****\*** for relevance scoring — SQLite FTS5 has `rank` but it's simpler

\- ***\*Computed** **`TSVECTOR`** **columns\**** — SQLite FTS5 uses virtual tables instead

The on-device search needs a different implementation. Here's what I'd suggest based on the goals doc's requirements:

***\*SQLite FTS5 for core matching:\****

The FTS5 virtual table should include entity `alt_names` baked directly into the searchable content. At export time, flatten each entity's `alt_names` array into a space-separated string alongside the primary fields:

\```sql

CREATE VIRTUAL TABLE ammo_search USING fts5(

​    manufacturer,

​    product_line,

​    bullet_name,

​    caliber_name,

​    bullet_weight_text,  -- "140gr 140 grain"

​    all_names,           -- Primary name + alt_names flattened: "ELD Match ELDM ELD-M ELDMatch"

​    item_number,

​    content=cartridge,   -- External content table

​    content_rowid=rowid

);

\```

Because `alt_names` are on each entity, the FTS5 index naturally includes them — no join against a separate alias table at query time.

***\*Abbreviation expansion before FTS5 query:\****

For global abbreviations that describe bullet **types** rather than specific products (BTHP, OTM, FMJ), use a small in-memory lookup in the Swift search layer to expand the query before hitting FTS5:

\```

User types: "SMK 175 308"

→ Abbreviation expansion: "SMK" → "MatchKing Sierra" (from global dictionary)

→ Expanded query: "MatchKing Sierra 175 308"

→ FTS5 query against ammo_search (where alt_names already contain "SMK" on the Sierra MatchKing bullet)

\```

In practice, both paths catch the query — the FTS5 index has "SMK" in `all_names` for the MatchKing bullet, **and** the abbreviation expansion adds "MatchKing Sierra" to the query. Belt and suspenders. The abbreviation expansion helps when the user types **only** an abbreviation with no other context.

***\*Typo tolerance via trigram table:\****

SQLite FTS5 doesn't support fuzzy matching natively. The goals doc mentions trigram matching — here's the concrete approach:

Build a trigram index table at export time:

\```sql

CREATE TABLE search_trigrams (

​    trigram TEXT NOT NULL,       -- 3-char sequence, e.g., "hor", "orn", "rna"

​    entity_type TEXT NOT NULL,   -- "bullet", "cartridge", "caliber"

​    entity_id TEXT NOT NULL,

​    field TEXT NOT NULL,         -- Which field this trigram came from

​    PRIMARY KEY (trigram, entity_type, entity_id, field)

);

CREATE INDEX idx_trigrams ON search_trigrams(trigram);

\```

At search time, break the query into trigrams, look up matching entities, score by trigram overlap percentage. "Hornaday" → trigrams ["hor", "orn", "rna", "nad", "ada", "day"] → high overlap with "Hornady" trigrams ["hor", "orn", "rna", "nad", "ady"]. This catches single-character typos reliably.

The trigram table adds ~500KB-1MB to the database size (well within the 2MB budget) and gives you typo tolerance without any network dependency.

***\*Contextual ranking from active gun profile:\****

The goals doc mentions boosting results by the user's active gun caliber. Implementation suggestion: pass the active caliber_id as a search parameter and apply a multiplier to matching results:

\```swift

func search(query: String, activeCaliberId: UUID?) -> [SearchResult] {

​    var results = fts5Search(query)

​    if let caliberId = activeCaliberId {

​        results = results.map { result in

​            var r = result

​            if r.caliberId == caliberId {

​                r.relevanceScore *= 1.5  // Boost caliber-matched results

​            }

​            return r

​        }

​    }

​    return results.sorted(by: { $0.relevanceScore > $1.relevanceScore })

}

\```

This is simple, effective, and doesn't require a complex ranking model. The boost factor (1.5x) is tunable.

\---

**## Specific Suggestions for Open Questions**

**### Open Question #3: How Much Bullet Classification Metadata for V1?**

***\*Recommendation: Start with** **`bullet_type`** **as free text +** **`alt_names`** **for abbreviation search. Add structured fields in V2.\****

At Doro, we started with free-text `description` and `specialties` fields for companies, then added structured classifications (`primary_industry`, `offering_category`, `lifecycle_stage`) once we understood the taxonomy. The free-text fields were immediately useful for search and display. The structured fields were useful for filtering and analytics.

For bullets, the single `bullet_type` text field ("ELD Match", "Hybrid Target", "MatchKing BTHP") covers display and search needs at V1. Abbreviation resolution ("BTHP" → "Boat Tail Hollow Point") is handled by including "BTHP" in the bullet's `alt_names` array and "Boat Tail Hollow Point" in the global abbreviation expansion dictionary. Users don't filter by ogive type at this stage — they search by name.

Add `base_type`, `ogive_type`, `tip_type` as structured enums when you have a caliber detail page design that calls for them. The schema should have nullable columns for these from day one (no migration needed), but don't spend time populating them until there's a UI consuming them.

**### Open Question #4: Caliber Detail Page Scope**

***\*Recommendation: Curate the metadata now, decide display scope later.\****

The marginal cost of storing `typical_use_cases`, `common_twist_rates`, `common_barrel_lengths`, and `parent_case` on the Caliber entity is near-zero. You're hand-curating ~15-20 records. Spend 15 minutes per caliber filling in these fields. Whether the V1 UI shows a rich detail page or a minimal list is a product/design decision — but having the data ready means the design isn't constrained by missing data.

At Doro, we learned that **not** having data when the design calls for it is much more expensive than having data that sits unused for a while.

\---

**## Pipeline Tooling Suggestions**

**### Human Review CLI**

The goals doc mentions a "simple CLI tool: show extracted record, approve/reject/edit." Doro has a validation workflow with similar needs. Suggestions for the review tool:

\```

$ python review.py --pending

[1/47] Cartridge: Hornady 140gr ELD Match 6.5 Creedmoor

  Source: https://www.hornady.com/ammunition/rifle/6-5-creedmoor-140-gr-eld-match#!/

  Scraped: 2026-02-15

  manufacturer:     Hornady

  product_line:     ELD Match

  caliber:          6.5 Creedmoor          ← matched to Caliber(id=...)

  bullet:           Hornady 140gr ELD Match ← matched to Bullet(id=...), confidence=0.95

  bullet_weight_gr: 140.0

  bc_g1:            0.646

  bc_g7:            0.326

  mv_fps:           2710

  test_barrel_in:   24.0

  item_number:      81500

  upc:              090255815009

  [a]pprove  [e]dit  [r]eject  [s]kip  [o]pen URL  [?] help

\```

Key features:

\- Show the source URL (clickable) so the reviewer can verify against the original page

\- Highlight fields with low extraction confidence in a different color

\- Show the bullet match and its confidence — this is where errors cluster

\- `[o]pen URL` opens the source page in a browser for quick verification

\- Track who reviewed and when (`last_verified_at`, `verified_by`)

**### Coverage Dashboard**

At Doro, we tracked "what percentage of target companies have complete data" as a quality metric. The ammo equivalent:

\```

Coverage Report — 2026-02-20

═══════════════════════════════

Calibers:   15/18 defined (83%)

Bullets:   187/250 target (75%)

Cartridges: 203/300 target (68%)

Rifle Models: 42/75 target (56%)

Missing high-priority:

  ✗ Berger 140 Hybrid Target (6.5 CM) — no bullet page found

  ✗ Lapua 139 Scenar-L — BC discrepancy (0.301 vs 0.321), pending review

  ✗ Barnes 127 LRX — test barrel length missing

Manufacturer coverage:

  Hornady:  89/95  (94%) ████████████████████░

  Berger:   34/42  (81%) ████████████████░░░░░

  Sierra:   28/40  (70%) ██████████████░░░░░░░

  Federal:  22/35  (63%) ████████████░░░░░░░░░

  Nosler:    8/20  (40%) ████████░░░░░░░░░░░░░

  Lapua:     5/15  (33%) ██████░░░░░░░░░░░░░░░

  Barnes:    3/12  (25%) █████░░░░░░░░░░░░░░░░

  Norma:     0/10  ( 0%) ░░░░░░░░░░░░░░░░░░░░░

\```

This should be automated — run after every pipeline batch, commit to repo as a markdown file. It makes "what do I work on next?" obvious.

**### SQLite Export Script**

The export pipeline should be a single command that:

1. Queries the master PostgreSQL database for all approved records
2. Builds the SQLite file with the four entity tables (alt_names included as JSON arrays on each entity)
3. Builds the FTS5 virtual table with `alt_names` flattened into searchable content
4. Builds the trigram index table
5. Loads global abbreviation expansions into a small lookup table
6. Stamps a `schema_version` and `data_version` in a metadata table
7. Compresses the output
8. Reports file size and record counts

\```

$ python export_bundled_db.py --output rangefinder_ammo_v1.2.sqlite

Exporting approved records...

  Calibers:     18 (avg 4.2 alt_names each)

  Bullets:     247 (avg 2.8 alt_names each)

  Cartridges:  289 (avg 1.9 alt_names each)

  Rifle Models: 67

  Abbreviations: 48

Building FTS5 index... done

Building trigram index... done (187,421 trigrams)

Output: rangefinder_ammo_v1.2.sqlite

  Uncompressed: 1.4 MB

  Compressed:   0.6 MB

  Schema version: 3

  Data version: 1.2

\```

The metadata table:

\```sql

CREATE TABLE db_metadata (

​    key TEXT PRIMARY KEY,

​    value TEXT NOT NULL

);

-- Populated with:

-- schema_version: "3"

-- data_version: "1.2"

-- export_date: "2026-02-20T14:30:00Z"

-- record_counts: '{"calibers": 18, "bullets": 247, "cartridges": 289, "rifle_models": 67}'

\```

The iOS app reads `schema_version` on startup to know if it needs to run a migration. `data_version` is displayed in settings ("Ammo database v1.2").

\---

**## Things That Bit Us at Doro (Don't Repeat These)**

**### 1. Null Handling in Reconciliation**

At Doro, we still haven't perfectly solved how to handle null values in reconciliation. If one source says a company has 150 employees and another source returns null for that field, does null mean "I don't know" or "this field doesn't apply"? We ended up dropping null datapoints before reconciliation, which occasionally loses signal.

For the ammo pipeline: ***\*missing data is not conflicting data.\**** If Hornady's product page shows BC G7 but not BC G1, that's not a conflict with a source that shows both — it's just incomplete. Don't store a null datapoint for `bc_g1` when the source simply doesn't mention it. Only store what was actually extracted. This is simpler than Doro's approach and correct for this domain.

**### 2. Source Quality ≠ Datapoint Quality**

At Doro, we conflated source quality (how reliable is LinkedIn?) with datapoint quality (how confident are we in this specific extraction?). They're related but distinct. LinkedIn is a high-quality source (0.85), but an LLM might extract the wrong number from a LinkedIn page (datapoint confidence 0.6).

For the ammo pipeline, track both:

\- ***\*Source quality:\**** How reliable is this source in general? (Manufacturer page = 0.95, retailer page = 0.75, forum post = 0.3)

\- ***\*Extraction confidence:\**** How confident is the LLM that it correctly extracted this specific field? (Clear specs table = 0.95, buried in marketing copy = 0.7, inferred from context = 0.5)

The effective confidence for a datapoint is `min(source_quality, extraction_confidence)`. A high-quality source with a low-confidence extraction shouldn't be treated as trustworthy.

**### 3. Schema Changes After Data Exists**

At Doro, we've had to add fields to the company schema multiple times after data was already flowing. Each time, we needed to decide: re-scrape everything to populate the new field, or accept that old records won't have it?

For the ammo pipeline, the V1 schema should include all the fields you **might** populate in the next 6 months, even if they're nullable and empty at launch. Adding a column to SQLite is trivial. Populating it retroactively across hundreds of records is not. The goals doc's "extended fields (optional at V1)" list for bullets (bullet_length, base_type, ogive_type, etc.) should be columns in the schema from day one — just nullable and empty.

**### 4. LLM Extraction Prompt Iteration**

At Doro, extraction accuracy improved dramatically with prompt iteration. The first version of our company extraction prompt had ~70% accuracy. After 3-4 rounds of looking at failures and adjusting the prompt (adding examples, clarifying ambiguous fields, constraining output format), we got to ~90%.

Budget time for this. The first scrape of Hornady's product pages will have extraction errors. Look at every error, categorize them (wrong field? wrong value? missed field? hallucinated value?), and adjust the extraction schema's field descriptions. Two rounds of this should get you to 95%+ accuracy for well-structured manufacturer pages.

\---

**## Summary: What to Build, In What Order**

| Step | What | Informed by Doro? | Effort |

|------|------|-------------------|--------|

| 1 | Define the four-entity schema + `alt_names` per entity + BC source table | Schema patterns, provenance tracking | 2-3 days |

| 2 | Hand-curate 30-50 seed records (ground truth for validation) | - | 2-3 days |

| 3 | Build scraping pipeline: Firecrawl fetch → LLM extraction → normalization | Sourcing strategy framework, HTML reduction, extraction prompts | 1-1.5 weeks |

| 4 | Build entity resolution: composite key matching + fuzzy fallback | Entity resolver pattern, RapidFuzz, confidence tracking | 3-5 days |

| 5 | Build human review CLI | Validation workflow patterns | 2-3 days |

| 6 | Build SQLite export with FTS5 + trigram indexes | Search strategy patterns (adapted for SQLite) | 3-5 days |

| 7 | Build coverage dashboard | Quality metrics patterns | 1 day |

| 8 | Expand to all 8 manufacturers | Pipeline already built, just config per manufacturer | 1-2 weeks |

The pipeline (step 3) is where most of the Doro reuse happens. The entity resolution (step 4) is the second biggest reuse area. The on-device search (step 6) is new implementation informed by Doro patterns but not directly reusable code.

\---

**## Files Worth Reading in the Doro Codebase**

If you want to look at the actual code for reference:

***\*Extraction & scraping:\****

\- `services/app/src/app/services/web_search/fetching/backends/_firecrawl.py` — Firecrawl integration

\- `services/app/src/app/services/companies/sourcing_strategies/schemas.py` — How we define extraction schemas (the field docstrings **are** the extraction prompt)

\- `services/app/src/app/services/companies/sourcing_strategies/base.py` — `BaseSourcingStrategy` and `SourcedArtifact`

***\*Entity resolution:\****

\- `services/app/src/app/services/companies/entity_resolution/` — Strategy chain pattern, confidence scoring, batch resolution

***\*Reconciliation (for understanding the multi-source pattern):\****

\- `core/src/core/schemas/algos/datapoint.py` — Generic `DataPoint[T]` with `SourceInfo`

\- `core/src/core/schemas/algos/reconciliation.py` — `ReconciliationConfig`, consistency strategies, scoring weights

\- `services/algos/src/algos/services/reconciliation/service.py` — The actual reconciliation logic

***\*Database models (for schema patterns):\****

\- `core/src/core/db/models/public/research/shared_companies.py` — Trigram indexes, tsvector search, JSONB fields

\- `core/src/core/db/models/public/research/shared_company_datapoints.py` — Immutable datapoint storage

***\*Workflow orchestration:\****

\- `services/app/src/app/services/companies/workflows/enrich.py` — Temporal workflow for the full sourcing → extraction → storage pipeline