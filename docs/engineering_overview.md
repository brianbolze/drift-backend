# Drift Ballistics — Engineering Overview

*Everything an engineer needs to know to contribute effectively. Read this first, then the specific work item docs.*

------

## What We're Building

A precision ballistics calculator app for iOS. Shooters enter their rifle and ammunition specs, and the app computes hold values (how much to adjust their scope) at any distance given current atmospheric conditions. Think of it as a specialized scientific calculator with a database layer and rich profiles.

**Platform**: iOS native (Swift / SwiftUI) **Architecture**: Local-first, offline-capable, no account required for core features **Backend**: Python / FastAPI for data pipeline and search infrastructure **Target**: MVP in 8-10 weeks

------

## Why This Matters (The Short Version)

Existing ballistics apps either have good math but terrible UX (Applied Ballistics), or decent UX but limited data (Hornady 4DOF). The market leader just did a major redesign that broke user trust — mass data loss, corrupted profiles, broken hardware integrations. There's an opening for a reliable, well-designed alternative.

Our edge: the founder is the target user, the data pipeline tech is directly reusable from a previous company (Doro), and AI/ML tools now make smart data entry feasible in a way that wasn't possible three years ago.

------

## Domain Primer

You don't need to be a shooter to work on this, but you need to understand the core concepts.

### What a Ballistic Solution Is

A bullet follows a predictable trajectory governed by physics: gravity pulls it down, air resistance slows it, wind pushes it sideways. A "ballistic solution" computes how much a shooter needs to adjust their scope to hit a target at a given distance.

**Inputs:**

- Bullet properties: weight (grains), ballistic coefficient (BC), caliber
- Rifle properties: muzzle velocity (fps), barrel twist rate, scope height over bore
- Zero: the distance at which the rifle is currently calibrated (typically 100 yards)
- Atmosphere: temperature, barometric pressure, humidity, altitude
- Wind: speed and direction relative to the shooter
- Target: distance (yards or meters)

**Outputs:**

- Elevation hold: how much to adjust vertically (in MOA or Mils)
- Windage hold: how much to adjust horizontally (in MOA or Mils)
- Click count: elevation/windage converted to scope adjustment clicks
- Secondary: bullet drop (inches), time of flight (seconds), remaining velocity (fps), remaining energy (ft-lbs)

### Units That Matter

| Unit                         | What It Is                        | Conversion                                                   |
| ---------------------------- | --------------------------------- | ------------------------------------------------------------ |
| **MOA** (Minute of Angle)    | Angular measurement               | 1 MOA ≈ 1.047" per 100 yards                                 |
| **Mil / MRAD** (Milliradian) | Angular measurement               | 1 Mil ≈ 3.6" per 100 yards                                   |
| **Grains (gr)**              | Bullet weight                     | 1 grain = 0.0648 grams                                       |
| **FPS**                      | Muzzle velocity (feet per second) | Typical range: 2,400-3,200 fps                               |
| **BC**                       | Ballistic coefficient             | Dimensionless, typically 0.1-0.8. Higher = less drag.        |
| **G1 / G7**                  | Drag models                       | G1 = traditional, G7 = modern boat-tail bullets (more accurate for long range) |

Scopes have a "click value" — the angular adjustment per click of the turret. Common values: 0.25 MOA/click or 0.1 Mil/click. The app needs to convert hold values to click counts for the user's specific scope.

### What "DOPE" Means

DOPE = Data On Previous Engagement. It's a shooter's personal record of verified hold values at known distances. Example: "At 500 yards with my setup, I hold 3.4 mils up and 0.5 mils right in an 8 mph crosswind."

Calculated DOPE (from an app) is a starting point. Shooters verify and refine it by actually shooting at those distances and recording corrections. This process is called "truing." No app currently helps manage this transition from calculated to verified — that's a key part of our product thesis, though the specific UX is still being tested.

### What "Truing" Means

Truing is the process of adjusting your ballistic inputs (usually muzzle velocity or BC) so that calculated solutions match observed real-world impacts. Example: if your app says to hold 3.3 mils at 500 yards but you consistently impact 0.2 mils low, your actual muzzle velocity is probably lower than entered. Adjusting MV from 2,710 to 2,690 fps might correct the solution across all distances.

This is important context for the impact logging data model — we'll eventually want to derive these corrections from logged data.

------

## Technical Architecture

