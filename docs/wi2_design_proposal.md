# WI-2: Ammo & Firearms Data Library — Design Proposal

> **Historical reference (2026-02-20).** This is the original design doc that bootstrapped the WI-2 backend. The schema, pipeline stages, and curation system have evolved since — code is now the source of truth.
>
> Read this for the *why* (motivating principles, original tradeoffs, open questions at the time). For *what's actually shipping*, use:
> - `src/drift/models/` — current schema
> - [docs/pipeline_README.md](pipeline_README.md) — current pipeline workflow
> - [docs/curation_README.md](curation_README.md) — current curation system
> - [docs/engineering_overview.md](engineering_overview.md) — current glossary and gotchas

**Status:** Historical / Reference
**Date:** 2026-02-20
**Author:** Engineering

---

## Overview

Work Item 2 delivers an on-device ammunition and firearms database that powers fast, fuzzy search during profile creation. The goal: a shooter picks their gun and ammo in under 60 seconds, and gets a correctly populated ballistic profile with no manual data entry.

The database ships as a bundled SQLite asset, built by an offline scraping and extraction pipeline. It covers ~200–300 factory loads across priority calibers and manufacturers at MVP, with a pipeline designed to compound coverage over time.

---

## Design Principles

**Correctness over coverage.** Every record traces back to a source URL. We'd rather ship 200 loads we trust than 2,000 we can't verify. The pipeline is built for auditability — every field carries provenance.

**Bullet is the canonical unit.** A single 140gr ELD Match bullet appears in multiple factory cartridges and countless handloads. The schema reflects this: Bullet is the shared entity, Cartridge and UserLoadProfile both reference it.

**Chamber is not caliber.** A gun is chambered, not "calibered." .223 Wylde is a chamber with no corresponding cartridge. 5.56 NATO can fire .223 Rem but not vice versa. The schema models this directionality explicitly.

**Offline-first, AI at ingestion.** LLM extraction happens once in the pipeline, producing clean structured data. The on-device database is pure SQLite — no inference at query time, no network dependency.

**Published, estimated, measured.** For values like BC where multiple sources exist, we track up to three tiers: the manufacturer's published number (what the user expects to see), an estimated real-world value (from third-party testing), and eventually a user-measured value (from their own chronograph and shot data).

**Handloaders are first-class citizens.** A handloader's flow is: pick a bullet (they already know which one), enter their chrono'd MV, and go. No cartridge selection, no product line, no SKU. The "bullet as canonical unit" decision isn't just architecturally clean — it directly serves the handloader path. This must be a first-class UX flow, not a fallback from the factory ammo path.

**Build a pipeline, not a spreadsheet.** The database is a living artifact. Monthly re-scrapes, automated extraction, human review. The tooling matters as much as the data.

---

## Architecture

### System Diagram

```
                     ┌──────────────────────────────────┐
                     │        SCRAPING PIPELINE          │
                     │  (offline, runs on backend)       │
                     │                                   │
                     │  DISCOVER → FETCH → REDUCE →      │
                     │  EXTRACT → NORMALIZE → RESOLVE →  │
                     │  STORE → RECONCILE                │
                     └──────────────┬───────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │  Backend SQLite  │
                          │  (source of      │
                          │   truth + full   │
                          │   provenance)    │
                          └────────┬────────┘
                                   │
                            export & version
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  Bundled SQLite  │
                          │  (on-device,     │
                          │   stripped for    │
                          │   size, FTS5     │
                          │   indexes)       │
                          └────────┬────────┘
                                   │
                                   │
                                   ▼
                            ┌────────────┐
                            │  FTS5      │
                            │  Fuzzy     │
                            │  Search    │
                            └────────────┘
```

### Pipeline Stages

| Stage | Purpose | Tooling |
|-------|---------|---------|
| **Discover** | Enumerate product pages for target manufacturers + calibers | Sitemap parsing, seed URL lists |
| **Fetch** | Download and cache raw HTML | Firecrawl |
| **Reduce** | Strip nav, ads, boilerplate; isolate product content | HTML simplification |
| **Extract** | Pull structured fields from product content | LLM with typed schema prompts |
| **Normalize** | Canonicalize caliber names, validate numeric ranges, detect units | Caliber alias map, range validators |
| **Resolve** | Match extracted bullets/cartridges to existing entities | Tiered confidence: exact SKU → composite key → fuzzy name |
| **Store** | Write to backend SQLite with full provenance | Source URL, scrape timestamp, extraction confidence per field |
| **Reconcile** | Resolve multi-source conflicts (BC values especially) | Human-in-the-loop for first pass; rules-based after |

