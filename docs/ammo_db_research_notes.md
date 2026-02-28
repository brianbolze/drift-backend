# Drift Ballistics — Ammo & Firearms Database: Research Notes

*Reference findings from research into ballistics domain modeling, industry data standards, and prior art. Compiled to inform the data pipeline and schema design.*

*February 2026*

---

## 1. Caliber / Cartridge Naming Is a Minefield

### The Naming Problem

Cartridge naming conventions are historically inconsistent across American, European, and military systems. The number in a cartridge name often does not match the actual bullet diameter:

| Cartridge Name | Implied Diameter | Actual Bullet Diameter |
|---|---|---|
| .270 Winchester | .270" | **.277"** |
| .38 Special | .38" | **.357"** |
| .44 Magnum | .44" | **.429"** |
| .308 Winchester | .308" | .308" (happens to be correct) |

This means we cannot derive bullet diameter from the cartridge name programmatically. Bullet diameter must be an explicit, verified field on both the Caliber and Bullet entities.

### Military vs. Commercial: Close but NOT Identical

Two pairings that cause particular confusion:

| Commercial | Military | Safe to interchange? |
|---|---|---|
| .223 Remington | 5.56x45mm NATO | **One-way only.** .223 is safe in a 5.56 chamber, but 5.56 NATO is NOT safe in a .223 chamber (higher pressure, longer throat). |
| .308 Winchester | 7.62x51mm NATO | **Mostly.** .308 Win has higher SAAMI max pressure (62,000 vs ~58,000 PSI). Military brass is thicker-walled (less case capacity). Practically interchangeable in most modern rifles, but technically distinct. |

**Implication for our data model:** These should be separate Caliber records with aliases linking them. A search for "5.56" should surface the 5.56 NATO caliber primarily, with .223 Rem as a related result. We should NOT merge them into one entity.

### Shared Bullet Diameters Across Cartridges

This is extremely common and is the physical basis for the Bullet ↔ Caliber relationship:

| Bullet Diameter | Cartridges That Use It |
|---|---|
| .224" (5.56mm) | .223 Rem, 5.56 NATO, .22-250, .224 Valkyrie, .22 Nosler |
| .243" (6mm) | .243 Win, 6mm Creedmoor, 6mm BR, 6mm ARC |
| .264" (6.5mm) | 6.5 Creedmoor, 6.5 PRC, .260 Rem, 6.5x55 Swede, 6.5-284 Norma, .264 Win Mag |
| .277" (6.8mm) | .270 Win, .270 WSM, 6.8 Western, 27 Nosler |
| .284" (7mm) | 7mm Rem Mag, 7mm-08, .280 Rem, .280 AI, 7mm PRC, 28 Nosler |
| .308" (7.62mm) | .308 Win, .30-06, .300 Win Mag, .300 WSM, .300 PRC, .300 Norma, .300 BLK |
| .338" (8.6mm) | .338 Lapua, .338 Win Mag, .338 Norma, .33 Nosler |

**The .308" diameter family alone has 10+ common cartridges.** A single Hornady 178gr ELD-X bullet (.308" diameter) can be loaded into any of them. The bullet doesn't change — only the case and velocity change.

### Common Groupings Shooters Use

Beyond individual calibers, shooters think in categories:

**By action length** (determines which rifles can chamber it):
- Mini action: COAL < 2.3" (.223 Rem)
- Short action: COAL 2.3"–2.8" (.308 Win, 6.5 Creedmoor)
- Long action: COAL 2.8"–3.34" (.30-06, .270 Win)
- Magnum: COAL > 3.34" (.300 PRC, .338 Lapua)

**By performance class:**
- Standard (.308 Win, .30-06)
- Magnum (.300 Win Mag, 7mm Rem Mag)
- Short Magnum (.300 WSM, 6.5 PRC — magnum performance in short action)

**By use case:**
- Long-range competition: 6.5 CM, 6mm CM, .308, .300 PRC, 6.5 PRC, .338 Lapua
- Medium game hunting: .243, 6.5 CM, .308, .270
- Large game: .300 Win Mag, 7mm Rem Mag, .338 Win Mag

These groupings are good candidates for filter facets or category chips in the app UI.

---

