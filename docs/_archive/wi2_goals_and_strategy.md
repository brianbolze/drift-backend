# WI-2: Ammo & Firearms Data Library — Goals & Strategy

*The strategic blueprint for what we're building, why it matters, and how we'll get there. This document bridges product intent and engineering execution.*

---

## What This Is

We're building a curated reference database of ammunition and firearms, paired with an on-device search system, that eliminates the friction between "I just bought this app" and "I have an accurate ballistic solution." This is the infrastructure that makes Pillar 1 (Effortless Data Entry) real.

But it's more than a data entry shortcut. Done right, this database becomes a compounding asset — a growing body of accurate, well-structured ballistic data that makes the app more valuable over time and increasingly difficult for competitors to replicate.

---

## Why This Matters More Than It Looks

The ballistic math is commoditized. Every app solves the same equations. The solver (WI-1) is necessary but not differentiating. What differentiates is *how fast and accurately a user gets the right inputs into that solver.* A wrong BC or an inaccurate muzzle velocity produces a mathematically correct but practically useless solution. The user misses, blames the app, and churns.

Today, every competitor's setup flow looks the same: manual entry of 10-15 fields, most of which require Googling. Hornady 4DOF avoids this — but only for Hornady ammo. Applied Ballistics has a bullet library, but it's bullets-only (no factory MV data) and locked inside their ecosystem. Ballistic AE has 5,000+ entries, but the data quality is inconsistent and the app is effectively abandoned.

Our opportunity: be the first app where a shooter types "140 ELD 6.5" and gets a fully populated, verified-correct load profile in two taps — factory MV included, BC provenance tracked, and every field traceable to a published source. That's the experience that turns a skeptic into a user in under three minutes.

### Connection to the Product Pillars

| Pillar | How This Work Item Serves It |
|--------|------------------------------|
| **Pillar 1: Effortless Data Entry** | Directly. This is the engine behind natural language search and auto-population. |
| **Pillar 2: DOPE Confidence** | Indirectly. Accurate starting data means the calculated-to-verified gap is smaller, building initial trust faster. A wrong auto-filled BC undermines the entire confidence system. |
| **Pillar 3: Premium Design** | The Caliber entity enables rich detail pages — caliber illustrations, common loads, typical use cases. The database makes the app feel *knowledgeable*, not just pretty. |
| **Pillar 4: Data Safety** | The bundled DB is read-only reference data, separate from user data. Clear separation means DB updates never touch user profiles. No silent mutations. |
| **Pillar 5: Arsenal & Inventory** | Ammo search powers quick inventory entry. Rifle model data pre-fills gun profiles. |

---

## Goals

### Goal 1: Speed to First Solution

**Target:** A new user finds their factory ammo and has a fully populated load profile in <60 seconds from their first search.

This is the <3 minute "install to first accurate solution" target from the product doc, and the data library is the biggest lever. The three-tap ideal — "click rifle, click ammo, view range card" — requires the database to resolve a natural language query into a complete set of solver inputs: bullet weight, diameter, BC (with correct drag model), and factory muzzle velocity.

**What this means for the database:** Coverage of the most-shot loads must be near-complete. If a user can't find their ammo on the first search, they fall back to manual entry — and we've lost the moment. The hit rate on the first search for our beachhead users (PRS competitors, Shooter app migrants, precision hobbyists) should be >90%.

### Goal 2: Correctness Over Coverage

**Target:** Every record in the bundled database is traceable to a published manufacturer source, with no unverified BC values.

200 verified-correct loads beats 500 with scattered errors. A wrong BC value doesn't just produce a bad solution — it produces a *quietly* bad solution. The user dials their scope, shoots, misses by 0.3 mils at 700 yards, and blames the app. They'll never diagnose that the BC was wrong. They'll just switch to Applied Ballistics.

**What this means for the pipeline:** Every record needs source provenance (URL + date). BC values from manufacturer product pages are the baseline. Applied Ballistics measured values, when available, are noted as higher-confidence alternatives. Any value the pipeline is uncertain about gets flagged for human review rather than shipped. The quality gate is: *would I trust this data to make my own holds at 1,000 yards?*

