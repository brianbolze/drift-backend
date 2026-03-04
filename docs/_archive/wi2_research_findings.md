# WI-2: Schema Design Research Findings

*Research conducted February 2026. Findings organized by schema impact — what do we now know that changes or confirms our data model decisions?*

---

## Executive Summary

Five research areas were investigated. The key findings that directly affect schema design:

1. **Caliber is messy enough to warrant a first-class entity, but simple enough to hand-curate for MVP.** There's no public structured API from SAAMI or CIP. We'll build our own Caliber table (~15-20 records for priority tiers) with an alias layer. Parent-case relationships are high-value metadata.

2. **The Bullet → Cartridge split is confirmed and essential.** Manufacturers clearly distinguish component bullets from factory loaded ammunition. The same physical bullet appears in multiple cartridges across calibers. Hornady's ELD Match 140gr (item #26331) is the bullet; Hornady Match 6.5 Creedmoor 140gr (item #81500) is a cartridge containing that bullet. Different SKU ranges, different product pages, different data available.

3. **BC storage needs more nuance than a single float.** Sierra publishes velocity-banded G1 BCs (3-5 bands). Hornady publishes BCs at three Mach numbers. Berger publishes single averaged G1/G7 values. Applied Ballistics publishes independently measured G7 BCs that often differ from manufacturer claims. Our schema should support a primary single BC value (what 95% of users need) with optional extended data for advanced use.

4. **Existing open-source datasets are thin but useful as structural references.** Ammolytics/projectiles covers ~6 manufacturers with a flat schema. JBM has ~2,000 bullets but no downloadable data. No existing dataset matches our quality bar, but the field patterns across projects confirm our schema direction.

5. **Rifle model data is boringly consistent for our priority calibers.** Every major precision rifle in 6.5 Creedmoor ships with a 1:8 twist, 22-24" barrel. The RifleModel entity can be very lightweight — 50-100 records, minimal fields.

---

## Area 1: Caliber Taxonomy — Findings

### No Authoritative Structured Data Source Exists

SAAMI and CIP both publish specifications, but only as PDFs and web interfaces. No JSON, XML, or API exports. The Ammolytics `cartridges` dataset on GitHub attempts to structure SAAMI/CIP/NATO STANAG data but currently only contains cartridge names — the dimensional/pressure specs are incomplete.

**Implication:** We must hand-curate our Caliber table. For ~15-20 priority calibers, this is a few hours of work, not a pipeline problem.

### Naming Is a Genuine Mess — But Bounded for Our Use Case

Key alias patterns discovered:

| Caliber | Aliases | Notes |
|---------|---------|-------|
| 6.5 Creedmoor | "6.5 CM", "CM", "Creed", "6.5mm Creedmoor" | Most consistent — one primary name, few aliases |
| .308 Winchester | ".308 Win", ".308", "7.62x51", "7.62 NATO" | **Danger zone** — see below |
| .300 Win Mag | ".300 WM", ".300 Win Mag", "300 Mag" | Moderate alias set |
| .223 Rem / 5.56 NATO | ".223", "5.56", "5.56x45", ".223 Wylde" | **Three distinct chamber types** |
| 6.5 PRC | "PRC" (ambiguous with .300 PRC) | Need full caliber name for disambiguation |

### The .308 Win / 7.62x51 NATO Problem

These are NOT identical. Key differences: chamber pressure specs (62,000 psi SAAMI vs ~58,000 psi NATO equivalent), headspace tolerances, and case wall thickness. Firing .308 Win ammo in a 7.62 NATO chamber can be unsafe. The same directional incompatibility exists for .223 Rem / 5.56 NATO (reversed — 5.56 NATO in a .223 Rem chamber is the dangerous direction).

**Schema impact:** Store .308 Win and 7.62x51 NATO as separate caliber records with a compatibility/alias relationship, not as synonyms. For search purposes, they should cross-reference each other. For ballistic purposes, the bullet diameter and BC are identical — the difference is in chamber pressure and case specs, which matter for safety but not for the solver.

