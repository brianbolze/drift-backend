## Data Quality Audit — March 2026

DB snapshot: 547 bullets, 237 cartridges, 116 calibers, 86 manufacturers, 679 BC sources.
Pipeline: 2,637 manifest URLs → 2,118 extracted → 877 flagged entities.

---

### 1. 15 cartridges stored as bullets (Berger + 1 Nosler)

Berger sells both bullet components and loaded ammunition from the same product pages. The pipeline extracted 14 Berger ammo products and 1 Nosler ammo product as bullet entities. Most have BC data (extracted from the page); 3 are referenced as `bullet_id` by cartridges.

Examples:
- `300 Winchester Magnum 185 Grain Classic Hunter Rifle Ammunition` (sku=70020)
- `6.5 mm Creedmoor 135 Grain Classic Hunter Rifle Ammunition` (sku=31031)
- `9mm 115gr ASP JHP Ammunition` (Nosler, sku=60192)

All 15 source URLs:
| SKU | Name | Source URL |
|-----|------|-----------|
| 31031 | 6.5 mm Creedmoor 135 Grain Classic Hunter Rifle Ammunition | bergerbullets.com/product/6-5-mm-creedmoor-135gr-classic-hunter |
| 70090 | 300 Winchester Magnum 230gr Hybrid OTM Tactical | bergerbullets.com/product/300-winchester-magnum-230gr-hybrid-otm-tactical |
| 81060 | 338 Lapua Magnum 250gr Elite Hunter Rifle Ammunition | bergerbullets.com/product/338-lapua-magnum-250gr-elite-hunter |
| 70020 | 300 Winchester Magnum 185 Grain Classic Hunter Rifle Ammunition | bergerbullets.com/product/300-winchester-magnum-185gr-classic-hunter |
| 30032 | 260 Remington 136gr Lapua Scenar -L | bergerbullets.com/product/260-remington-136gr-lapua-scenar-l |
| 23020 | 223 Remington 73 Grain Boat Tail Target Rifle Ammunition | bergerbullets.com/product/223-remington-73-grain-boat-tail-target |
| 30010 | 260 Remington 140gr Hybrid Target | bergerbullets.com/product/260-remington-140gr-hybrid-target |
| 70100 | 300 Winchester Magnum 215gr Hybrid Target | bergerbullets.com/product/300-winchester-magnum-215gr-hybrid-target |
| 31091 | 6.5 mm Creedmoor 153.5 Grain Long Range Hybrid Target Rifle Ammunition | bergerbullets.com/product/6-5-mm-creedmoor-153-5gr-long-range-hybrid-target |
| 62020 | 300 Norma Magnum 215 Grain Hybrid OTM Tactical Rifle Ammunition | bergerbullets.com/product/300-norma-magnum-215gr-hybrid-target |
| 60030 | 308 Winchester 155.5gr Fullbore Target | bergerbullets.com/product/308-winchester-155-5gr-fullbore-target |
| 60060 | 308 Winchester 185gr Juggernaut Target | bergerbullets.com/product/308-winchester-185gr-juggernaut-target |
| 20010 | 6 mm Creedmoor 95 Grain Classic Hunter Rifle Ammunition | bergerbullets.com/product/6-mm-creedmoor-95gr-classic-hunter |
| 60192 | 9mm 115gr ASP JHP Ammunition | nosler.com/asp-9mm-115g-hg-jhp-200ct.html |
| 20030 | 6 mm Creedmoor 109 Grain Long Range Hybrid Target Rifle Ammunition | bergerbullets.com/product/6-mm-creedmoor-109gr-long-range-hybrid-target |

**Action**: Remove/reclassify. 3 are referenced by cartridge `bullet_id` — those FKs need clearing first.

---

### 2. 68 cartridges with wrong bullet_id (weight mismatch >1gr)

From earlier pipeline commits before abbreviation expansion. The resolver matched the right bullet *type* but the DB didn't have the right *weight*, so it assigned the closest available. Breakdown by bullet type:

| Pattern | Count |
|---------|-------|
| CX | 16 |
| SST | 8 |
| InterLock | 6 |
| Terminal Ascent | 4 |
| ELD-X | 2 |
| FTX | 1 |
| Other | 31 |

Examples:
- `350 Legend 150 gr InterLock® Black™` → cart_wt=150gr, assigned bullet_wt=250gr InterLock
- `300 Wby Mag 180 gr. CX® Outfitter®` → cart_wt=180gr, assigned bullet_wt=150gr CX
- `220 Swift 55 gr V-MAX®` → cart_wt=55gr, assigned bullet_wt=35gr V-MAX

**Action**: Self-corrects when missing bullet weights are added and `pipeline-store --commit` is re-run (the update path reassigns `bullet_id`).

---

### 3. 522 flagged bullets — all low-confidence fuzzy matches