```
┌─────────────────────────────────────────────┐
│                  iOS App                     │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ SwiftUI  │  │ Ballistic│  │  Local DB  │  │
│  │   Views  │──│  Solver  │  │ (SwiftData)│  │
│  │          │  │ (Swift)  │  │            │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│       │                           │          │
│  ┌──────────┐            ┌───────────────┐   │
│  │ Atmo     │            │ Bundled Ammo  │   │
│  │ Service  │            │ DB (SQLite)   │   │
│  └──────────┘            └───────────────┘   │
│       │                         ▲            │
└───────│─────────────────────────│────────────┘
        │                         │
        ▼                         │ periodic sync
   Weather API               ┌───┴────────────┐
   (Open-Meteo)              │  Backend API    │
                             │  (FastAPI)      │
                             │                 │
                             │ ┌─────────────┐ │
                             │ │  Scraping    │ │
                             │ │  Pipeline    │ │
                             │ └─────────────┘ │
                             │ ┌─────────────┐ │
                             │ │  Ammo/Gun   │ │
                             │ │  Master DB  │ │
                             │ └─────────────┘ │
                             │ ┌─────────────┐ │
                             │ │  Search /   │ │
                             │ │  Fuzzy Match│ │
                             │ └─────────────┘ │
                             └─────────────────┘
```

### Key Architectural Decisions

**Local-first, offline-capable.** Core features (solver, profiles, DOPE) must work with zero connectivity. Ranges and hunting areas frequently have no cell service. This is a churn trigger when absent — competitors have lost users specifically because their app required connectivity.

**No account required for core features.** Users can use the full calculator and profile management without creating an account. Accounts are only needed for optional cloud sync/backup.

**Bundled database with periodic updates.** The ammo/firearms database ships with the app and is searchable offline. Updates are pulled when connectivity is available — not blocking, not required.

**UUIDs everywhere.** All entities (guns, loads, inventory items, future: impacts, sessions) use UUID identifiers. This makes eventual cloud sync dramatically easier (no ID collisions between devices). Build this in from day one.

**Solver as a standalone package.** The ballistic solver should be a pure Swift package with no UI or persistence dependencies. Clean inputs → clean outputs. Fully testable in isolation. This is the most safety-critical code in the app — people make real decisions based on its output.

------

## Data Model (Core Entities)
NOTE: Read through the python files in `src/drift/models` for the most up to date info on the data schema. 

These are the entities we're confident about regardless of which product direction wins in prototype testing. Schema should be extensible — we'll almost certainly add confidence states, truing history, or session data later.

### Gun Profile

```
id: UUID
name: String                    // User-assigned name, e.g. "Bergara HMR"
make: String?                   // e.g. "Bergara"
model: String?                  // e.g. "B-14 HMR"
caliber: String                 // e.g. "6.5 Creedmoor"
barrelLength: Double?           // inches
twistRate: Double?              // e.g. 8.0 (meaning 1:8)
twistDirection: Enum?           // .right (default) | .left
scopeHeightOverBore: Double     // inches, e.g. 1.75
clickValue: Double              // angular value per click, e.g. 0.1
clickUnit: Enum                 // .moa | .mil
reticleType: String?            // e.g. "EBR-7C MRAD"
notes: String?
createdAt: Date
updatedAt: Date
```

### Load Profile

```
id: UUID
gunId: UUID                     // FK → Gun Profile (loads belong to guns)
name: String                    // User-assigned or auto-generated
manufacturer: String?           // e.g. "Hornady"
productLine: String?            // e.g. "ELD Match"
bulletWeight: Double            // grains, e.g. 140
bulletDiameter: Double?         // inches, e.g. 0.264
bcG1: Double?                   // G1 ballistic coefficient
bcG7: Double?                   // G7 ballistic coefficient
muzzleVelocity: Double          // fps, e.g. 2710
zeroDistance: Double             // yards, e.g. 100
zeroTemperature: Double?        // °F at time of zero
zeroPressure: Double?           // inHg at time of zero (station pressure)
zeroAltitude: Double?           // feet ASL at time of zero
notes: String?
ammoDbId: String?               // FK → bundled ammo database entry, if sourced from DB
createdAt: Date
updatedAt: Date
```

### Atmospheric Snapshot

```
id: UUID
temperature: Double             // °F
pressure: Double                // inHg (station pressure, NOT sea-level adjusted)
humidity: Double                // 0-100%
altitude: Double                // feet ASL
windSpeed: Double               // mph
windDirection: Double            // degrees, 0=headwind, 90=right-to-left, etc.
latitude: Double?
longitude: Double?
source: Enum                    // .manual | .weatherApi | .kestrel
timestamp: Date
```

### Inventory Item

```
id: UUID
loadId: UUID                    // FK → Load Profile
quantity: Int                   // rounds on hand
location: String?               // e.g. "Safe", "Range bag"
notes: String?
updatedAt: Date
```

### Impact Record (for future use — schema only, no UI yet)

