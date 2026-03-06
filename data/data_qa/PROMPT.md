# Task: Data Quality Audit

You're responsible for auditing the data in our ballistics database for correctness. This data feeds a ballistic solver in an iOS app — wrong values mean wrong firing solutions, so **numerical accuracy is the top priority**.

The database is at `data/drift.db` (SQLite). Start by reading `docs/db_summary.md` for a schema overview and data snapshot.

## Audit Methodology

For each run, do the following in order:

### Phase 1: Structural Integrity (SQL only — no web needed)

Run these checks via SQL queries on drift.db:

**Referential integrity:**
_Low Priority_: Foreign Key constraints should handle this at the database level.
- Every `cartridge.bullet_id` exists in `bullet`
- Every `cartridge.caliber_id` exists in `caliber`
- Every `bullet.manufacturer_id` exists in `manufacturer`
- Every `cartridge.manufacturer_id` exists in `manufacturer`
- Every `bullet_bc_source.bullet_id` exists in `bullet`

**Cross-entity consistency:**
- For each cartridge, verify `cartridge.bullet_weight_grains` matches the linked `bullet.weight_grains`. Flag mismatches.
- For each cartridge, verify the linked bullet's `bullet_diameter_inches` matches the caliber's `bullet_diameter_inches`. A mismatch means wrong bullet or wrong caliber linkage. This is a **critical** issue.

**Duplicate detection:**
- Find bullet pairs sharing the same `manufacturer_id` + `bullet_diameter_inches` + `weight_grains`. List both names and source_urls. If their BC values also match, it's almost certainly a duplicate. Group by manufacturer.

**Implausible values:**
- BC values: G1 should be 0.050–0.900, G7 should be 0.030–0.500. Flag anything outside these ranges.
- G1/G7 ratio: For bullets with both, the ratio G1/G7 typically falls between 1.5 and 2.5. Outliers may indicate a G1/G7 swap.
- Muzzle velocity: Flag cartridges with `muzzle_velocity_fps = 0`. Also flag rifle cartridges (non-handgun calibers) with velocity outside 1,600–4,200 fps, and handgun cartridges outside 600–2,200 fps. The exception would be subsonic cartridges like .300 blackout or 8.6 blackout.
- Bullet weight vs diameter: A .224 bullet over 90gr or a .308 bullet under 80gr is suspicious. Use your domain knowledge to flag implausible weight/diameter combinations.

**Missing critical fields:**
- Bullets with all four BC fields NULL (`bc_g1_published`, `bc_g1_estimated`, `bc_g7_published`, `bc_g7_estimated`). Group by manufacturer. **Note:** Cutting Edge Bullets and some Nosler entries are expected to have missing BCs — their product pages don't publish them. Only flag rifle-caliber bullets (diameter <= .375) from other manufacturers as warnings.

### Phase 2: Spot-Check Verification (web search)

Sample **10 records** for web-based cross-referencing. Pick a mix:
- 9-12 bullets from high-priority calibers (.264, .308, .284 diameter) from major manufacturers (Hornady, Sierra, Berger, Lapua)
- 9-12 cartridges from top LR calibers (6.5 Creedmoor, .308 Win, 6.5 PRC)
- 2 bullets that had unusual values flagged in Phase 1
- 2 randomly selected records

For the 10 bullets and 10 cartridges, it's okay to do similar sets of 2-3 -- say, 2-3 bullets from the same manufacturer & family, 3-5 sets - to make the searching efficient. 

For each sampled record:
1. Visit the `source_url` (if available) or search the manufacturer's site
2. Verify: BC values (G1 and G7), bullet weight, diameter, muzzle velocity (for cartridges)
3. Note any discrepancies between our DB and the source

**Tips for specific manufacturer sites:**
From earlier AI research agent runs, here are some guidelines from what we've found so far:
- **Hornady** (`hornady.com`): Product pages list G1/G7 BC, sectional density, weight, diameter. ELD Match and A-Tip pages are the most spec-rich. Hornady International pages (ECX, etc.) often lack velocity data.
- **Sierra** (`sierrabullets.com`): All product pages should have G1 and G7 BC. URL pattern: `/[slug]` e.g. `/6-5mm-142-gr-hpbt-cn-matchking-smk`.
- **Berger** (`bergerbullets.com`): All pages should have G1/G7 BC, weight, diameter, length. URL: `/product/[slug]`.
- **Lapua** (`lapua.com`): Most match/target bullets should have both G1 and G7 BC. Hunting bullets may only list G1. URL: `/product/[slug]`.
- **Barnes** (`barnesbullets.com`): Multi-variant pages — one URL lists multiple weights. G1 BC is typical; G7 less common. URL: `/[slug]`.
- **Nosler** (`nosler.com`): Product pages should confirm caliber, weight, product line. **BC values are usually in their load data section, not on product pages.** Don't flag missing Nosler BCs as data errors.
- **Speer** (`speer.com`): Product pages should have BC, diameter, weight, sectional density.
- **Federal** (`federalpremium.com`): Salesforce Commerce Cloud SPA — product pages can be tricky. Gold Medal and premium lines should have BC; budget lines may not.
- **Cutting Edge Bullets** (`cuttingedgebullets.com`): BC values are tricky to find. May require javascript rendering to find the technical info table.
- **Lehigh Defense** (`lehighdefense.com`): Pages should have BC, sectional density, diameter, velocity data. Clean URL pattern.
- **Norma** (`norma.cc`): Usually only publishes G1 BC, no G7 anywhere on site. Specs are in structured JSON-LD on product pages.

### Phase 3: Bullet Name Quality (informational)

Scan for these patterns and report counts by manufacturer:
- Pack counts in name: `(100ct)`, `(50ct)`, etc.
- ALL CAPS names
- Caliber/diameter redundantly in name: "30 CAL", "6.5mm .264", etc.
- Metric weight prefix: "12,0 g / 185 gr"
- Trademark symbols: (R), TM, special unicode chars
- Names over 80 characters

This is informational — these are cosmetic issues for a future cleanup pass, not data correctness problems.

## Output

Write a markdown report to `data/data_qa/report_YYYY-MM-DD.md` with this structure:

```markdown
# Data Quality Report — YYYY-MM-DD

## Summary
- Database: X manufacturers, Y calibers, Z bullets, W cartridges
- Critical issues found: N
- Warnings found: N
- Informational: N

## Critical Issues
[Wrong values, broken linkages, diameter mismatches — things that would cause incorrect ballistic solutions]

## Warnings
[Duplicates, missing BCs for major manufacturers, implausible but not necessarily wrong values]

## Spot-Check Results
[Table of 10 sampled records with verification status]

## Informational
[Name quality stats, coverage gaps, expected manufacturer limitations]

## Queries Run
[Include key SQL queries and their results for reproducibility]
```

**Severity guide:**
- **CRITICAL**: Wrong BC, wrong bullet-cartridge link, diameter/caliber mismatch — directly causes wrong ballistic calculations
- **WARNING**: Missing BC (rifle bullets from publishers who should have it), likely duplicates, implausible velocity
- **INFO**: Name cosmetics, expected gaps (Cutting Edge BCs, Nosler BCs), coverage observations