### On-Device Search

Search runs entirely on-device via SQLite FTS5 with three additions:

1. **Abbreviation expansion** — Query preprocessor expands shooter shorthand before it hits FTS5 ("ELDM" → "ELD Match", "SMK" → "Sierra MatchKing", "BTHP" → "Boat Tail Hollow Point")
2. **Trigram table** — Catches typos and near-misses ("hornday" → "hornady", "creeedmoor" → "creedmoor")
3. **Contextual ranking** — Results matching the user's active chamber/caliber are boosted

The search flow: `user query → abbreviation expand → trigram correct → FTS5 lookup → rank by chamber context → return results`.

---

## Data Model

### Entity Relationship

```
                               Manufacturer
                              /     |      \
                            /       |        \
                          /         |          \
  Chamber ─── chamber_accepts_caliber ─── Caliber
    │                                        │
    │  (gun is chambered in)    (cartridge belongs to)
    │                                        │
  RifleModel ─── Manufacturer          Cartridge ─── CartridgeListing (V2)
  GunProfile (user)                          │
                                             │
                                  (cartridge contains)
                                             │
                                          Bullet ─── Manufacturer
                                             │
                                  (user load references)
                                             │
                                      UserLoadProfile (user)
```

### Manufacturer

A company that produces bullets, cartridges, rifles, or retails ammunition. Single source of truth for display names, logos, and website URLs — replaces raw manufacturer strings scattered across other entities.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `name` | String | Canonical display name: "Hornady", "Federal Premium" |
| `alt_names` | JSON array | Aliases for search: ["Federal", "Federal Ammunition", "ATK Federal"] |
| `website_url` | String? | e.g., "https://www.hornady.com" |
| `logo_url` | String? | For UI display — CDN path or bundled asset reference |
| `type_tags` | JSON array | ["bullet_maker", "ammo_maker", "rifle_maker", "retailer"] |
| `country` | String? | "USA", "Finland" |
| `notes` | String? | Editorial context |

**Key decisions:**

- `type_tags` rather than a single `type` enum because many manufacturers span categories. Hornady makes both component bullets and loaded cartridges. Federal owns Sierra. Brownells is both a retailer and a house brand. Tags handle this naturally.
- A single Manufacturer table covers ammo makers, bullet makers, rifle makers, and retailers. The alternative — separate tables per role — creates duplication (Federal would appear in three tables) and complicates search. Tags distinguish roles when needed.
- `alt_names` handles corporate name variations and common shorthand ("Federal" vs. "Federal Premium" vs. "Federal Ammunition"). Same pattern as every other entity.
- `logo_url` is optional and deferred for MVP. Useful for polish in the search UI but not blocking.

**Open question:** Some corporate relationships are complex — Federal owns Sierra, Vista Outdoor owns both, Hornady is independent. Do we model parent/subsidiary relationships? **Recommendation: no. A flat list with clear `alt_names` is sufficient. Corporate hierarchy doesn't affect ammo selection.**

---

### Caliber

Represents a cartridge designation — the ammo side of the equation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `name` | String | Canonical display name: "6.5 Creedmoor", ".308 Winchester" |
| `alt_names` | JSON array | Aliases for search: ["6.5 CM", "6.5mm Creedmoor"] |
| `bullet_diameter_inches` | Float | Physical dimension, e.g., 0.264 for 6.5mm |
| `case_length_inches` | Float? | |
| `saami_designation` | String? | Official SAAMI name if one exists |
| `notes` | String? | Editorial context |
| `source_url` | String? | Provenance |

**Key decisions:**

- `alt_names` is a JSON array on the entity, not a separate alias table. This keeps FTS5 indexing simple (one row to index per entity) and avoids join-table sync complexity. The Doro learnings are emphatic on this point.
- No `military_designation` or `commercial_equivalent_id` fields. The military/commercial relationship (e.g., .308 Win vs. 7.62x51 NATO) is captured by the Chamber entity's `accepts_caliber_ids` directionality, and by `alt_names` for search purposes. Simpler, less to maintain.
- Bullet diameter is stored explicitly because caliber names are unreliable (e.g., .270 Win uses .277" bullets, .38 Special uses .357" bullets).