## 2. Bullet Classification Is Multi-Dimensional

### Two Independent Axes: Shape and Construction

Bullets vary along at least two independent axes that both matter for ballistics and use case:

**Base geometry** (affects BC):
- Flat base (FB) — lower BC, often more accurate at short range
- Boat tail (BT) — higher BC, standard for long-range
- Rebated boat tail (RBT) — stepped variant

**Ogive shape** (affects BC and seating sensitivity):
- Tangent — smooth transition, less sensitive to seating depth
- Secant — steeper, lower drag, more sensitive to seating depth (VLD-style)
- Hybrid — Berger's innovation: secant for high BC + tangent for seating tolerance

**Tip/construction type** (affects terminal performance and BC):
- Open Tip Match (OTM) / BTHP — the precision standard
- Polymer tip — improves BC, initiates expansion, protects tip in magazine
- Soft point (SP) — traditional hunting
- FMJ — non-expanding, cheapest
- Bonded — jacket fused to core, high weight retention
- Partitioned — Nosler Partition, dual cores
- Monolithic/solid copper — lead-free, near-100% weight retention

**A single "bullet_type" enum cannot capture this.** A Hornady ELD-X is `boat_tail` + `polymer_tip` + `bonded` + `hunting`. A Sierra MatchKing is `boat_tail` + `open_tip` + `cup_and_core` + `match`. The schema uses separate fields for each axis.

### BC Impact of Shape

The shape differences have real ballistic consequences. For a typical 6.5mm ~140gr bullet:

| Shape | Typical G7 BC Range |
|---|---|
| Flat base, tangent | 0.240–0.260 |
| Boat tail, tangent | 0.270–0.300 |
| Boat tail, secant/hybrid | 0.290–0.330+ |

That's a 25-35% difference in drag between the worst and best shapes at the same weight, which translates to meaningful differences in drop and wind drift at distance.

### Monolithic (Copper) Bullets Are Longer

Because copper is less dense than lead, a monolithic copper bullet of the same weight is significantly longer than a lead-core bullet. This matters for:
- Twist rate requirements (longer bullets need faster twist to stabilize)
- Magazine fit (may not fit in standard COAL)
- BC (can be higher due to the longer ogive)

This is relevant for the app: if someone selects a monolithic bullet, a note about twist rate requirements could be valuable.

---

## 3. Manufacturer Product Line Organization

### The Universal Pattern

Every major manufacturer organizes along the same axis:

| Tier | Hornady | Federal | Sierra | Nosler | Berger |
|---|---|---|---|---|---|
| Elite match | A-Tip | Gold Medal Berger | MatchKing (SMK) | RDF | LRHT, Hybrid Target |
| Match/target | ELD Match | Gold Medal | Tipped MatchKing (TMK) | Custom Competition | Target |
| Premium hunting | ELD-X | Terminal Ascent | Tipped GameKing (TGK) | AccuBond, Partition | Hybrid Hunter |
| Value hunting | SST, InterLock | Fusion, Power-Shok | GameKing | Ballistic Tip | Classic Hunter |
| Varmint | V-MAX, ELD-VT | (various) | BlitzKing | Ballistic Tip Varmint | FB Varmint |
| Lead-free | CX | Trophy Bonded Tip | — | E-Tip | — |
| Budget/training | Frontier | American Eagle | — | — | — |

This pattern is useful for the `use_case` classification on bullets and the `is_match_grade` / `is_hunting` flags on cartridges.

### Component Bullets vs. Factory Ammo

Most manufacturers sell both:

- **Component bullet**: "Hornady ELD Match 6.5mm .264 140gr" — part #26331. Sold to handloaders in boxes of 100. Has BC, weight, diameter. No muzzle velocity (depends on the handloader's recipe).
- **Factory cartridge**: "Hornady Match 6.5 Creedmoor 140gr ELD Match" — item #81500. Complete ready-to-fire round. Has everything the bullet has PLUS muzzle velocity from a test barrel.

**Same bullet in both.** Our Bullet entity captures the shared properties; the Cartridge entity adds the velocity and packaging context.

### Cross-Manufacturer Loading

Some ammo makers load other companies' bullets:

- **Federal Gold Medal Match** uses Sierra MatchKing bullets
- **Federal Gold Medal Berger** uses Berger Hybrid Target bullets
- **Nosler Trophy Grade** uses Nosler's own bullets (vertically integrated)

This is why `manufacturer_id` on the Cartridge entity can differ from the Bullet's `manufacturer_id`. The user cares about both: "Federal loads Berger bullets."

---

## 4. Ballistic Coefficient: G1 vs. G7 Deep Dive

### Why Two Standards Exist

G1 and G7 are reference projectile shapes. A BC is a measure of how a bullet's drag compares to one of these reference shapes.

- **G1**: Based on an 1880s flat-base, blunt-nosed projectile. Looks nothing like a modern long-range bullet.
- **G7**: Based on a long boat-tail with a secant ogive. Very close to modern match bullets.

Because G1 is a poor shape match for modern bullets, the drag ratio changes significantly with velocity. A G1 BC is only accurate in a narrow velocity band. G7 is a much better match, so a single G7 BC is nearly constant across all velocities.

### The Practical Difference

For a typical modern match bullet (e.g., Hornady 140 ELD Match):
- Published G1 BC: **0.585**
- Published G7 BC: **0.326**

The G7 value is roughly 0.5x the G1 value, but the ratio varies by bullet shape (0.48x to 0.55x). **You cannot reliably convert between G1 and G7 with a fixed multiplier.** Each bullet has its own form factor.

### Stepped BCs (Sierra's Approach)

Sierra publishes velocity-banded G1 BCs to compensate for the poor G1 shape match:

```
Above 2800 fps:   0.535
2400–2800 fps:    0.550
Below 2400 fps:   0.530
```

This creates velocity discontinuities that need smoothing in the solver. Our schema supports this via `bc_g1_stepped` as a JSON array.

### Applied Ballistics Custom Drag Models (CDMs)

The gold standard: bullet-specific drag curves measured via Doppler radar. Not a BC at all — it's the actual Cd vs. Mach number relationship for that specific bullet. Eliminates the approximation error of fitting to G1 or G7 reference shapes.

AB has published CDMs for 175+ bullets. The data is proprietary. Our schema can accommodate CDMs (a JSON array of Mach → Cd pairs on the Bullet entity), but we likely won't populate them for V1.

### Source Hierarchy for BC Values

When multiple sources exist for a bullet's BC:

1. **Applied Ballistics measured G7** (highest confidence — independently measured via Doppler)
2. **Manufacturer-published G7** (good, but may be optimistic)
3. **Manufacturer-published G1** (adequate, most widely available)
4. **Retailer/third-party published** (use with caution — often copied with errors)

The schema's `bc_g1_source` / `bc_g7_source` fields track this.

---

## 5. The Abbreviation / Alias Problem

### The Scale of the Problem

Shooters use a dense vocabulary of abbreviations, nicknames, and shorthand. The search system must handle all of these fluently. Here's a sampling:

**Bullet abbreviations (universally understood):**
FMJ, BTHP, OTM, HP, SP, BT, FB, HPBT, JHP, AP

**Manufacturer-specific (widely recognized):**
- Hornady: ELDM, ELDX, SST, CX, GMX, A-MAX (discontinued predecessor to ELD-M), FTX, A-Tip
- Sierra: SMK, TMK, GK, TGK, BK
- Nosler: PT (Partition), AB (AccuBond), ABLR, RDF, CC, BT (Ballistic Tip — ambiguous with "boat tail")
- Berger: VLD, HT (Hybrid Target), HH (Hybrid Hunter), LRHT
- Barnes: TSX, TTSX, LRX

**Caliber shorthand:**

| Canonical | Common aliases |
|---|---|
| 6.5 Creedmoor | 6.5 CM, 6.5 Creed, 6.5 Creedmore (misspelling) |
| .308 Winchester | .308 Win, 308, 7.62x51 (loosely) |
| .300 Winchester Magnum | .300 Win Mag, 300WM, .300 WM |
| .30-06 Springfield | 30-06, thirty-aught-six |
| .300 AAC Blackout | .300 BLK, 300 Blackout |
| .338 Lapua Magnum | .338 Lapua, 338LM |