All 522 hit `fuzzy_name` at 22–40% confidence. None are "no match" — every one matches a similar bullet at the wrong weight or wrong subtype. They match to 228 unique DB entities (many-to-one).

By manufacturer:
| Manufacturer | Count |
|---|---|
| Sierra | 161 |
| Barnes | 75 |
| Hornady | 71 |
| Cutting Edge | 70 |
| Berger | 67 |
| Nosler | 55 |
| Lapua | 19 |
| Federal | 4 |

Sierra's 161 includes TMK (Tipped MatchKing), TGK (Tipped GameKing), MKX (MatchKing X), VarmintKing — newer product lines not yet in DB. Barnes has TTSX BT and LRX at various weights. Cutting Edge is mostly MTH, ESP Raptor, Maximus, Lazer-Tipped variants.

**Root cause**: DB has representative bullets for most types but is missing many weight variants. Adding these unblocks both bullet creation *and* fixes cartridge `bullet_id` mismatches (issue #2).

---

### 4. 323 flagged cartridges — unresolved references

**141 missing caliber refs** — these calibers aren't in the DB:

| Caliber | Count | Category |
|---------|-------|----------|
| 9mm Luger | 9 | Pistol |
| 40 S&W | 7 | Pistol |
| 10mm Auto | 6 | Pistol |
| 12 GA | 6 | Shotgun |
| not extracted | 6 | LLM failure |
| 338 ARC | 5 | Rifle (new) |
| 357 Magnum | 5 | Pistol |
| 9mm Luger +P | 5 | Pistol |
| 45 Auto | 5 | Pistol |
| 454 Casull | 4 | Pistol |
| 380 Auto | 3 | Pistol |
| 500 S&W Magnum | 3 | Pistol |
| 38 Special | 3 | Pistol |
| 500 Nitro Express | 3 | Rifle (exotic) |
| 45 Colt | 3 | Pistol |
| 6.8mm SPC | 2 | Rifle |
| 357 Sig | 2 | Pistol |
| 45 Auto +P | 2 | Pistol |
| 25 Auto | 2 | Pistol |
| 32 Auto | 2 | Pistol |
| 360 Buckhammer | 2 | Rifle (new) |
| 370 Sako Mag | 2 | Rifle (exotic) |
| 22 ARC | 2 | Rifle (new) |
| 12 GA 00 Buckshot | 2 | Shotgun |
| 444 Marlin | 2 | Rifle |

Plus ~25 more with 1 occurrence each (460 S&W, 480 Ruger, 20 GA, 44 Special, 4.6x30mm, 30 Super Carry, etc.).

**114 missing bullet refs** — bullet doesn't exist in DB or matched below confidence threshold. Top examples: ELD-X (7), Barnes TSX (7), Trophy Copper (6), Jacketed Soft Point (6), FTX (5), Jacketed Hollow Point (4), Fusion Soft Point (4), Fusion Tipped (4).

**Action**: Pistol/shotgun calibers should be **rejected** (not flagged) since we don't need them. Newer rifle calibers (.338 ARC, .22 ARC, .360 Buckhammer) could be seeded if desired.

---

### 5. 38 bullets with no BC data

| Manufacturer | Count |
|---|---|
| Federal | 18 |
| Cutting Edge | 8 |
| Lapua | 5 |
| Nosler | 3 |
| Sierra | 2 |
| Berger | 1 |
| Hornady | 1 |

Likely a mix of: handgun bullets (no published BC), solids/dangerous-game bullets, and extraction gaps where BC wasn't on the product page.

**Action**: Investigate Federal (18) — likely handgun bullets that shouldn't be in DB. Others may be legitimate (DGS solids, etc.).

---

### 6. 46 "duplicate" bullet groups (same mfr + diameter + weight)

Almost all **legitimate** — different bullet types at the same weight. Examples:
- Nosler 6.5mm 140gr: RDF, HPBT Custom Competition, Ballistic Tip (3 distinct products)
- Cutting Edge .338 175gr: MTH, Rifle Maximus FCG, ESP Raptor (3 distinct products)
- Lapua .308 185gr: Scenar OTM, D46 FMJBT (2 distinct products)

The few genuine dupes are the Berger ammo-as-bullet entries from issue #1.

**Not a data problem** — no action needed.

---

### Priority Order

1. **Add rejection mechanism** for calibers we don't need (pistol, shotgun) — prevents ~90 cartridges from being perpetually flagged
2. **Remove/reclassify 15 Berger/Nosler ammo-as-bullet entries**
3. **Seed missing rifle calibers** (.338 ARC, .22 ARC, .360 Buckhammer, etc.) — unblocks ~15 cartridges
4. **Add missing bullet weight variants** — unblocks 522 bullets + fixes 68 cartridge bullet_id mismatches
5. **Investigate 38 bullets with no BC data**
