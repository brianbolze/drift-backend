# Data Coverage Audit: Missing Grain Weight Variants

> Generated 2026-03-19 | DB: data/drift.db (1,297 bullets, 569 cartridges)

## Executive Summary

Cross-referenced our database against manufacturer catalogs for five major match/LR bullet product lines and factory cartridge offerings for the top 15 long-range calibers. **Found 13 missing bullet variants and ~15 missing cartridge loads**, plus two entirely absent manufacturers (Remington ammo, Sig Sauer ammo).

---

## Part 1: Missing Bullet Grain Weight Variants by Product Line

### Hornady ELD Match

**In DB (12 variants):** 22cal 73gr, 88gr | 6mm 108gr | 25cal 134gr | 6.5mm 123gr, 147gr | 7mm 162gr, 180gr | 30cal 178gr, 195gr, 225gr | 338cal 285gr

**Missing from DB (8 variants):**

| Diameter | Weight | Notes |
|----------|--------|-------|
| .224 | 52 gr | Lightweight .22 cal match |
| .224 | 75 gr | Mid-weight .22 cal match |
| .224 | 80 gr | Heavy .22 cal match |
| .264 | 100 gr | Lightweight 6.5mm match |
| .264 | 120 gr | Mid-weight 6.5mm match |
| .264 | 130 gr | Popular 6.5 Creedmoor weight |
| .264 | 140 gr | **Critical** — most popular 6.5mm match weight |
| .308 | 155 gr | Palma/mid-range .30 cal match |
| .308 | 168 gr | **Critical** — most popular .30 cal match weight |
| .308 | 208 gr | Heavy .30 cal match |

**Priority:** The 6.5mm 140gr and .30cal 168gr ELD Match are among the most widely used match bullets in their calibers. Their absence is a significant gap.

### Berger Hybrid Target / Long Range Hybrid Target

**In DB (18+ variants):** Good coverage. 22cal 85.5gr LRHT | 6mm 105gr HT, 109gr LRHT | 25cal 135gr LRHT | 6.5mm 140gr HT, 144gr LRHT, 153.5gr LRHT | 7mm 180gr HT, 184gr F-Open, 190gr LRHT | 30cal 155gr HT, 200.20x HT, 208gr LRHT, 215gr HT, 220gr LRHT, 230gr HT, 245gr LRHT

**Missing from DB (2 variants):**

| Diameter | Weight | Notes |
|----------|--------|-------|
| .308 | 168 gr | Hybrid Target — popular F-class weight |
| .308 | 185 gr | Hybrid Target — common .308 Win weight |

**Note:** Berger also offers a .338 250gr Hybrid OTM Tactical — we have it. Coverage is strong.

### Sierra MatchKing (SMK) & Tipped MatchKing (TMK)

**In DB (57 variants):** Excellent coverage across all diameters. This is our best-covered product line.

**Missing from DB (3 variants):**

| Diameter | Weight | Product | Notes |
|----------|--------|---------|-------|
| .224 | 52 gr | SMK | Classic benchrest weight |
| .224 | 69 gr | TMK | Popular AR .223 match weight |
| .308 | 155 gr | TMK | Tipped Palma variant |
| .308 | 175 gr | TMK | Tipped version of classic 175gr SMK |
| .308 | 195 gr | TMK | Tipped heavy .30 cal |

**Note:** The .224 52gr SMK is one of the most iconic benchrest bullets ever made. The .308 155gr, 175gr, and 195gr TMK are tipped versions of already-present SMK weights.

### Nosler RDF

**In DB (9 variants + 1 ammo duplicate):** 22cal 70gr, 77gr, 85gr | 6mm 105gr, 115gr | 6.5mm 140gr | 7mm 185gr | 30cal 175gr (x2), 210gr

**Missing from DB (2 variants):**

| Diameter | Weight | Notes |
|----------|--------|-------|
| .264 | 130 gr | 6.5mm mid-weight match |
| .308 | 168 gr | Classic .30 cal match weight |

### Lapua Scenar / Scenar-L

**In DB (19 variants):** Complete match to current production catalog.

**Missing: NONE** — Full coverage of both Scenar and Scenar-L lines.

---