**Community slang:**
- "pills" = bullets
- "Gold Medal" = Federal Gold Medal Match (the specific ammo, not a generic term)
- "Match Kings" / "Kings" = Sierra MatchKing
- "Hybrids" = Berger Hybrid Target or Hybrid Hunter
- "Juggs" = Berger Juggernaut OTM
- "Copper bullets" = any monolithic (Barnes, Hornady CX, Nosler E-Tip)

### Alias Strategy

The Search Alias table needs to be seeded aggressively at launch and maintained as an ongoing editorial effort. Categories of aliases to cover:

1. **Abbreviations** — ELDM, SMK, 300WM, etc.
2. **Alternate names** — "Hollow Point Boat Tail" for BTHP, "7.62 NATO" for 7.62x51
3. **Misspellings** — "Creedmore," "Hornaday," "Berger" (commonly mispronounced/misspelled as "Burger")
4. **SKUs/part numbers** — "81500" → Hornady 140 ELD Match 6.5CM
5. **Military designations** — M118LR → 7.62 NATO 175gr SMK, M855 → 5.56 62gr green tip
6. **Discontinued predecessors** — "A-MAX" should still resolve to the ELD Match that replaced it

---

## 6. Prior Art: How Existing Systems Model This Data

### Open-Source Ballistic Calculators

Most open-source solvers (Gehtsoft, Sharp.Ballistics) model ammunition as a flat struct: bullet properties + muzzle velocity in one object. They don't model calibers, manufacturers, or product lines because they're solver libraries, not data systems. **They solve the physics problem but not the data entry problem.**

Key pattern: every system separates the weapon (rifle + optic + zero) from the ammunition (bullet + velocity) from the atmosphere. These are the three independent inputs to any ballistic calculation.

### Applied Ballistics

AB's bullet library is the gold standard for ballistic data. ~500+ bullets with:
- Weight, diameter, length
- G1 and G7 BCs (with form factors)
- Custom Drag Models for 175+ bullets (Doppler-measured Cd vs. Mach curves)

AB does NOT model cartridges (factory loaded ammo) or calibers — it models bullets only. The velocity is entered by the user. This makes sense for their use case (precision shooters who know their MV), but it's not sufficient for our data-entry-reduction goal where we want to auto-fill MV from factory specs.

### Strelok

3,000+ cartridge profiles. Models cartridges as flat records (bullet props + MV + powder sensitivity). Separates rifle and cartridge as independent entities that combine at solve time. Notable for modeling powder temperature sensitivity on the cartridge (MV variation per degree).

### Hornady 4DOF

The most technically sophisticated. Doesn't use BC at all — each bullet has a 437-point drag coefficient curve measured via Doppler radar. Also models jacket thickness and pitch/yaw dynamics (true 4DOF). However, the bullet library is Hornady-only.

### AmmoSeek (Price Aggregator)

Treats "caliber" as the primary organizing concept (a string label — 350+ values). Products are flat records with caliber, manufacturer, weight, bullet type, UPC. No bullet-level entity. No BC data. Useful reference for the *breadth* of caliber names and product SKUs that exist in the wild, but not a model for ballistic data.

### SAAMI / CIP Standards

SAAMI models cartridges and chambers — not bullets. Each cartridge has dimensional specs and pressure limits. Naming conventions are authoritative but don't match common usage (SAAMI uses "308 Win" without the leading dot; the community universally writes ".308 Win"). CIP categorizes primarily by rim type (rimless, rimmed, belted).

SAAMI publishes cartridge interchangeability tables (which cartridges can safely fire in which chambers) and historical name equivalency tables. Both are useful seed data for our Caliber entity and alias system.

### Reloading Databases (Hodgdon, Sierra, LoadData)

Organized as: Cartridge → Bullet → Powder → Load Recipe. 300K+ recipes. The bullet and cartridge are separate entities joined in a recipe. Powder charge, velocity, and pressure are per-recipe. This is the handloader's world — a fundamentally different access pattern from external ballistics, but it confirms that the bullet as a separable entity is a well-established pattern.

### Key Takeaway Across All Prior Art

