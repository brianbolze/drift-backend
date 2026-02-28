# Optics, Reticles & the Variants Question: Engineering Recommendation

*Response to the design team brief. For: PM + design lead + iOS engineers.*

---

## TL;DR

1. **Option B (flat rows) for everything.** One row per buyable SKU. Group for display at query time. Don't build a parent/variant schema.
2. **Reticle as its own table — yes**, but keep it lean. Name, unit system, manufacturer FK, and a description. No subtension data in V1.
3. **The existing `RifleModel` is already Option B** — one row per chambering. No changes needed. Just add a `model_family` grouping column.
4. **Single bundled SQLite file** for all entities. Don't split by domain.
5. **Seed optics the same way we seed everything else**: hand-curated Python dicts, domain-expert reviewed. ~30–40 optic rows, ~15–20 reticle rows covers the beachhead.

---

## The Variants Question: Option B, and It's Not Close

Your instinct is right, but I want to make the case sharper than "it's simpler." The reason Option B wins isn't simplicity — it's that **Option A solves a problem we don't have and creates problems we don't need.**

### Why not Option A (parent + variant)

The normalized parent/child model is the right call when:
- The number of variants per parent is large or unpredictable (e.g., t-shirts with 12 colors × 8 sizes = 96 SKUs).
- Shared attributes change independently from variant attributes and you need transactional consistency.
- You're building a catalog management UI where humans edit parent-level fields and expect changes to cascade.

None of these apply to us:

- **Variant counts are tiny and stable.** Scopes: 2 (Mil/MOA). Rifles: 3–5 chamberings. This isn't a combinatorial problem.
- **Shared attributes don't change.** If we get the tube diameter wrong on a Vortex Viper PST, we fix it on 2 rows, not 200. The duplication cost is negligible.
- **We have no catalog management UI.** Data enters via seed scripts or pipeline. There's no "edit the parent and cascade" workflow. Updates are full table reseeds or row-level edits.
- **The on-device query path gets worse.** The iOS app needs complete, self-contained records for display. A parent+variant schema means the app either (a) does joins at query time (slower, more code), or (b) we denormalize at export time anyway — in which case we've built the normalized schema for zero benefit.

The one theoretical advantage of Option A — "it models the user's mental model" — is actually a UX concern, not a data model concern. The user's mental model is: "I have a Viper PST in Mil." The flat model with a grouping key produces exactly that UX: search returns grouped results, user taps to pick the variant. Whether the grouping lives in the schema (FK to parent) or in a column (`model_family`) is invisible to the user.

### The model_family grouping key

For both optics and rifles, add a `model_family` string column. This is a human-readable grouping key, not a computed hash.

```
Optic row 1:  model_family="Vortex Viper PST Gen II 5-25x50"  sku=PST-5258  reticle=EBR-7C MRAD
Optic row 2:  model_family="Vortex Viper PST Gen II 5-25x50"  sku=PST-5259  reticle=EBR-7C MOA
```

Why a readable string, not a hash:
- Debuggable. You can `SELECT DISTINCT model_family FROM optic` and immediately see the grouping.
- Editable. When the pipeline or a human reviewer gets it wrong, the fix is obvious.
- Sufficient. We're not deduplicating across millions of rows — we're grouping ~30–40 optics. A string works fine.

For display, the iOS app groups by `model_family` and shows variants as sub-options. The query is `SELECT * FROM optic WHERE search_text MATCH ? ORDER BY model_family, name` — one table, no joins.

### Implications for RifleModel

The existing `RifleModel` table is already Option B — one row per chambering, with `manufacturer_id`, `model`, and `chamber_id`. The Bergara B-14 HMR in 6.5 CM and .308 Win are two separate rows today. This is correct.

The only addition: a `model_family` column (e.g., `"Bergara B-14 HMR"`) so the app can group the chambering variants for display. This is a nullable String column — trivial migration when we get to it. No structural changes to the existing model.

### Implications for ammo

None. Cartridge is already one row per SKU. The "Hornady ELD Match 6.5 CM 140gr" and "Hornady ELD Match .308 175gr" are separate rows linked to separate Bullets and Calibers. The `product_line` column (`"ELD Match"`) already serves the same grouping purpose as `model_family`. No changes needed.

---

## Recommended Schema: Optic & Reticle

### Reticle

Separate table. This is the right call even for V1, for three reasons:

1. **Reticles have independent identity.** The Horus Tremor3 exists independently of any scope. It's licensed to Nightforce, Sig, and others. It has a name, a unit system, and (eventually) subtension data. That's an entity, not an attribute.
2. **Reticles are shared across optic variants.** The EBR-7C MRAD reticle appears in the Viper PST Gen II 5-25x50, the Viper PST Gen II 3-15x44, and the Razor HD Gen III 6-36x56. One Reticle row, many Optic rows pointing to it.
3. **Future value is high, current cost is low.** Reticle subtension tables (holdover marks at specific magnifications) are a V2 feature that shooters would love. Having the entity in place now means we don't need a migration later. And for V1, it's ~15–20 rows with 4 columns each. Trivial.

```
Reticle
├── id: UUID
├── name: String(255), indexed     -- "EBR-7C MRAD", "Tremor3", "H59", "MIL-XT"
├── alt_names: JSON?               -- ["EBR-7C", "7C MRAD"]
├── unit: String(10)               -- "mil" | "moa"
├── manufacturer_id: FK → Manufacturer  -- Who designed it (often scope maker, sometimes Horus/etc.)
├── description: Text?             -- Brief notes
├── source_url: String?
├── created_at / updated_at        -- TimestampMixin
```

The `unit` field is the reticle's measurement system, not the turret's. Most modern precision scopes match reticle and turret units, but not all — some SFP scopes have MOA reticles with MOA turrets, while a few oddball configs exist. The reticle unit and the optic's click unit are tracked separately.

### Optic

One row per buyable configuration (SKU). Flat, self-contained, groupable.

```
Optic
├── id: UUID
├── manufacturer_id: FK → Manufacturer
├── name: String(500), indexed     -- "Vortex Viper PST Gen II 5-25x50 EBR-7C MRAD"
├── alt_names: JSON?
├── model_family: String(255)?     -- "Vortex Viper PST Gen II 5-25x50" (grouping key)
├── product_line: String(255)?     -- "Viper PST Gen II" (broader product line)
├── sku: String(100)?, indexed
├── reticle_id: FK → Reticle
│
├── # Turret / click specs (what the wizard auto-fills)
├── click_unit: String(10)         -- "mil" | "moa"
├── click_value: Float             -- 0.1 (mil) or 0.25 (moa)
│
├── # Optical specs
├── magnification_min: Float       -- 5.0
├── magnification_max: Float       -- 25.0
├── objective_diameter_mm: Float   -- 50.0
├── tube_diameter_mm: Float        -- 30.0, 34.0, 35.0
├── focal_plane: String(10)        -- "ffp" | "sfp"
│
├── # Adjustment range
├── elevation_travel_mils: Float?  -- total elevation, in mils (convert MOA scopes)
├── windage_travel_mils: Float?    -- total windage, in mils
│
├── # Physical (nice to have, not ballistically critical)
├── weight_oz: Float?
├── length_inches: Float?
│
├── # Provenance
├── source_url: String?
├── created_at / updated_at
│
├── # Relationships
├── manufacturer → Manufacturer
├── reticle → Reticle
```

**Key decisions:**

- **`click_unit` and `click_value` live on Optic, not Reticle.** The turret click specs are a property of the scope configuration, not the reticle. The EBR-7C reticle exists in both Mil and MOA versions — the reticle etching determines the measurement marks, but the turret hardware determines the click value. In practice they match, but they're logically separate.
- **Travel stored in mils regardless of click unit.** Normalizing to one unit avoids conversion bugs downstream. The seed script can accept MOA values and convert (1 MOA ≈ 0.2909 mil). If we want to display "65 MOA / 35 Mil" to the user, we derive it.
- **No separate `OpticVariant` table.** The Mil and MOA versions of the same scope are two Optic rows with the same `model_family`. The iOS app groups them for display.

---

## Answering the Specific Questions

### 1. Does the grouping key hold up for edge cases?

Yes, with one nuance. For scopes where the same model name exists in both FFP and SFP versions (some Leupold Mark 5HD configurations), the `model_family` should include focal plane:

```
model_family = "Leupold Mark 5HD 5-25x56 FFP"
model_family = "Leupold Mark 5HD 5-25x56 SFP"
```

This isn't a schema problem — it's a data curation decision. The `model_family` is a human-curated string, not a computed key, so we just get it right during data entry. If we mess up, it's a string edit, not a schema migration.

For the vast majority of precision scopes in our V1 scope (Vortex, Nightforce, Leupold, Kahles, Sig, ZCO), there's exactly one focal plane per model. This edge case is real but rare.

### 2. Reticle as separate entity or embedded?