## Part 2: Missing Cartridge Grain Weight Variants by Caliber

### Calibers with Good Coverage (No Action Needed)

| Caliber | LR Rank | Loads | Assessment |
|---------|---------|-------|------------|
| .308 Winchester | 5 | 61 | Excellent |
| 6.5 Creedmoor | 1 | 40 | Excellent |
| .300 Win Mag | 6 | 34 | Good |
| 7mm Rem Mag | 13 | 18 | Good |
| 6mm Creedmoor | 4 | 15 | Good |
| 6.5 PRC | 8 | 14 | Good |
| .338 Lapua | 10 | 14 | Good |

### Calibers with Notable Cartridge Gaps

#### 7mm PRC (LR Rank 9) — 10 loads, ~4 missing

| Manufacturer | Weight | Bullet | MV (fps) | Status |
|-------------|--------|--------|----------|--------|
| Federal | 155 gr | Terminal Ascent | 3100 | **MISSING** |
| Federal | 175 gr | Fusion Tipped | 2925 | **MISSING** |
| Hornady | 154 gr | SST AWT (new 2026) | 3030 | **MISSING** |
| Remington | 175 gr | Core-Lokt Tipped (new 2026) | 3000 | **MISSING** |

#### .300 PRC (LR Rank 7) — 8 loads, ~3-5 missing

| Manufacturer | Weight | Bullet | MV (fps) | Status |
|-------------|--------|--------|----------|--------|
| Hornady | 174 gr | ELD-VT V-Match (new) | 3150 | **MISSING** |
| Hornady | 190 gr | CX Outfitter | 3000 | **MISSING** (verify) |
| Federal | 210 gr | Terminal Ascent | 2850 | **MISSING** (verify) |

#### 6.5 PRC (LR Rank 8) — 14 loads, ~3-5 missing

| Manufacturer | Weight | Bullet | MV (fps) | Status |
|-------------|--------|--------|----------|--------|
| Hornady | 100 gr | ELD-VT V-Match (new) | 3450 | **MISSING** |
| Federal | 120 gr | Trophy Copper | 3050 | **MISSING** (verify) |
| Remington | 140 gr | Core-Lokt Tipped (new 2026) | 2960 | **MISSING** |

#### 6mm ARC (LR Rank 11) — 5 loads

Research confirms only 3 factory loads exist from Hornady (103gr, 105gr, 108gr). Our DB has 5 loads which includes the 80gr V-Match and 90gr CX. Barnes announced a 90gr TAC-TX for 2026 but not yet shipping. **Coverage is actually complete or slightly ahead of market.**

#### 6mm GT (LR Rank 3) — 1 load

Only 1 factory load exists (Hornady 109gr ELD Match). This is a reloading-centric cartridge. **No gap to fill — coverage matches market.**

#### .25 Creedmoor (LR Rank 12) — 4 loads

DB has: 95gr ELD-VT, 112gr CX, 128gr ELD-X, 134gr ELD Match. Research confirms Hornady offers 3 loads (112gr, 128gr, 134gr). The 95gr V-Match is a bonus. **Coverage is complete.**

### Entirely Missing Manufacturers

#### Remington (ammo_maker in DB, 0 cartridges)

Remington offers factory ammo in key LR calibers:

| Caliber | Weight | Bullet | MV (fps) |
|---------|--------|--------|----------|
| 6.5 Creedmoor | 129 gr | Core-Lokt Tipped | 2945 |
| 6.5 Creedmoor | 140 gr | PSP Core-Lokt | 2700 |
| .308 Winchester | 150 gr | PSP Core-Lokt | 2820 |
| .308 Winchester | 180 gr | PSP Core-Lokt | 2620 |
| .300 Win Mag | 150 gr | PSP Core-Lokt | 3290 |
| .300 Win Mag | 180 gr | PSP Core-Lokt | 2960 |
| 7mm PRC | 175 gr | Core-Lokt Tipped (new 2026) | 3000 |
| 6.5 PRC | 140 gr | Core-Lokt Tipped (new 2026) | 2960 |

**~8 loads missing.** Remington is a major ammo brand — their absence is noticeable for users.

#### Sig Sauer (not tagged as ammo_maker, offers rifle ammo)