**Open question:** Do we need a `parent_case_id` self-referential FK to model cartridge family trees (e.g., 6.5 CM is based on .30 TC, which is based on .308 Win)? Useful for educational content, but not needed for search or filtering at MVP. **Recommendation: defer.**

---

### Bullet

The canonical ballistic unit. Shared across factory cartridges and user handloads.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `manufacturer_id` | FK → Manufacturer | |
| `name` | String | "ELD Match", "MatchKing" |
| `alt_names` | JSON array | ["ELDM", "ELD-M"] |
| `sku` | String? | Manufacturer part number, e.g., "#26331" |
| `caliber_id` | FK → Caliber | |
| `weight_grains` | Float | |
| `bc_g1_published` | Float? | Manufacturer's published G1 value |
| `bc_g1_estimated` | Float? | Third-party tested value (Applied Ballistics, etc.) |
| `bc_g7_published` | Float? | Manufacturer's published G7 value |
| `bc_g7_estimated` | Float? | Third-party tested value |
| `bc_source_notes` | String? | e.g., "G7 estimated from Applied Ballistics, 2024 edition" |
| `length_inches` | Float? | Bullet length (for stability calc) |
| `type_tags` | JSON array | ["match", "boat-tail", "hollow-point", "polymer-tip"] -- Will want some **normalization** here |
| `used_for` | JSON array | ["target", "big game", "varmint"] -- Will want some **normalization** here |
| `sectional_density` | Float? | Derived: weight / (diameter^2 * 7000) |
| `source_url` | String? | |
| `extraction_confidence` | Float? | Pipeline confidence score |
| `last_verified_at` | DateTime? | |

**Key decisions:**