Separate entity. Covered above. The join cost is negligible (it's one FK lookup on a table with ~15–20 rows — SQLite will serve this from the page cache every time). The upside of having reticle as a real entity far outweighs the cost of one join.

For V1 the Reticle table is just name + unit + manufacturer. That's enough to auto-fill the wizard. Subtension data (holdover values at each hash mark) is a V2 feature that requires real optical engineering data, but the entity being in place means we're ready for it.

### 3. Single bundled DB or split by domain?

**Single file.** Reasons:

- **Cross-domain queries matter.** "Show me all 6.5 CM options" should return rifles, ammo, AND scopes. That's one query across a unified DB, not three queries across three files with results merged in Swift.
- **Schema versioning is simpler.** One `schema_meta` table, one version check at app startup, one migration path.
- **Bundle size is not a concern.** The optics and rifle model tables add maybe 50–100 rows with short string fields. That's <100KB. The entire bundled DB will be well under 5MB even with full ammo data.
- **Update frequency doesn't justify splitting.** Yes, optics catalogs change less often than ammo prices. But we're shipping the DB as a bundled asset with app releases anyway (OTA updates are V2). There's no mechanism to update one domain without the other. When OTA exists, it's still simpler to ship one file than coordinate three.

### 4. What fields do we need for V1 vs. future?

**The wizard needs exactly four things from the optics data:**
1. `click_unit` (mil/moa)
2. `click_value` (0.1 / 0.25)
3. Reticle name (for display and for the `reticleType` field on GunProfile)
4. Reticle unit (mil/moa — for validation that reticle matches turrets)

**Store everything else anyway.** Here's why: the marginal cost of storing magnification, tube diameter, focal plane, and travel limits is zero (they're scalar fields on the same row). The data is readily available on manufacturer spec sheets — it's not harder to capture than click value. And every one of these fields has a clear future use:

- Magnification range → display, search filtering
- Tube diameter → mount compatibility recommendations
- Focal plane → display, education ("your SFP reticle subtensions only hold at max magnification")
- Elevation/windage travel → the solver can warn "this solution requires X mils of elevation — your scope only has Y"

The only field I'd mark as truly optional is `weight_oz` / `length_inches`. Nice for spec sheets, no ballistic or functional use. Capture it if the data is on the page, don't chase it if it's not.

---

## Scraping Complexity: Realistic Assessment

Optics manufacturer pages are **significantly more structured** than ammo pages, and here's why:

Optic specs are a **fixed set of scalar values** (magnification, tube diameter, click value, etc.) that manufacturers present in consistent spec tables. There's no equivalent of the BC mess — a scope's click value is 0.1 Mil or it isn't. No one disputes it. No conflicting sources.

That said, the data isn't structured *enough* for pure HTML scraping — the spec table formats vary by manufacturer (Vortex uses one layout, Nightforce another). LLM extraction would work well here, but honestly, **for V1 we don't need it.**

The precision optics market that matters to our beachhead users is small:
- ~6 manufacturers (Vortex, Nightforce, Leupold, Kahles, Sig Sauer, Zero Compromise Optics)
- ~3–5 model lines per manufacturer that precision shooters actually buy
- ~2 variants per model (Mil/MOA)
- Total: **~30–50 optic records**

This is hand-curation territory, same as what we just did for manufacturers and calibers. A domain expert can populate these in an afternoon. Save the pipeline for ammo, where we have 200–300 records across dozens of product pages with messy BC data.

---

## Recommended Implementation Sequence

1. **Add Reticle and Optic models** to `src/drift/models/`. Add `model_family` column to `RifleModel`. Create migration.
2. **Add `optic_maker` to the manufacturer `type_tags` vocabulary.** Add the ~6 key optics manufacturers to the seed data (Vortex, Nightforce, Leupold, Kahles, Sig Sauer, ZCO). Some may already be familiar names — Sig Sauer could share a manufacturer row if we add `optic_maker` to their tags.
3. **Hand-curate reticle seed data** (~15–20 rows). The domain expert can identify the reticles that matter: EBR-7C, Tremor3, ATACR Mil-XT, H59, MSR2, etc.
4. **Hand-curate optic seed data** (~30–50 rows). One row per SKU. The wizard-critical fields first (click unit, click value, reticle FK), then fill in the rest from spec sheets.
5. **Hand-curate an initial set of rifle model seed data** (~20–30 rows across priority calibers). Same approach — one row per chambering, `model_family` for grouping.
6. **Ship the bundled DB to iOS.** They can start building the wizard against real data.

Steps 1–5 are very similar to what we just did for Steps 1–2. Same script pattern, same test patterns, same domain expert review cycle. The iOS team gets unblocked within a week.