Sig Sauer has a small rifle ammo line:

| Caliber | Weight | Bullet | MV (fps) |
|---------|--------|--------|----------|
| 6.5 Creedmoor | 130 gr | Elite Hunter Tipped | 2850 |
| .308 Winchester | 165 gr | Elite Hunter Tipped | 2840 |
| .308 Winchester | 168 gr | OTM Match | 2700 |
| .300 Win Mag | 190 gr | OTM Match | 2850 |

**~4 loads missing.** Lower priority than Remington given smaller product line.

---

## Part 3: Known Issues Status

| ID | Severity | Summary | Status | Change |
|----|----------|---------|--------|--------|
| C1 | Critical | 8 cartridge-bullet weight mismatches | Open | Unchanged |
| C6 | Critical | Sierra 22cal 60gr TMK bad record (0.220 diam) | Open | Unchanged |
| C7 | Critical | Hornady .308 220gr RN International metric barrel | Open | Unchanged |
| C8 | Critical | Sako Gamehead .308 150gr wrong BC | Open | Unchanged |
| W1 | Warning | 14 cartridges with MV=0 | Open | Unchanged |
| W2 | Warning | 33 rifle bullets missing all BC fields | Open | Unchanged |
| W3 | Warning | .204 Ruger 4400fps loads (plausible) | Open | Unchanged |
| W5 | Warning | 5 Federal Custom Rifle Ammo placeholders | Open | Unchanged |
| W7 | Warning | Hornady 8x57 International metric barrel | Open | Unchanged |
| W8 | Warning | 12 Berger ammo pages stored as bullet records | Open | Unchanged |
| W9 | Warning | Hornady 6.5CM ELD-VT source URL mismatch | Open | Unchanged |
| W10 | Warning | Sierra 6.5mm 107gr TMK misnamed as '6MM' | Open | Unchanged |
| C2-C5, W4, W6 | — | Previously resolved | Resolved | — |

No new structural issues found. No resolved issues regressed.

---

## Part 4: Spot Checks (2026-03-19)

| Entity | Record | Field | DB Value | Website Value | Status |
|--------|--------|-------|----------|---------------|--------|
| Bullet | Hornady 7mm 175gr ELD-X | G1 BC | 0.689 | 0.689 | PASS |
| Bullet | Hornady 7mm 175gr ELD-X | G7 BC | 0.347 | 0.347 | PASS |
| Bullet | Berger 30cal 190gr VLD Hunting | G1 BC | 0.566 | 0.566 | PASS |
| Bullet | Berger 30cal 190gr VLD Hunting | G7 BC | 0.290 | 0.290 | PASS |
| Cartridge | Hornady 6.5 PRC 130gr CX Outfitter | MV | 2975 | ~2975 | PASS |
| Cartridge | Hornady 300 PRC 212gr ELD-X PH | MV | 2860 | 2860 | PASS |

---

## Priority Action Items

### High Priority (Most Impact for App Users)

1. **Add Hornady ELD Match 6.5mm 140gr and .30cal 168gr** — Two of the most popular match bullets in existence. Their absence will be noticed by serious shooters.
2. **Add Remington cartridges** (~8 loads) — Major brand entirely missing from cartridge data.
3. **Add missing 7mm PRC cartridges** (~4 loads) — Fastest-growing LR caliber, thin coverage.

### Medium Priority

4. **Add remaining Hornady ELD Match variants** (52gr, 75gr, 80gr, 100gr, 120gr, 130gr, 155gr, 208gr .30cal)
5. **Add missing .300 PRC and 6.5 PRC cartridges** (~6-8 loads total)
6. **Add Berger 30cal 168gr and 185gr Hybrid Target** — Common .308 Win match weights
7. **Add Nosler RDF 6.5mm 130gr and .30cal 168gr**

### Lower Priority

8. **Add Sig Sauer cartridges** (~4 loads) — Niche brand, small lineup
9. **Add Sierra TMK tipped variants** (155gr, 175gr, 195gr .30cal; 69gr .22cal) — Tipped versions of already-present SMK weights
10. **Add Sierra SMK .224 52gr** — Iconic benchrest bullet, but less relevant for LR app