- **Published vs. estimated BC** as separate columns rather than a multi-row `BulletBCSource` table. This is simpler for the on-device schema, trivial to query, and maps cleanly to the UI ("here's the manufacturer number; here's what we think the real number is"). The pipeline's backend can still track richer provenance internally; the bundled schema is the user-facing projection.
- **Measured BC lives on `UserLoadProfile`**, not here. A user's measured BC is specific to their rifle, barrel length, and conditions — it doesn't belong on the shared Bullet entity.
- `type_tags` as a JSON array rather than an enum. Bullet classification is multi-dimensional (boat-tail + hollow-point + polymer-tip) and the taxonomy evolves. Tags are flexible and searchable.
- `sku` enables exact entity resolution in the pipeline (Hornady #26331 is unambiguous). Not all manufacturers publish SKUs consistently.

**Open question:** Should we store velocity-banded BC tables for bullets where manufacturers publish them (Sierra's stepped G1 values, Hornady's Mach-number bands)? This is accurate but adds schema complexity. **Recommendation: defer to V2. Use the single best-available value for now. The solver already handles single-value BC well, and stepped BCs are a refinement, not a correctness issue for typical engagement distances.**

---

### Cartridge

A factory-loaded round. References a specific Bullet in a specific Caliber.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `manufacturer_id` | FK → Manufacturer | |
| `product_line` | String? | "Precision Hunter", "Gold Medal" -- Will want some **normalization** here |
| `name` | String | Full product name |
| `alt_names` | JSON array | |
| `sku` | String? | e.g., Hornady #81500 |
| `caliber_id` | FK → Caliber | |
| `bullet_id` | FK → Bullet | |
| `bullet_weight_grains` | Float | Denormalized for search/display convenience |
| `muzzle_velocity_fps` | Int | Published MV (typically from a test barrel length) |
| `test_barrel_length_inches` | Float? | e.g., 24" — critical context for the MV number |
| `round_count` | Int? | Box count (20, 50, etc.) |
| `source_url` | String? | |
| `extraction_confidence` | Float? | |
| `last_verified_at` | DateTime? | |

**Key decisions:**

- `bullet_id` links to the shared Bullet entity. This is the core of the "bullet as canonical unit" principle. When a user picks Hornady 6.5 CM 140gr ELD Match (cartridge #81500), we can pull BC data from the linked Bullet (#26331).
- `bullet_weight_grains` is intentionally denormalized — it's the most common search/filter dimension and shouldn't require a join.
- `muzzle_velocity_fps` is the manufacturer's published value from their test barrel. The user's actual MV will differ based on their barrel length and will live on `UserLoadProfile`.
- `test_barrel_length_inches` provides context. A published 2,710 fps from a 24" barrel tells the user something different than 2,710 from a 26" barrel.

**Open question:** Some cartridges use bullets not sold as standalone components (e.g., Federal's proprietary projectiles). Do we create Bullet records for these even though they can't be purchased separately? **Recommendation: yes. The Bullet entity represents a ballistic object, not a purchasable product. Every cartridge gets a linked Bullet record, even if that bullet has no independent SKU or product page.**

---

### CartridgeListing *(V2 — schema only, not built for V1)*

Purchase links and pricing for factory cartridges. Defined in the schema for forward compatibility, but **no engineering time is allocated to scraping, populating, or serving this entity in V1.** We validate user demand for "Where to buy" before investing here.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `cartridge_id` | FK → Cartridge | |
| `retailer_id` | FK → Manufacturer | Retailer entity — Manufacturer with "retailer" type tag |
| `url` | String | Direct product page link |
| `price_cents` | Int? | Nullable — may not always be scrapeable |
| `price_per_round_cents` | Int? | Derived if box count is known |
| `in_stock` | Bool? | Snapshot at scrape time |
| `last_scraped_at` | DateTime | |

**Key decisions:**

- Separate table because one cartridge has many listings, and pricing data is volatile.
- Stale is fine. Even a 6-month-old link to the right product page on MidwayUSA is useful. We're not building a price tracker; we're reducing friction for the user to find and buy the ammo they've selected.
- **Not bundled on-device at MVP.** This is a backend lookup when the user taps "Where to buy." Keeps the bundled DB small and avoids shipping stale prices as if they were current.
- **Deferred until post-launch.** We're a ballistics tool, not a marketplace. This entity exists in the schema so we don't need a migration later, but it gets zero pipeline or UI work until we have signal that users want it.

---

### Chamber

Represents what a gun is machined for. Lightweight, mostly auto-generated, hand-curated for the interesting cases.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `name` | String | "5.56 NATO", ".223 Wylde", "6.5 Creedmoor" |
| `alt_names` | JSON array | |
| `notes` | String? | Editorial, e.g., ".223 Wylde is a hybrid chamber..." |
| `source` | String? | "SAAMI spec", "manufacturer documentation" |

**Plus join table:**

| `chamber_accepts_caliber` | | |
|---------------------------|---|---|
| `chamber_id` | FK → Chamber | |
| `caliber_id` | FK → Caliber | |
| `is_primary` | Bool | 1 = native caliber, 0 = also accepts |

**Key decisions:**

- Chamber is separate from Caliber because they represent different physical things (the gun vs. the ammo). This matters for .223 Wylde (chamber-only, no cartridge), 5.56/.223 directionality, and .308/7.62x51 directionality.
- ~25 total records. Most auto-generated as 1:1 mirrors of Caliber entries. Only 5–8 require manual curation (the .223/.556/.308/7.62 family plus a few others).
- `is_primary` on the join table distinguishes the "native" cartridge from "also safe to fire" — useful for search ranking (primary caliber results first, compatible caliber results second).

---

### RifleModel

Factory rifle specifications. Referenced during gun profile creation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `manufacturer_id` | FK → Manufacturer | |
| `model` | String | "B-14 HMR", "T3x TAC A1" |
| `manufacturer_url` | String |  |
| `alt_names` | JSON array | |
| `chamber_id` | FK → Chamber | |
| `barrel_length_inches` | Float? | |
| `twist_rate` | String? | "1:8", "1:10" |
| `weight_lbs` | Float? | |
| `description` | String? | |
| `barrel_material` | String? |  |
| `barrel_finish` | String? |  |
| `source_url` | String? | |

**Key decisions:**

- Lightweight entity by design. For the MVP calibers (especially 6.5 CM), rifle specs are boringly consistent — almost all are 1:8 twist, 22–24" barrel. This entity doesn't need the same pipeline rigor as Bullet/Cartridge.
- References Chamber, not Caliber. A Ruger American in .223 Wylde is chambered for .223 Wylde, not ".223 Remington."

---

### User-Side Entities (Not Part of WI-2, But Relevant)

These live in the app's SwiftData layer, not the bundled database:

**GunProfile:**
- `chamber_id: FK → Chamber` (replaces `caliber_id`)
- `rifle_model_id: FK → RifleModel?`
- `barrel_length_inches`, `twist_rate`, etc. (user-overridable)

**UserLoadProfile:**
- `bullet_id: FK → Bullet`
- `cartridge_id: FK → Cartridge?` (null for handloads)
- `muzzle_velocity_fps: Int` (user's actual MV, may differ from published)
- `muzze_velocity_fps_sd: Float` (variance / standard deviation of MV values, may differ from estimated)
- `bc_g1_measured: Float?` (derived from user's own data)
- `bc_g7_measured: Float?`

The solver uses a priority chain: **measured > estimated > published** for BC values, pulling from UserLoadProfile first, then falling back to the linked Bullet.

---

## MVP Scope

### Calibers (Phase 1)

6.5 Creedmoor, .308 Winchester, .223 Remington / 5.56 NATO, .300 Win Mag, .300 PRC, 6.5 PRC, .338 Lapua Magnum, .270 Winchester.

This covers the beachhead long-range precision audience plus the most popular general rifle calibers.

### Manufacturers

| Ammo / Bullet Manufacturers | Rifle Manufacturers |
|-|-|
| Hornady | Bergara |
| Federal / Sierra | Tikka |
| Berger | Ruger |
| Nosler | Howa |
| Barnes | Savage |
| Lapua | Remington |
| Applied Ballistics (BC data) | |

### Target Record Counts

| Entity | Estimated Records |
|--------|------------------|
| Manufacturer | ~15–20 |
| Caliber | ~15–20 |
| Bullet | ~150–200 |
| Cartridge | ~200–300 |
| Chamber | ~20–25 |
| RifleModel | ~50–80 |
| CartridgeListing | *(V2 — schema only)* |

---

## What We're Not Building (V1)

- **Handloader recipe database.** Users can create custom load profiles manually. We're not scraping load data or powder charges.
- **Custom drag models.** Applied Ballistics CDMs are proprietary. We use G1/G7 standard models.
- **OTA database updates.** V1 ships as a bundled asset. Updates come with app releases. OTA is a V2 feature.
- **Velocity-banded BC tables.** Single best-value BC is sufficient for typical engagement distances. Stepped BC profiles are a refinement for V2.
- **Chamber safety advice.** We filter ammo based on chamber compatibility. We don't display warnings or recommendations about what's "safe." The filtering itself is the safety layer.
- **CartridgeListing / purchase links.** Schema is defined for forward compatibility. No pipeline, UI, or backend work until post-launch demand is validated.

---

## Future Considerations

Items that don't need to be built now but the architecture should anticipate:

**User data correction reports.** Once the database is in users' hands, someone will tell us "your BC for the 175 SMK is wrong." We need a lightweight feedback mechanism — even just a "report data issue" button that logs the entity type, entity ID, the field in question, and a freeform note. That feeds back into the pipeline's human review queue. A simple `data_issue_report` table (entity_type, entity_id, field_name, user_note, timestamp) is trivial to add when the time comes.

**Search-miss analytics.** The abbreviation dictionary and trigram table are editorial assets that need to grow with usage. After launch, we should instrument search to capture queries that return zero results or where the user abandons the result set. This is the primary signal for expanding abbreviation coverage and identifying gaps in the database itself.

**Velocity-banded BC tables.** Sierra publishes stepped G1 values across velocity ranges; Hornady uses Mach-number bands. The single best-value BC is sufficient for V1, but a `BulletBCBand` child table (velocity_min, velocity_max, bc_value, drag_model) would enable more accurate long-range solutions in V2.

**OTA database updates.** V1 ships as a bundled asset. V2 should support delta updates without requiring an app release. The schema versioning in the export script lays groundwork for this.

---

## Next Steps

1. **Finalize schema and create models.** Convert this proposal into actual SQLAlchemy classes / Python code. Create initial Alembic database migration. 
2. **Hand-curate seed data.** Build the Manufacturer, Caliber, and Chamber tables manually (~15–25 records each). These are editorial data, not scraped. **Validate the "priority loads" list** against community data (match equipment surveys, forum frequency analysis, retailer bestsellers) to confirm that our ~200–300 cartridge target hits >90% search hit rate for beachhead users.
3. **Build pipeline skeleton.** Stand up the DISCOVER → STORE pipeline with a single manufacturer (Hornady) and single caliber (6.5 CM) as the proving ground.
4. **Build human review tooling.** CLI that shows extracted records, links to source URLs, and allows approve/edit/reject. This needs to exist before we ingest at scale.
5. **Build abbreviation + trigram tables.** Curate the shooter vocabulary (ELDM, SMK, BTHP, etc.) and seed the trigram table for typo correction.
6. **FTS5 search integration.** Wire up the on-device search path with abbreviation expansion, trigram correction, and chamber-aware ranking.
7. **Export script.** Automated export from backend SQLite → bundled SQLite with schema versioning, provenance stripping, and size optimization.



---

## Addendum: PM Review — Items to Incorporate from Earlier Data Model Proposal

*Added by Product after cross-referencing this proposal against an earlier independent data model proposal by a second engineer. The earlier proposal reached the same core structural decisions (four entities, bullet as canonical unit, caliber as first-class) but made several field-level and tooling choices worth pulling into this document. None of these change the architecture — they're refinements that strengthen the schema and the search system.*

*This addendum is directive: treat these as requirements for Step 1 (finalize schema), not suggestions for future consideration.*

---

### 1. Add `popularity_rank` to Caliber and Cartridge

**What:** An editorially curated integer field on both the Caliber and Cartridge entities. Lower number = more popular. Nullable for unranked records.

**Why:** Contextual ranking from the active gun profile (already in the proposal) helps when the user has a gun set up. But on first launch — no gun profile yet, user types "140 ELD" — we need a way to rank 6.5 Creedmoor results above 6.5 PRC results, and Hornady Match above Hornady Precision Hunter. FTS5 relevance scoring alone won't do this. A simple integer rank, curated by us, is the cheapest and most reliable way to get default search ordering right.

**On Caliber:** Rank by our estimate of market share among our target users. 6.5 CM = 1, .308 Win = 2, etc.

**On Cartridge:** Rank within caliber. For 6.5 CM: Hornady 140 ELD Match = 1, Hornady 147 ELD Match = 2, Federal Gold Medal 140 SMK = 3, etc. Derived from PRS equipment surveys, forum frequency, and retailer bestseller data.

**Schema change:**

```
Caliber:   + popularity_rank  Int?
Cartridge: + popularity_rank  Int?
```

---

### 2. Define Controlled Vocabulary for `type_tags` and `used_for` on Bullet

**What:** The proposal notes "will want some normalization here" on both fields. This defines it.

**Why:** If one pipeline run tags a bullet `["match", "boat-tail"]` and another tags a similar bullet `["competition", "bt"]`, the tags are useless for filtering or display consistency. We need a fixed vocabulary from day one.

**`type_tags` controlled vocabulary** (drawn from the earlier proposal's structured enum taxonomy — these are the only valid values):

```
Base:         "flat-base", "boat-tail", "rebated-boat-tail"
Tip:          "open-tip", "polymer-tip", "hollow-point", "soft-point",
              "fmj", "aluminum-tip", "solid"
Construction: "cup-and-core", "bonded", "partitioned", "monolithic"
Other:        "lead-free"
```

A bullet gets multiple tags from across categories. Examples:
- Hornady 140 ELD Match: `["boat-tail", "polymer-tip", "cup-and-core"]`
- Barnes 127 LRX: `["boat-tail", "polymer-tip", "monolithic", "lead-free"]`
- Sierra 175 MatchKing: `["boat-tail", "open-tip", "cup-and-core"]`

**`used_for` controlled vocabulary:**

```
"match", "hunting-big-game", "hunting-varmint", "tactical",
"plinking", "self-defense"
```

A bullet can have multiple use cases. Hornady ELD-X: `["hunting-big-game"]`. Hornady ELD Match: `["match"]`. Nosler AccuBond: `["hunting-big-game"]`.

**Implementation:** Document these vocabularies in the seed data guide. The extraction pipeline's LLM prompt should constrain outputs to these values. The normalization step should reject or flag any extracted tag not in the vocabulary.

**Future-proofing:** The earlier proposal used separate structured enum fields (`base_type`, `tip_type`, `construction`, `use_case`) which are more queryable for filtering UIs. Add these as nullable columns to the Bullet schema now — empty for V1, populatable from `type_tags` when we build caliber/bullet detail pages:

```
Bullet:   + base_type     String?   -- "boat-tail", "flat-base", "rebated-boat-tail"
          + tip_type      String?   -- "polymer-tip", "open-tip", etc.
          + construction  String?   -- "cup-and-core", "bonded", etc.
```

Zero cost to define, no migration later.

---

### 3. Enrich Caliber Metadata in Backend (Export Selectively)

**What:** Curate the following additional fields on the Caliber entity in the backend. Export only the subset needed for V1's on-device use case; the rest is ready when caliber detail pages are built.

**Additional Caliber fields for the backend:**

```
Caliber:  + coal_inches           Float?     -- Max cartridge overall length
          + max_pressure_psi      Int?       -- SAAMI MAP
          + rim_type              String?    -- "rimless", "rimmed", "belted", "rebated"
          + action_length         String?    -- "mini", "short", "long", "magnum"
          + parent_caliber_id     UUID?      -- FK → Caliber (self-referential)
          + year_introduced       Int?
          + is_common_lr          Bool       -- Common long-range cartridge? (display/filter)
          + description           String?    -- Editorial, e.g., "The dominant precision rifle cartridge..."
```

**Why:** These are trivially curated for 15-20 records (15 minutes per caliber). The earlier proposal had all of these and they're the right list. Not having the data when the design calls for it is more expensive than curating it now. `action_length` and `is_common_lr` are immediately useful for search filtering even in V1. `parent_caliber_id` powers the cartridge family tree display that makes our caliber pages richer than anything in any competing app.

**V1 bundled export includes:** Everything currently in the proposal, plus `action_length`, `is_common_lr`, `popularity_rank`, and `description`. The dimensional/pressure fields (`coal_inches`, `max_pressure_psi`, `rim_type`) stay backend-only until caliber detail pages ship.

**Note:** This resolves the open question on `parent_case_id` — yes, add it now, curate it with the seed data, don't export it until there's a UI consuming it.

---

### 4. Add `alias_type` Metadata to Pipeline Backend

>  _Nice to Have_: Could defer if too complex.

**What:** The `alt_names` JSON array on each entity (this proposal's approach) is correct for the bundled export and on-device search. But in the pipeline's backend curation tooling, we should track *why* each alias exists.

**Why:** When reviewing and maintaining aliases, knowing that "Creedmore" is a misspelling, "SMK" is an abbreviation, and "81500" is a SKU helps with curation quality. It also helps when debugging search: if a search fails, we can check "do we have an abbreviation-type alias for this term?"

**Implementation:** In the backend pipeline database (not the bundled export), store aliases with metadata:

```python
# Backend alias storage (pipeline-side only)
class EntityAlias(Base):
    entity_type: str       # "caliber", "bullet", "cartridge", etc.
    entity_id: UUID
    alias: str             # The alias text
    alias_type: str        # "abbreviation", "misspelling", "alternate_name",
                           # "sku", "military_designation", "nickname",
                           # "discontinued_predecessor"
```

At export time, flatten to the `alt_names` JSON array on each entity (current behavior — no change to the bundled schema). The alias_type metadata stays in the pipeline for curation and debugging.

**Seed data examples** (from the earlier proposal — these should be curated during Step 2):

| entity | alias | alias_type |
|--------|-------|------------|
| Sierra MatchKing (bullet) | SMK | abbreviation |
| Sierra MatchKing (bullet) | HPBT | abbreviation |
| Hornady ELD Match (bullet) | ELDM | abbreviation |
| Hornady ELD Match (bullet) | ELD-M | abbreviation |
| Hornady ELD Match (bullet) | A-MAX | discontinued_predecessor |
| 6.5 Creedmoor (caliber) | 6.5 CM | abbreviation |
| 6.5 Creedmoor (caliber) | 6.5 Creedmore | misspelling |
| .308 Winchester (caliber) | 7.62x51 NATO | military_designation |
| Hornady (manufacturer) | Hornaday | misspelling |
| Berger (manufacturer) | Burger | misspelling |
| Hornady 140 ELD Match 6.5CM (cartridge) | 81500 | sku |
| Federal Gold Medal Match (cartridge) | GMM | abbreviation |
| .30-06 Springfield (caliber) | thirty-aught-six | nickname |

---

### 5. Include Worked Search Example in Documentation

**What:** The earlier proposal included a concrete worked example of a search query flowing through the system. This should be added to this proposal (or the engineer guide) as a reference for the iOS developer implementing search.

**The example (adapted from the earlier proposal):**

**User types:** `"hornady 140 eld 6.5"`

**Step 1 — Tokenize:** `["hornady", "140", "eld", "6.5"]`

**Step 2 — Abbreviation expansion:** `"eld"` → no exact expansion (it's a partial match, not a known abbreviation). Passes through to FTS5 where it matches "ELD Match" and "ELD-X" via prefix.

**Step 3 — FTS5 lookup across entity types:**
- `"hornady"` → matches Manufacturer "Hornady" and all entities with "Hornady" in `alt_names`
- `"140"` → matches Bullet `weight_grains = 140` (in `search_text`)
- `"eld"` → matches Bullet names containing "ELD" (ELD Match, ELD-X)
- `"6.5"` → matches Caliber aliases for 6.5 Creedmoor, 6.5 PRC, 6.5x55 Swede, etc.

**Step 4 — Result ranking:**
1. All 4 tokens matched → highest base relevance
2. Caliber `popularity_rank`: 6.5 Creedmoor (rank 1) >> 6.5 PRC (rank 4) >> 6.5x55 (rank 12)
3. Cartridge `popularity_rank` within 6.5 CM: ELD Match (rank 1) >> ELD-X (rank 5)
4. If active gun profile is set to 6.5 CM chamber → additional 1.5x boost (belt and suspenders)

**Top result:** Hornady 6.5 Creedmoor 140gr ELD Match (Cartridge)

**Auto-population on selection:**

| Load Profile field | Source | Value |
|---|---|---|
| manufacturer | Cartridge → Manufacturer.name | "Hornady" |
| bullet weight | Cartridge.bullet_weight_grains | 140 |
| bullet diameter | Bullet.caliber → Caliber.bullet_diameter_inches | 0.264 |
| BC G1 | Bullet.bc_g1_published | 0.646 |
| BC G7 | Bullet.bc_g7_estimated (AB value, if available) or bc_g7_published | 0.326 |
| muzzle velocity | Cartridge.muzzle_velocity_fps | 2710 |
| test barrel length | Cartridge.test_barrel_length_inches | 24 |

User still enters: zero distance, zero conditions, barrel-length MV adjustment.

---

### 6. Add `is_lead_free` Boolean to Bullet

**What:** Simple boolean flag. Defaults to false.

**Why:** California and several other states have lead-free ammunition requirements for hunting on public land. This is a real filter that real users need. Barnes TSX/TTSX, Hornady CX/GMX, Nosler E-Tip — these are the monolithic copper bullets that qualify. It's a trivially curated field for our dataset and enables a "lead-free only" filter toggle that no competing ballistics app offers.

```
Bullet:   + is_lead_free  Bool  (default false)
```

---

### 7. Bundled SQLite Export — Reference DDL

**What:** The earlier proposal included concrete `CREATE TABLE` and `CREATE VIRTUAL TABLE` SQL for the bundled on-device database. This proposal's Step 7 (export script) should produce output matching this pattern. Key design decisions from the earlier DDL that should carry forward:

- **Denormalize manufacturer names as strings** on the bundled tables (no Manufacturer FK on-device — just the name string). Eliminates joins for the most common read path.
- **Pre-compute `search_text`** on every entity: concatenate canonical name + `alt_names` + weight + manufacturer into a single text column that FTS5 indexes. One FTS5 match covers all search paths.
- **Denormalize `caliber_name`** as a string on Cartridge and RifleModel (avoids join for display).
- **Include `alt_names` as a JSON column** on bundled entities (not just in `search_text`), so the app can display "Also known as: 6.5 CM, 6.5 Creed" on detail screens if needed.
- **`schema_meta` table** with `schema_version`, `data_version`, `export_date`, and record counts.

The engineer should produce the actual DDL as part of Step 1. The earlier proposal's DDL (available in the data library research folder) is a valid starting reference.

---

### Summary of Schema Changes

All addendum items collected in one place for the engineer:

**Caliber (new fields):**
```
+ popularity_rank      Int?
+ coal_inches          Float?
+ max_pressure_psi     Int?
+ rim_type             String?
+ action_length        String?
+ parent_caliber_id    UUID?      FK → Caliber (self-ref)
+ year_introduced      Int?
+ is_common_lr         Bool       (default false)
+ description          String?
```

**Bullet (new fields):**
```
+ popularity_rank      Int?       (within-caliber rank — optional, may rank via cartridge instead)
+ base_type            String?    (nullable, V2 filtering)
+ tip_type             String?    (nullable, V2 filtering)
+ construction         String?    (nullable, V2 filtering)
+ is_lead_free         Bool       (default false)
```

**Cartridge (new fields):**
```
+ popularity_rank      Int?
```

**Pipeline backend (not bundled export):**
```
+ EntityAlias table with alias_type metadata
```

**Bundled export (DDL guidance):**
```
+ Denormalized manufacturer names (strings, no FK)
+ Pre-computed search_text column per entity
+ Denormalized caliber_name on Cartridge/RifleModel
+ alt_names JSON column retained on bundled entities
+ schema_meta table
```

**Documentation:**
```
+ Controlled vocabulary for type_tags and used_for (in seed data guide)
+ Worked search example (in this doc or engineer guide)
```