**Practical note for our app:** Since we're computing ballistic solutions (not advising on chamber compatibility), we can treat .308 Win and 7.62x51 as aliases *for search and solver input purposes* while storing them as distinct caliber records with a note. We are NOT in the business of chamber safety advice — that's a liability minefield. Our caliber entity is for *ballistic computation and product search*, not firearm safety.

### Parent-Case Relationships Are High-Value Metadata

Key families in our priority calibers:

```
.308 Winchester family:
  └── .260 Remington (necked down to 6.5mm)
  └── .243 Winchester (necked down to 6mm)
  └── 7mm-08 Remington (necked down to 7mm)

.30 TC family:
  └── 6.5 Creedmoor
      └── 6mm Creedmoor (necked down to 6mm)

.375 H&H Magnum family:
  └── .300 Winchester Magnum
  └── 7mm Remington Magnum

.416 Rigby family:
  └── .338 Lapua Magnum

.300 Norma Magnum family:
  └── 6.5 PRC
  └── .300 PRC
```

**Schema impact:** A nullable `parentCaseId` FK on the Caliber entity is sufficient. No need for a separate relationship table — the hierarchy is simple (one parent per caliber).

### Recommended Caliber Metadata Fields

Based on what's available from SAAMI/CIP and useful for our app:

| Field | Source | Use in App |
|-------|--------|------------|
| Bullet diameter (inches/mm) | SAAMI | Links caliber to compatible bullets; display |
| Typical bullet weight range | SAAMI + manufacturer data | Search filtering; validation |
| Typical MV range | Manufacturer data | Sanity checking user input |
| Common twist rates | Manufacturer rifle specs | Auto-fill suggestion for rifle setup |
| Common barrel lengths | Manufacturer rifle specs | Display; barrel-length MV correction (future) |
| Max SAAMI pressure (psi) | SAAMI | Display/informational only |
| Parent case | Reference literature | Display; caliber family grouping |
| Year introduced | Reference literature | Display |
| Action length (short/long/magnum) | Reference literature | Rifle compatibility display |
| Cartridge type (centerfire rifle/rimfire) | SAAMI | Filtering |

---

## Area 2: Manufacturer Product Structures — Findings

### Hornady (Most Important — Largest Share of Precision Ammo)

**Product organization:** Clearly separated into "Bullets" (components) and "Ammunition" (loaded cartridges). Different product pages, different SKU ranges, different URLs.