No existing system models the full chain we need: **Caliber → Bullet → Cartridge → User Profile** with search, aliases, and provenance. Solver libraries model the physics inputs. Product databases model the commercial catalog. Standards bodies model the dimensional specs. We're building the layer that connects all three and optimizes for the data-entry use case. That's genuinely novel for this domain.

---

## 7. Cartridge Dimensional Data (SAAMI Reference)

For the Caliber entity's dimensional specs, here are key values for our priority calibers:

| Caliber | Bullet Dia | Case Length | COAL | MAP (PSI) | Action | Rim Type |
|---|---|---|---|---|---|---|
| .223 Rem | .224" | 1.760" | 2.260" | 55,000 | Mini | Rimless |
| 5.56 NATO | .224" | 1.760" | 2.260" | ~62,000* | Mini | Rimless |
| .243 Win | .243" | 2.045" | 2.710" | 60,000 | Short | Rimless |
| 6mm Creedmoor | .243" | 1.920" | 2.800" | 62,000 | Short | Rimless |
| 6.5 Creedmoor | .264" | 1.920" | 2.825" | 62,000 | Short | Rimless |
| .260 Rem | .264" | 2.035" | 2.800" | 60,000 | Short | Rimless |
| 6.5 PRC | .264" | 2.030" | 2.955" | 65,000 | Short | Rimless |
| 6.5x55 Swede | .264" | 2.165" | 3.150" | 46,000† | Long | Rimless |
| .270 Win | .277" | 2.540" | 3.340" | 65,000 | Long | Rimless |
| 7mm-08 Rem | .284" | 2.035" | 2.800" | 61,000 | Short | Rimless |
| 7mm Rem Mag | .284" | 2.500" | 3.290" | 61,000 | Long | Belted |
| 7mm PRC | .284" | 2.280" | 2.955" | 65,000 | Short | Rimless |
| .308 Win | .308" | 2.015" | 2.810" | 62,000 | Short | Rimless |
| .30-06 | .308" | 2.494" | 3.340" | 60,000 | Long | Rimless |
| .300 Win Mag | .308" | 2.620" | 3.340" | 64,000 | Long | Belted |
| .300 WSM | .308" | 2.100" | 2.860" | 65,000 | Short | Rimless |
| .300 PRC | .308" | 2.580" | 3.700" | 65,000 | Magnum | Rimless |
| .300 BLK | .308" | 1.368" | 2.260" | 55,000 | Mini | Rimless |
| .338 Lapua | .338" | 2.724" | 3.681" | 60,916 | Magnum | Rimless |
| .338 Win Mag | .338" | 2.500" | 3.340" | 64,000 | Long | Belted |

*5.56 NATO pressure is measured differently (NATO EPVAT vs SAAMI piezo) — not directly comparable.*
†The 6.5x55 Swede has a lower SAAMI pressure spec due to the age of the cartridge and the number of older rifles still in service. Modern rifles can handle significantly more.

---

## 8. Sectional Density Reference

Sectional density (SD) is a derived property: `SD = (weight_gr / 7000) / (diameter_in²)`. It's useful as a search filter and informational display. Common values for our priority bullets:

| Bullet | Weight | Diameter | SD |
|---|---|---|---|
| 77gr .224" (SMK) | 77 | .224" | 0.219 |
| 108gr 6mm (ELD-M) | 108 | .243" | 0.261 |
| 140gr 6.5mm (ELD-M) | 140 | .264" | 0.287 |
| 147gr 6.5mm (ELD-M) | 147 | .264" | 0.301 |
| 175gr .308 (SMK) | 175 | .308" | 0.264 |
| 185gr .308 (Juggernaut) | 185 | .308" | 0.278 |
| 212gr .308 (ELD-X) | 212 | .308" | 0.319 |
| 225gr .338 (ELD-M) | 225 | .338" | 0.281 |
| 285gr .338 (ELD-M) | 285 | .338" | 0.356 |
| 300gr .338 (SMK) | 300 | .338" | 0.375 |

General ranges:
- < 0.200: Varmint bullets
- 0.200–0.250: General purpose
- 0.250–0.300: Good penetration (most long-range match/hunting)
- \> 0.300: Heavy-for-caliber, excellent penetration

---

*These notes are research reference, not spec. See `ammo_db_data_model.md` for the actual schema proposal.*