### Goal 3: The Bullet Is the Canonical Unit

**Target:** A data model where bullet (projectile) properties are stored once and reused across every factory cartridge and user load profile that contains that bullet.

This is the single most important structural decision. A Hornady 140gr ELD Match bullet has one set of properties (weight, diameter, G7 BC 0.326, G1 BC 0.646). That bullet appears in factory loaded 6.5 Creedmoor (MV 2710, 24" test barrel), factory loaded 6.5 PRC (MV 2960, 24" test barrel), and an unknown number of handloader recipes at custom velocities. The bullet data shouldn't be duplicated across all of these — it should be stored once and referenced.

When Hornady updates their published BC (they've done this — the ELD Match G1 shifted from 0.585 to 0.646 in revised literature), we update one bullet record. Every cartridge and every user load profile referencing that bullet inherits the correction. No hunting for duplicates. No inconsistencies.

### Goal 4: Caliber as a First-Class Entity

**Target:** A Caliber entity rich enough to power search filtering, informational detail pages, and contextual search ranking — not just a text string on a load profile.

Caliber is how shooters organize their mental model. When someone walks into a gun store, they don't say "I need a .264 diameter bullet" — they say "I need 6.5 Creedmoor ammo." When someone browses ammo online, they filter by caliber first, then manufacturer, then bullet weight.

Our Caliber entity should support: dropdown/filter selection in search, informational detail pages (caliber specs, parent case, typical use cases, common factory loads), contextual search boosting (if your active gun is 6.5 CM, searching "140 ELD" should rank 6.5 CM results first), and caliber-family browsing ("show me all 6.5mm cartridges" or "show me all short-action calibers").

This is also where product design can shine. A well-designed caliber page with a cartridge illustration, key specs, and curated factory ammo listings would be unlike anything in any existing ballistics app — and it leverages the data we're already collecting.

### Goal 5: Search That Matches How Shooters Talk

**Target:** Fuzzy, alias-aware search that resolves abbreviations, misspellings, and partial queries into the right results — and feels instant.

The abbreviation vocabulary in this community is dense: ELDM, SMK, BTHP, OTM, TMK, ABLR, VLD, LRHT. These aren't edge cases — they're the primary way people refer to bullets. "SMK 175" is how a .308 match shooter talks about the Sierra 175gr MatchKing. "Berger Hybrids" means Berger Hybrid Target. "Gold Medal" means Federal Gold Medal Match. "Creedmore" (with an E) is a common misspelling that should still resolve.

Search aliases are first-class data, not a nice-to-have optimization. The alias table is curated editorial content that ships with the database and is maintained alongside the spec data.

The search should also be contextual: if the user has a gun profile set to 6.5 Creedmoor, caliber-matched results should rank higher without the user having to specify caliber. The active gun profile is a strong signal for what the user is looking for.

### Goal 6: Build a Pipeline, Not a Spreadsheet

**Target:** Infrastructure that makes ongoing database expansion low-effort and high-confidence.

The initial ~200-300 loads are the MVP. But the value of this database compounds over time. New products launch (Hornady released the 7mm PRC A-Tip in 2025). Users request loads we don't have. Community handloaders need component bullet data that doesn't come from factory cartridge pages.

The pipeline — scraping, LLM-assisted extraction, entity resolution, human review, bundled export — should be designed so that adding 50 new loads is an afternoon of work, not a week. Monthly re-scrapes catch spec corrections. Coverage dashboards show what's missing. The export pipeline stamps a version number and ships.

This is directly informed by the Doro experience: you've built entity resolution and structured data pipelines before. The difference here is the domain-specific quality bar (a wrong BC is worse than a wrong company description) and the smaller but more curated dataset.

---

## Strategy

### Data Model: Four Entities + Search Layer

The research confirms a four-entity model with a supporting alias/search layer:

```
Caliber (first-class entity, hand-curated, ~15-20 records at MVP)
│
├── bullet_diameter links to ──→ Bullet (projectile, the canonical reusable unit, ~200-300 records)
│                                  │
│                                  └──< Cartridge (factory loaded ammo, ~200-300 records)
│                                        references caliber_id + bullet_id
│
RifleModel (independent reference data, ~50-100 records)

SearchAlias (alias → entity mapping for fuzzy search)
```

**Why four entities, not one flat table:**

The flat table approach (one row per factory load with all bullet properties inline) is simpler to build but creates three problems. First, the same bullet's BC gets duplicated across every cartridge that contains it, creating inconsistency risk. Second, handloaders — who select a bullet but enter their own MV — don't fit the model (they have no "cartridge"). Third, the Caliber entity can't exist as a first-class thing with its own properties and detail page if it's just a text field on a load.

The normalized model costs us some join complexity in search queries. But the bundled SQLite database is small enough (~1MB) that this has zero performance impact. The correctness and extensibility gains are worth it.

### Caliber Entity — Richer Than a Lookup Table

Research revealed that caliber is messier than it looks on the surface (names don't always match diameters, military/commercial equivalents are subtly different, parent-case relationships exist) but also more bounded than feared for our use case. At MVP, we need ~15-20 caliber records covering priority tiers 1-4.

The Caliber entity carries enough metadata to power informational display and search filtering:

**Core fields:** name, bullet diameter (inches + mm), case length, COAL, max SAAMI pressure, action length (short/long/magnum), rim type, parent case (nullable FK), year introduced.

**Display fields:** typical bullet weight range, typical MV range, common twist rates, common barrel lengths, typical use cases (match/hunting/varmint).

**Alias layer:** "6.5 CM", "6.5 Creed", "Creedmore" (misspelling), ".308 Win", "7.62x51" all resolve to the right caliber record.

**The .308 Win / 7.62x51 NATO decision:** Store as separate Caliber records with a cross-reference alias. For ballistic computation, they're identical (same bullet diameter, same BCs). For safety, they're distinct. We are a ballistics calculator, not a chamber compatibility guide — but we store the distinction so we're never accused of conflating them. Search for either resolves both, but the primary result matches the query.

### Bullet Entity — The Canonical Truth

The Bullet entity represents a physical projectile. It carries the properties that matter for ballistic computation and don't change based on how the bullet is loaded or what cartridge it's in.

**Core fields:** manufacturer, name/product_line, weight (grains), diameter (inches), bc_g1 (Float?), bc_g7 (Float?), bc_source (enum: manufacturer / applied_ballistics / community), sectional_density (computed).

**Extended fields (optional at V1):** bullet_length (inches — for spin drift; Berger and AB publish this), minimum_twist_rate, bullet_type (free text — "ELD Match", "Hybrid Target", "MatchKing"), base_type (flat / boat_tail / rebated), ogive_type (tangent / secant / hybrid), tip_type (open / polymer / aluminum), construction (jacketed / monolithic / bonded), use_case (match / hunting / varmint / general).

**Velocity-banded BCs:** Stored as optional JSON metadata (bc_g1_stepped, bc_g7_stepped) for Sierra-style banded data and Hornady Mach-number data. These are reference/provenance data, not the solver's primary input. The solver uses the single bc_g1 or bc_g7 value.

**What we're NOT storing:** Custom drag models (CDMs). Both Applied Ballistics and Hornady 4DOF use proprietary CDMs that aren't published or accessible. Our solver uses G1/G7 BCs. If we ever add CDM support, it's a solver upgrade, not a database change.

### Cartridge Entity — Factory Loaded Ammo

The Cartridge entity represents a specific factory-loaded ammunition product — a bullet loaded in a case with powder, ready to fire.

**Core fields:** caliber_id (FK → Caliber), bullet_id (FK → Bullet), manufacturer (String — can differ from bullet manufacturer, e.g., Federal loads Sierra bullets), product_line, muzzle_velocity (fps), test_barrel_length (inches), item_number/SKU, UPC (optional).

**The manufacturer distinction matters:** A Federal Gold Medal Match 6.5 Creedmoor cartridge (manufacturer: Federal) contains a Sierra 140gr MatchKing bullet (bullet manufacturer: Sierra). The Cartridge's manufacturer is Federal; the Bullet's manufacturer is Sierra. Users care about both: "Federal loads Sierra bullets" is meaningful information.

**Muzzle velocity context:** Factory MV is measured from a specific test barrel length. We store both values and display them together: "MV: 2,710 fps (24" test barrel)." This sets the right expectation — the user's actual MV will differ based on their barrel length, and the DOPE confidence system picks up from there.

**Linking Bullet to Cartridge:** No manufacturer explicitly publishes which component bullet SKU goes into which loaded cartridge. The link is established through our entity resolution layer, matching on (manufacturer + bullet name/line + weight + caliber). This is inferred, not declared — and the confidence of the inference should be tracked in the pipeline.

### RifleModel Entity — Intentionally Lightweight

Research confirmed this is boringly consistent for our priority calibers. Every major 6.5 CM precision rifle ships with 1:8 twist, 22-24" barrel. .308 Win is slightly more varied (1:10 to 1:12). The value here is convenience (auto-fill barrel length and twist rate when a user selects their rifle), not essential data.

**Fields:** manufacturer, model, caliber_id (FK → Caliber), barrel_length (inches), twist_rate (Float — e.g., 8.0 for 1:8), twist_direction (enum, default right), action_type (bolt/semi-auto), weight (lbs, optional).

**Scope:** ~50-100 records covering the most popular models from Bergara, Tikka, Ruger, Savage, Howa, and a handful of custom/higher-end names (Accuracy International, MPA, Seekins). Enough to auto-fill for the majority; everyone else enters manually.

### Search Architecture — Two Tiers

**On-device (primary, offline-capable):** SQLite FTS5 with a pre-built search index covering: manufacturer, product_line, bullet_name, caliber name + aliases, bullet weight. Trigram matching for typo tolerance. Alias table for abbreviation resolution. Optional caliber context parameter from the active gun profile for ranking boost.

**Backend API (secondary, online):** For broader search, new products not yet in the bundled DB, and analytics on what users search for but can't find (coverage gap signal). FastAPI endpoint returning ranked results. Not required for core functionality — the bundled DB must stand alone.

**Search alias table:** This is curated editorial data, not computed. Every common abbreviation (ELDM, SMK, BTHP, TMK, ABLR, VLD, LRHT), every misspelling ("Creedmore", "Hornaday", "Burger" for Berger), every military designation (M118LR, M855), and every retired product name (A-MAX → ELD Match) gets an entry. The alias table ships with the bundled DB and is updated alongside the spec data.

---

## What We're Explicitly Not Doing

Scope discipline matters, especially for a side project. These are conscious exclusions, not oversights:

**Handloader recipe data.** We're not modeling powder charges, primer types, or load recipes. Our Bullet entity serves handloaders (they select a bullet, get BC data, enter their own MV). The reloading database world (Hodgdon, Sierra LoadData, 300K+ recipes) is a separate domain we don't need to enter.

**Chamber compatibility / safety advice.** We note that .308 Win and 7.62x51 NATO are distinct calibers. We do not advise on whether ammunition is safe to fire in a given chamber. This is a liability minefield with no upside for a ballistics calculator.

**Custom drag models.** Both AB and Hornady use proprietary CDMs that aren't accessible. Our solver uses G1/G7 BCs. CDMs are a future solver upgrade, not a database concern.

**Pricing or availability data.** AmmoSeek exists for this. Not our domain.

**Over-the-air database updates for V1.** The bundled SQLite ships with each app release. When we add loads, we cut a new app version. The App Store is the distribution mechanism. Add delta sync later if the update cadence demands it (unlikely at monthly refresh pace).

**Powder temperature sensitivity on MV.** Real effect (~1-2 fps/°F), modeled by Strelok, but V2 at earliest. The Cartridge schema includes a nullable field for future use.

---

## Implementation Sequence

### Phase 1: Schema & Seed (Week 1)

Define the four-entity schema (Caliber, Bullet, Cartridge, RifleModel) plus the SearchAlias table. Hand-curate 30-50 of the highest-priority records — the loads our beachhead users actually shoot. This becomes the ground truth for validating the automated pipeline.

Priority seed list: Hornady 140 ELD Match in 6.5 CM, Hornady 147 ELD Match in 6.5 CM, Federal Gold Medal 140 SMK in 6.5 CM, Berger 140 Hybrid Target in 6.5 CM, Hornady 178 ELD-X in .308, Federal Gold Medal 175 SMK in .308, Federal Gold Medal 168 SMK in .308, Berger 185 Juggernaut in .308. Plus the corresponding component bullets and caliber records.

### Phase 2: Scraping Pipeline (Weeks 2-3)

LLM-assisted extraction against the four-entity schema. Start with Hornady (best-documented, most popular), then Berger, Sierra, Federal. Every extracted record gets diffed against the manual seed for accuracy validation. Entity resolution layer matches bullets to cartridges through (manufacturer + bullet_name + weight + caliber).

### Phase 3: On-Device Search (Week 3-4)

SQLite FTS5 index build. Alias table population. Trigram fuzzy matching. Test against the query patterns from the spec (partial matches, abbreviations, caliber-first, manufacturer-first, typos, SKUs). Caliber-context ranking from active gun profile.

### Phase 4: Human Review & Export (Week 4)

Review pipeline — every record that enters the bundled DB gets human approval for V1. Simple CLI tool: show extracted record, approve/reject/edit. Coverage dashboard: what percentage of "priority loads" are in the database? Export to compressed SQLite with schema version number.

### Phase 5: Expand Coverage (Ongoing)

Nosler, Lapua, Barnes, Norma. Expand caliber tiers 2-4. Monthly re-scrapes. Community feedback on missing loads. Coverage target: 90%+ hit rate on user searches within 60 days of launch.

---

## How We'll Know It's Working

| Metric | Target | How We Measure |
|--------|--------|----------------|
| Search hit rate | >90% of first searches find the user's ammo | Analytics: search query → did user select a result? |
| Time to populated profile | <60 seconds from first search | User testing, instrumented timing |
| BC accuracy | 100% match to published manufacturer value | Audit against source URLs |
| Database coverage (priority loads) | >80% of top loads by community popularity | Coverage report vs. forum/Reddit frequency analysis |
| Search alias coverage | Common abbreviations resolve correctly | Test suite against curated query list |
| Bundled DB size | <2MB | Build artifact measurement |

---

## Open Questions

1. **Multiple BC sources per bullet.** When both the manufacturer and Applied Ballistics publish a G7 BC and the values differ, do we store both with provenance? Or pick one as canonical? The former is more honest; the latter is simpler for the solver. Leaning toward: store both, use manufacturer as default, surface AB value as "independently measured" for advanced users.

2. **Hornady BC discrepancy between pages.** Hornady's ammo product page and bullet product page sometimes show different BC values for the same physical bullet (the ammo page has historically shown a slightly lower G7). Pipeline rule: scrape BC from the bullet/component page, not the cartridge/ammo page. The bullet page is the canonical source.

3. **How much bullet classification metadata for V1?** The multi-axis classification (base_type × ogive_type × tip_type) is correct but may be overbuilding for launch. Minimum viable: a single `bullet_type` text field plus the alias table for abbreviation search. Add structured classification fields if the caliber detail page design calls for them.

4. **Caliber detail page scope.** How rich do we want caliber pages at launch? Minimal (name, specs, list of matching ammo) or richer (illustration, parent case tree, common rifles, typical use cases)? This affects how much Caliber metadata we curate upfront.

---

*Created: February 2026*
*Informed by: wi2_research_findings.md, ammo_db_research_notes.md, product.md, context.md, roadmap.md, research notes - app store + reddit.md, design hypotheses.md*