**Component bullet page (e.g., 6.5mm 140gr ELD Match, #26331):**
- Bullet diameter, weight, sectional density
- G1 BC (0.646) and G7 BC (0.326)
- BCs at three Mach numbers: Mach 2.25, 2.0, 1.75
- Minimum recommended twist rate (1:8")
- Bullet construction details (tip type, jacket material, core type)
- Item number, box count (100)
- No muzzle velocity (it's a component — no powder charge)

**Loaded cartridge page (e.g., 6.5 Creedmoor 140gr ELD Match, #81500):**
- Cartridge/caliber, bullet weight, bullet type
- G1 and G7 BC (same values as bullet page)
- Muzzle velocity (2,710 fps) and muzzle energy (2,283 ft-lbs)
- Velocity/energy table at distance intervals
- Item number, box count (20)
- Test barrel length (24")
- Does NOT explicitly link to the component bullet by item number

**Critical finding — BC discrepancy:** Hornady has historically shown slightly different G7 values on the ammo page (0.305) vs. the bullet page (0.326) for the same product. They've been consolidating toward the Mach 2.25 values, but this means our pipeline must be careful about which page it scrapes from. **The bullet (component) page is the canonical BC source.**

**Velocity-banded BCs:** Hornady publishes BCs at Mach 2.25, 2.0, and 1.75 (approximately 2512, 2233, 1954 fps at standard conditions). The variation is small (~1.7% G7 spread across bands) but real at extreme long range. Example for 140 ELD Match: G7 of 0.326 at Mach 2.25, 0.320 at Mach 2.0, 0.310 at Mach 1.75.

### Berger Bullets

**Product organization:** Primarily a component bullet manufacturer. Product lines: Hybrid Target, Long Range Hybrid Target (LRHT), Hybrid Hunter, Elite Hunter, VLD Target, VLD Hunting, Juggernaut, Classic Hunter.

**Published data per bullet:**
- Weight, diameter, overall length
- G1 BC and G7 BC (single averaged values, measured via Doppler radar from 3000-1500 fps)
- G7 Form Factor (ratio of bullet drag to G7 standard — lower = less drag)
- Sectional density
- Minimum twist rate
- Comprehensive reference chart PDF available with all bullets

**Key differentiator:** Berger's BCs are Doppler-measured averages. They explicitly note that their measurement methodology (long-range live fire) differs from manufacturers who test only at short range, which can skew G1 BCs.

**Loaded ammo:** Berger does sell factory loaded ammunition (e.g., "Berger Match Grade" cartridges), but this is a smaller part of their business. Same bullet data plus MV and test barrel specs.

### Sierra Bullets

**Product organization:** Component bullets organized by caliber and product line (MatchKing, Tipped MatchKing/TMK, GameKing, GameChanger, Pro-Hunter, BlitzKing, Varminter).

**Critical finding — Velocity-banded BCs:** Sierra is the canonical example of velocity-banded BC publishing. They provide **3-5 G1 BC values at different velocity bands** instead of a single number. Example (6mm 107gr MatchKing): 0.547 @ 2500+ fps, 0.542 @ 1800-2500, 0.529 @ 1600-1800, 0.519 @ 1600 and below.

**Why they do this:** Sierra uses G1 as their reference standard. Because the G1 drag curve is a poor match for modern boat-tail bullets, the BC varies significantly with velocity. Rather than publish a misleading single average, they provide bands.

**Implication for schema:** Sierra's approach is the strongest argument for supporting velocity-banded BC storage. However, the ballistics community consensus (including Bryan Litz/Applied Ballistics) is that a single G7 BC is more accurate than banded G1 values for modern bullets. For Sierra bullets, Applied Ballistics has published independently measured G7 values.

**Recommendation:** Store Sierra's banded G1 values as metadata/provenance, but prioritize G7 BCs (from Applied Ballistics or our own measurements) as the primary solver input when available.

### Federal Premium

**Product organization:** Ammunition-first manufacturer (not components). Gold Medal Match is the precision line. Product pages show: cartridge, bullet weight, bullet brand/type (often Sierra MatchKing or Berger Hybrid), MV, ME, BC, item number.

**Key pattern:** Federal uses other manufacturers' bullets (Sierra MatchKing, Berger Hybrid, Nosler AccuBond). This means a Federal Gold Medal Match cartridge references a bullet that also exists as a standalone Sierra or Berger component. Our Bullet → Cartridge model handles this naturally — the Bullet entity is the shared truth, and the Cartridge entity (whether from Federal, Hornady, or Berger's loaded ammo line) points to it.

### Cross-Manufacturer Patterns

**Consistently available fields across all manufacturers:**

| Field | Bullets | Cartridges | Notes |
|-------|---------|------------|-------|
| Manufacturer | ✓ | ✓ | |
| Product line | ✓ | ✓ | Different names (bullet line vs. ammo line) |
| Bullet weight (gr) | ✓ | ✓ | |
| Bullet diameter (in) | ✓ | ✓ | |
| G1 BC | ✓ | ✓ | Universal |
| G7 BC | Most | Most | Hornady, Berger always; Sierra sometimes; smaller mfgs often G1-only |
| Sectional density | ✓ | Sometimes | Computed from weight/diameter anyway |
| Item number / SKU | ✓ | ✓ | Manufacturer-specific format |
| Muzzle velocity | ✗ | ✓ | Only on loaded ammo |
| Muzzle energy | ✗ | ✓ | Computed from MV + weight |
| Test barrel length | ✗ | Usually | Critical for MV context |
| Twist rate (minimum) | ✓ | Sometimes | |

**Inconsistently available:**

| Field | Notes |
|-------|-------|
| Velocity-banded BCs | Hornady (3 Mach bands), Sierra (3-5 velocity bands), Berger (single average only) |
| Bullet length/OAL | Berger publishes, Hornady sometimes, Sierra rarely |
| G7 form factor | Berger only |
| Bullet construction details | Varies wildly by manufacturer |
| UPC/barcode | Available from retailers, not always from manufacturer |

**Bullet-to-Cartridge linking:** No manufacturer explicitly links their component bullet SKU to their loaded ammunition SKU. The link must be inferred from matching (manufacturer + bullet name/line + weight + caliber). Hornady's ELD Match 140gr bullet (#26331) maps to their Match 6.5 Creedmoor 140gr ELD Match (#81500) through naming pattern — not through a published relationship. Federal's Gold Medal Match 6.5 CM 140gr maps to Sierra or Berger bullets through the bullet name on the cartridge spec page.

---

## Area 3: Bullet Properties & BC Nuances — Findings

### BC Measurement Methodologies Vary Significantly

| Source | Method | Result |
|--------|--------|--------|
| **Hornady** | Doppler radar, published at 3 Mach numbers | G1 and G7, Mach-banded |
| **Berger** | Doppler radar, averaged 3000-1500 fps | Single G1 and G7 |
| **Sierra** | Short-range testing (historically), velocity-banded | G1 only (3-5 bands) |
| **Applied Ballistics** | Independent Doppler radar testing | G7 (considered most authoritative) |

**Key finding:** Manufacturer-published BCs can differ meaningfully from independently measured values. Applied Ballistics (Bryan Litz) is considered the gold standard for independently measured G7 BCs. The JBM bullet library annotates Litz-measured values with "(Litz)" in the description.

**Schema implication:** We should store BC values with their source/provenance. A BC from Applied Ballistics carries more weight than a manufacturer's self-reported number, and our advanced users will know this. Fields: `bc_g1`, `bc_g7`, `bc_source` (enum: manufacturer, applied_ballistics, community, estimated).

### The Single BC vs. Velocity-Banded Question

Three approaches exist in the wild:

1. **Single G7 BC** (Berger, Applied Ballistics recommendation): Stays nearly constant across the velocity range for modern boat-tail bullets. The G7 standard drag curve closely matches modern long-range bullets, so the coefficient doesn't need to vary. ~10-14x less velocity-sensitive than G1.

2. **Single G1 BC** (most smaller manufacturers, JBM default): Simple but inaccurate for long-range trajectories with modern bullets. The G1 curve is a flat-base reference that poorly models boat-tail bullet drag at transonic speeds.

3. **Velocity-banded G1 BCs** (Sierra, Hornady optionally): Attempts to compensate for G1's poor fit by providing different coefficients at different speed ranges. Better than single G1, but creates discontinuities at band boundaries.

**Our solver already supports both G1 and G7 drag models.** The practical recommendation:

- **Store a single G7 BC as the primary value** when available (Berger, Hornady, Applied Ballistics data).
- **Store a single G1 BC as fallback** when G7 isn't available.
- **Store velocity-banded BCs as optional extended metadata** — useful for display/comparison, not needed for the solver's primary path.
- **Don't try to convert G1 to G7 or vice versa.** The conversion depends on bullet shape and is unreliable. Store what the source publishes.

### Bullet Type Taxonomy

There's no clean universal taxonomy. Each manufacturer uses their own naming:

| Type Code | Full Name | Characteristics |
|-----------|-----------|-----------------|
| BTHP | Boat Tail Hollow Point | Generic match/precision type |
| OTM | Open Tip Match | Similar to BTHP, military terminology |
| ELD-M | Extremely Low Drag Match | Hornady's polymer-tipped match bullet |
| ELD-X | Extremely Low Drag eXpanding | Hornady's polymer-tipped hunting bullet |
| VLD | Very Low Drag | Berger's secant ogive design |
| SMK | Sierra MatchKing | Sierra's match line |
| TMK | Tipped MatchKing | Sierra's polymer-tipped match line |
| A-Tip | Aluminum Tip | Hornady's ultra-precision line |
| LRHT | Long Range Hybrid Target | Berger's latest match design |

**Schema recommendation:** `bullet_type` should be a free-text String, not an enum. The namespace is too fragmented and manufacturer-specific to enumerate. The search alias table handles the abbreviation mapping (SMK → Sierra MatchKing, ELDM → ELD Match, etc.).

---

## Area 4: Existing Databases & Schemas — Findings

### Ammolytics Projectiles (GitHub — Most Relevant Open-Source Dataset)

- **Coverage:** ~6 manufacturers (Barnes, Berger, Hornady, Lapua, Sierra, Speer)
- **Format:** JSON files organized by manufacturer, accessible via Node.js/Python wrapper
- **Schema:** Intentionally flat — manufacturer, bullet name, caliber, weight, BC. Minimal fields.
- **Assessment:** Useful as a structural reference but too thin for our needs. No G7 BCs, no velocity-banded data, no SKUs, no cartridge/loaded ammo data.

### Ammolytics Cartridges (GitHub — Companion Dataset)

- **Coverage:** SAAMI, CIP, and NATO STANAG cartridge names
- **Format:** JSON organized by cartridge category (Pistol, Rifle, Rimfire, Shotshell)
- **Schema:** `name`, `names` (aliases), `diameter_mm`/`diameter_in`, `specs` (COAL, bullet/case/primer details), `standard`, `references`
- **Assessment:** Good structural model for our Caliber entity. Currently names-only (dimensional specs incomplete), but the schema pattern of dual metric/imperial fields and multi-standard support is worth borrowing.

### JBM Bullet Library

- **Coverage:** ~2,000 bullets across many manufacturers
- **Fields:** Manufacturer, caliber (inches), weight (grains), description, BC, drag function
- **BC types:** G1 (most), G7 (Litz-measured bullets marked "(Litz)"), Lapua custom drag coefficients marked "(CD)"
- **No downloadable data** — only accessible through the web calculator interface
- **Assessment:** Largest public bullet library. The "(Litz)" and "(CD)" annotations are a useful pattern — our schema should support BC source attribution similarly. **Notable missing field:** bullet length (required for spin drift calculation but not in JBM's library).

### Applied Ballistics Library

- **Coverage:** 500+ bullets with Doppler-measured data; newer library has thousands with Custom Drag Models
- **Fields:** Bullet name, weight, diameter, length, G1 BC, G7 BC, custom drag model (CDM), stability data, dimensioned drawings, drop scale factor
- **Format:** Proprietary, locked within AB apps/devices
- **Assessment:** The quality bar we should aspire to. Their schema includes fields we should consider: bullet length (for spin drift), G7 form factor, and CDM data. We won't have custom drag models at launch, but storing bullet length positions us for future accuracy improvements.

### LoadDevelopment.com Bullet Database

- **Coverage:** Community-maintained, evolving
- **Fields:** Cartridge, bullet weight, bullet name, bullet diameter, manufacturer, BC
- **Assessment:** Useful as a coverage reference (which bullets are people looking up?) but not as a data source. Lacks G7, velocity banding, or provenance.

### AccurateShooter.com Bullet Database

- **Coverage:** 3,900+ projectiles
- **Fields:** Caliber, manufacturer, stated weight, true weight, length, sectional density, BC
- **Assessment:** Interesting that they track "stated weight" vs. "true weight" — a nod to the fact that manufacturer-stated weights are nominal. Not relevant for our V1 but worth noting.

### Common Schema Patterns Across All Sources

| Field | Universal? | Notes |
|-------|-----------|-------|
| Manufacturer | ✓ | Always present |
| Bullet weight (grains) | ✓ | Always present |
| Caliber / diameter | ✓ | Sometimes as string name, sometimes as numeric diameter |
| G1 BC | ✓ | Present in every dataset |
| G7 BC | ~60% | Only in datasets with Litz/AB data or Hornady/Berger sourced data |
| Bullet type/description | ✓ | Always present but unstructured (free text) |
| Item number/SKU | ~50% | Manufacturer datasets have it; aggregated datasets don't |
| Bullet length | ~20% | AB has it; most others don't |
| Sectional density | ~40% | Computable from weight + diameter |

**Key takeaway:** No existing open-source dataset is comprehensive enough to seed our database directly. But the field patterns confirm our planned schema. The gap is quality and completeness — which is exactly why we're building a curated pipeline.

---

## Area 5: Rifle Model Data — Findings

### Boringly Consistent for Our Priority Calibers

For 6.5 Creedmoor (our #1 priority caliber), every major precision rifle ships with:
- **Twist rate:** 1:8" (universal across Bergara, Ruger, Tikka, Howa, Savage, Seekins)
- **Barrel length:** 22-24" (varies by model/variant)
- **Threading:** 5/8x24 (suppressor-ready, universal)
- **Action:** Bolt-action (for PRS/precision models)

| Rifle | Caliber | Barrel | Twist | Weight | Street Price |
|-------|---------|--------|-------|--------|-------------|
| Bergara B-14 HMR | 6.5 CM | 22" | 1:8 | ~9.2 lb | ~$1,000 |
| Bergara Premier HMR Pro | 6.5 CM | 24" | 1:8 | ~9.5 lb | ~$1,500 |
| Ruger Precision Rifle (Gen 4) | 6.5 CM | 24" | 1:8 | ~10.6 lb | ~$2,150 |
| Tikka T3x TAC A1 | 6.5 CM | 24" | 1:8 | ~10.4 lb | ~$1,800 |
| Tikka T3x CTR | 6.5 CM | 24" | 1:8 | ~8.0 lb | ~$1,100 |
| Tikka T3x ACE Target | 6.5 CM | 24-26" | 1:8 | TBD | ~$2,000 |
| Howa 1500 HCR | 6.5 CM | 24" | 1:8 | ~10.0 lb | ~$900 |
| Savage 110 Elite Precision | 6.5 CM | 26" | 1:8 | ~12.6 lb | ~$2,000 |

**Twist direction:** Right-twist is universal across all modern factory rifles. Left-twist is essentially nonexistent in factory guns (only some custom barrels).

**Schema implication:** The RifleModel entity is confirmed as lightweight. The most important fields for solver input are barrel length and twist rate — and for our top caliber, twist rate is always 1:8. The rifle database is more about convenience (auto-fill barrel length and twist) than about providing data the user doesn't know.

---

## Schema Design Implications — Summary

### Confirmed Decisions

1. **Four entities:** Caliber → Bullet → Cartridge, plus RifleModel (independent)
2. **Caliber as first-class entity** with alias table for search
3. **Bullet is the canonical reusable unit** — carries BC, weight, diameter, type
4. **Cartridge references a Bullet** — adds caliber, MV, test barrel length, manufacturer cartridge info
5. **RifleModel is lightweight** — manufacturer, model, caliber, barrel length, twist rate, twist direction

### New Decisions Informed by Research

6. **BC source attribution is essential.** Store `bc_source` (manufacturer / applied_ballistics / community) alongside BC values. Users and the truing system benefit from knowing provenance.

7. **Velocity-banded BCs are optional extended data, not primary.** Store them as a JSON blob or child records, not as the primary BC fields. The solver's primary path uses single G1 or G7 values.

8. **Bullet length should be in the schema.** Applied Ballistics includes it, Berger publishes it, and the solver needs it for spin drift calculation. Make it optional (not all sources have it) but present.

9. **`bullet_type` is free text, not an enum.** The taxonomy is too fragmented across manufacturers. The search alias table handles abbreviation resolution.

10. **Caliber compatibility is out of scope.** We're a ballistics calculator, not a chamber safety guide. Store .308 Win and 7.62x51 as separate caliber records with cross-reference aliases, but don't build a compatibility matrix. The liability risk outweighs the user value.

11. **Bullet-to-Cartridge linking is inferred, not declared.** No manufacturer explicitly publishes which component bullet SKU goes into which loaded cartridge. The link is established through our entity resolution layer matching on (manufacturer + bullet_name/line + weight + caliber).

12. **`parentCaseId` on Caliber is a simple nullable FK**, not a separate relationship table. The hierarchy is single-parent.

### Open Questions Remaining

- **Do we store Applied Ballistics measured BCs alongside manufacturer BCs?** If yes, we need a BC provenance model (not just a single `bc_source` field, but potentially multiple BC records per bullet from different sources). This is the "whose number do you trust?" question.
- **How do we handle the Hornady ammo-page vs. bullet-page BC discrepancy?** Scrape from bullet pages only? Store both and flag the canonical one?
- **Do we want bullet construction metadata** (jacket type, core material, tip material) for display/filtering, or is it premature for V1?

---

## Sources

### Caliber & Standards
- [SAAMI Technical Standards](https://saami.org/technical-information/ansi-saami-standards/)
- [CIP TDCC Tables](https://www.cip-bobp.org/en/tdcc)

### Manufacturer Product Data
- [Hornady 6.5mm 140gr ELD Match Bullet](https://www.hornady.com/bullets/rifle/6-5mm-264-140-gr-eld-match)
- [Hornady 6.5 Creedmoor 140gr ELD Match Ammunition](https://www.hornady.com/ammunition/rifle/6-5-creedmoor-140-gr-eld-match)
- [Berger Bullet Reference Charts](https://bergerbullets.com/information/lines-and-designs/bullet-reference-charts/)
- [Berger: A Better Ballistic Coefficient](https://bergerbullets.com/a-better-ballistic-coefficient/)
- [Berger: Variation in BC with Velocity](https://bergerbullets.com/nobsbc/variation-in-bc-with-velocity/)
- [Sierra: Lessons Learned from BC Testing](https://www.sierrabullets.com/exterior-ballistics/2-4-lessons-learned-from-ballistic-coefficient-testing/)

### BC & Drag Model Analysis
- [Applied Ballistics Education](https://appliedballisticsllc.com/education/)
- [Bryan Litz Ballistic Tools (via Berger)](https://bergerbullets.com/bryan-litz-ballistic-tools/)
- [Sniper's Hide: Which BC Should I Use?](https://www.snipershide.com/shooting/threads/which-ballistic-coefficient-should-i-use-hornady-eldm.6917153/)
- [Accurate Shooter: Bullet Database with 3900+ Projectiles](https://www.accurateshooter.com/ballistics/bullet-database-with-2900-projectiles/)

### Open-Source Datasets
- [Ammolytics Projectiles Dataset (GitHub)](https://github.com/ammolytics/projectiles)
- [Ammolytics Cartridges Dataset (GitHub)](https://github.com/ammolytics/cartridges)
- [JBM Bullet Library](https://jbmballistics.com/ballistics/calculators/help/common/bclibrary.shtml)
- [LoadDevelopment.com Bullet Database](https://www.loaddevelopment.com/bullet-database/)
- [GNU Ballistics Library (GitHub)](https://github.com/grimwm/libballistics)

### Rifle Models
- [Outdoor Life: Best Rifles 2025](https://www.outdoorlife.com/gear/best-rifles/)
- [Ronin's Grips: Top 20 Most Accurate Factory Rifles](https://blog.roninsgrips.com/market-analysis-the-top-20-most-accurate-factory-rifles-2024-2025/)

---

*Research completed February 2026. Next step: Draft revised schema proposal incorporating these findings.*