```
id: UUID
loadId: UUID                    // FK → Load Profile
distance: Double                // yards
holdElevation: Double           // mils or MOA used
holdWindage: Double             // mils or MOA used
holdUnit: Enum                  // .moa | .mil
impactOffsetVertical: Double    // mils or MOA, positive = high
impactOffsetHorizontal: Double  // mils or MOA, positive = right
atmosphereId: UUID?             // FK → Atmospheric Snapshot
notes: String?
timestamp: Date
```

### Important Notes on the Schema

**Station pressure vs. sea-level pressure**: This is a common source of bugs in ballistics apps. Weather services typically report sea-level adjusted barometric pressure. Ballistic solvers need *station pressure* (actual pressure at the shooter's altitude). The app must either ask for station pressure directly or convert from sea-level pressure using altitude. Getting this wrong produces systematic elevation errors that increase with distance. The atmospheric service should handle this conversion.

**G1 vs G7 BC**: Most manufacturers publish G1 BCs. G7 is more accurate for modern long-range bullets. Some bullets have both published. The solver needs to accept either and use the appropriate drag model. The database should store both when available.

**Load → Gun relationship**: Loads belong to guns (a specific load is sighted in on a specific rifle). The same ammunition product might exist as different load profiles on different guns with different muzzle velocities and zeros. This is the "rifle-first" organization that users expect.

------

## What's Being Decided in Parallel

While engineering work starts on the items below, the product team is testing three prototype directions with real shooters. The prototypes test different product *architectures* — not just different features:

- **Prototype A**: Full toolkit (calculator + arsenal + inventory + dispersion analysis)
- **Prototype B**: DOPE-card-centric (organized around the calculated → verified journey)
- **Prototype C**: Session-centric (organized around range sessions with an AI companion)

The engineering work described in the companion docs is **architecture-independent** — it's needed regardless of which direction wins. Anything that assumes a specific product architecture (session data models, DOPE confidence state machines, AI coaching) will start after prototype testing gives us signal.

------

## Glossary — Domain Terms

| Term                 | Meaning                                                      |
| -------------------- | ------------------------------------------------------------ |
| **DOPE**             | Data On Previous Engagement — your verified holds at known distances |
| **MOA**              | Minute of Angle — ~1.047" per 100 yards                      |
| **Mil/MRAD**         | Milliradian — ~3.6" per 100 yards                            |
| **BC**               | Ballistic Coefficient — drag resistance measure (higher = less drag) |
| **G1/G7**            | Drag models. G7 is preferred for modern boat-tail bullets.   |
| **MV**               | Muzzle Velocity — speed of bullet leaving the barrel (fps)   |
| **SD**               | Standard Deviation — measure of velocity consistency shot-to-shot |
| **ES**               | Extreme Spread — difference between fastest and slowest shots in a string |
| **Truing**           | Adjusting inputs (MV, BC) so calculated solutions match real-world impacts |
| **Station pressure** | Actual barometric pressure at your altitude (NOT the sea-level adjusted value weather apps show) |
| **DA**               | Density Altitude — a single number combining temp, pressure, humidity effects on air density |
| **Kestrel**          | Brand of weather meter popular with shooters — measures temp, pressure, humidity, wind |
| **Chrono**           | Chronograph — device that measures muzzle velocity           |

------

## Glossary — Backend Engineering Terms

Terms specific to this repo's pipeline, models, and tooling. Source of truth for each is in parentheses.

### Schema and provenance

| Term | Meaning |
| --- | --- |
| **Bullet** | Canonical projectile entity. Cartridge and UserLoadProfile reference Bullet (not the reverse). (`src/drift/models/bullet.py`) |
| **Cartridge** | Factory loaded ammunition. Holds a FK to one Bullet via `bullet_id` plus a confidence + method describing how that link was made. (`src/drift/models/cartridge.py`) |
| **Caliber vs Chamber** | Caliber is a cartridge dimension (e.g. .223 Rem). Chamber is a rifle property (e.g. .223 Wylde). One chamber can accept multiple calibers. (`src/drift/models/{caliber,chamber}.py`) |
| **EntityAlias** | Many-to-one mapping from a raw extracted name → canonical entity row. Used by curation and pipeline alike — never match manufacturer/caliber/bullet names by raw string. (`src/drift/models/entity_alias.py`) |
| **BulletProductLine** | Cross-manufacturer grouping of bullets that share a product family name (e.g. "ELD Match", "VLD Hunting"). Drives the Tier 2 product-line resolver tier. (`src/drift/models/bullet_product_line.py`) |
| **BulletBCSource** | Audit row for one BC observation (G1 or G7) on a Bullet, with `source` (manufacturer / cartridge_page / third_party) and `source_url`. Multiple sources per bullet allowed; never write a BC to Bullet without also writing a BulletBCSource. (`src/drift/models/bullet.py`) |
| **data_source** | Per-row column on bullet/cartridge/rifle. Values: `manual` (curation), `extracted` (pipeline), `seed`, `legacy`. Drives is_locked defaults and is stripped on production export. |
| **is_locked** | Boolean on bullet/cartridge/rifle. When true, the pipeline-store will not overwrite the row even if a higher-confidence match comes in. Curation patches set this to true on every record they create. |
| **extraction_confidence** | LLM-reported per-record confidence (0–1) carried through from the extract stage. Stripped on production export. |
| **bullet_match_method** / **bullet_match_confidence** | Per-cartridge provenance of the cartridge → bullet linkage (e.g. `composite_key`, `fuzzy_name`, `product_line+weight`) so we can audit how a particular row got its bullet. Persisted on Cartridge. |
| **display_name** | Canonical human-readable name builder for each entity type. Always use these — never concatenate name fields ad hoc. (`src/drift/display_name.py`) |

### Pipeline and resolution

| Term | Meaning |
| --- | --- |
| **manifest** | The seed list of URLs the pipeline scrapes, one per entity type. Lives under `data/pipeline/manifest/`. |
| **batch API** | Anthropic's [Message Batches](https://docs.claude.com/en/api/messages-batches) endpoint — 50% cheaper, no rate limits, ~24h SLA. Default for Anthropic extraction. |
| **reducer strategy** | Per-domain HTML reduction approach. Options: `generic` (BeautifulSoup strip), `main_content` (semantic main-content extraction), `jsonld_only` (extract only JSON-LD blocks for SPA pages). See `DOMAIN_REDUCER_STRATEGY` in `src/drift/pipeline/config.py`. |
| **normalize_entity** | Raw-text → canonical-key normalization (case fold, punctuation, abbreviations). Applied before alias lookup and fuzzy matching. (`src/drift/pipeline/normalization.py`) |
| **lookup_entity** | Deterministic `name → entity_id` resolution via the EntityAlias table. Shared between curation and pipeline so both paths agree on what "Hornady" means. (`src/drift/resolution/aliases.py`) |
| **EntityResolver** | Three-tier resolver (SKU → composite key → fuzzy name) used by `pipeline_store`. Returns a `MatchResult`. (`src/drift/pipeline/resolution/`) |
| **ResolutionConfig** | Frozen dataclass holding every threshold, tolerance, and confidence scalar the resolver uses. Tune via constructor injection; the default is captured by `tests/test_resolution_golden_set.py`. (`src/drift/pipeline/resolution/config.py`) |
| **MatchResult** | Resolver output: `entity_id`, `confidence`, `method`, `alternatives` (top runner-ups), `methods_tried`, `is_ambiguous` (gap to runner-up < threshold). |
| **token_set_ratio** | rapidfuzz similarity metric (0–1) used for fuzzy-tier name comparison. Order-insensitive, bag-of-tokens. |
| **action gates** | The `match_confidence_threshold`, `auto_create_confidence_ceiling`, `alias_auto_promote_threshold` knobs in ResolutionConfig that decide whether the store auto-matches, auto-creates, flags for review, or auto-promotes an EntityAlias. |
| **rejected_calibers** | `data/pipeline/rejected_calibers.json` — explicit allowlist-by-exclusion of calibers we don't ingest (pistol, shotgun, exotic). The store auto-rejects any extracted entity referencing one. |
| **dry-run** | Default mode for `pipeline-store` and `curate`. Resolves and reports without committing. Pass `--commit` to write. |
| **savepoint-per-operation** | Curation isolation pattern — each YAML operation runs inside its own SQLite savepoint so a single failure doesn't poison the rest of the patch. |

### Tooling and publish

| Term | Meaning |
| --- | --- |
| **production DB** | `data/production/drift.db` — stripped iOS-bundled copy of `drift.db`. Drops pipeline tables (`alembic_version`, `bullet_bc_source`), drops pipeline columns (`data_source`, `is_locked`, `extraction_confidence`, `bullet_match_*`), filters bad rows (zero-MV, weight-mismatched, bogus-diameter), VACUUMs. (`scripts/export_production_db.py`) |
| **OTA publish** | Cloudflare R2 upload of `production/drift.db` + `manifest.json` to `data.driftballistics.com`. Auto-versioned, SHA-256 integrity, validates PK stability against the previous version. (`scripts/publish_db.py`) |
| **PK stability check** | Pre-publish guard that compares primary keys between the new and last-published production DBs. Failing PKs would invalidate iOS-side foreign-key references in user data. |
| **SCHEMA_VERSION** | Constant in `scripts/publish_db.py`. Bump when the production DB schema changes incompatibly so the iOS app can refuse to load mismatched bundles. |

------

*Last updated: April 2026*