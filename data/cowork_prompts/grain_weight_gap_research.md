# CoWork Research Prompt: Missing Bullet Grain Weight Variants

## Context

The Drift ballistics database has 641 bullets and 270 factory cartridges. **100 cartridges (37%) are linked to the wrong bullet** because the correct bullet at the needed grain weight doesn't exist in our DB. The resolver falls back to the closest-match bullet, causing weight mismatches of up to 100 grains.

We need you to find manufacturer product page URLs for the missing bullet variants so we can run them through our extraction pipeline.

## Output Format

Return a JSON array. Each entry should look like:

```json
{
  "url": "https://www.hornady.com/bullets/cx/30-cal-308-165-gr-cx-item-30392",
  "entity_type": "bullet",
  "expected_manufacturer": "Hornady",
  "expected_caliber": ".308",
  "brief_description": "30 Cal .308 165gr CX",
  "confidence": "high",
  "notes": "Product page with BC data"
}
```

Rules:
- `url` must be the actual manufacturer product page (not retailer/3rd party)
- `entity_type` is always `"bullet"` for this task
- `expected_manufacturer` must be one of the exact names below
- `expected_caliber` should be the bullet diameter category (e.g., ".308", "6.5mm", ".224")
- `confidence`: "high" if you visited the page and confirmed specs, "medium" if URL pattern looks right but unverified
- Only include URLs where the page has bullet specs (weight, diameter, and ideally BC values)

## Manufacturer Names (use exactly)

- `Hornady` — hornady.com
- `Barnes Bullets` — barnesbullets.com
- `Federal` — federalpremium.com
- `Nosler` — nosler.com
- `Sierra Bullets` — sierrabullets.com
- `Speer` — speer.com
- `Berger Bullets` — bergerbullets.com
- `Lapua` — lapua.com

## Missing Bullets to Find

### Priority 1 — Hornady CX (20 cartridge mismatches)

These CX bullet variants are needed at the following diameter + weight combos. Our DB only has the 130gr 6.5mm and 150gr .308 CX — all other weights are missing.

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.224 | 50 | .223 Rem, .22-250 Rem, 5.56 NATO |
| 0.224 | 55 | .223 Rem, 5.56 NATO, .223 WSSM, .220 Swift |
| 0.243 | 80 | .243 Win |
| 0.257 | 90 | .257 Wby Mag, .25-06 Rem |
| 0.264 | 90 | 6.5 Grendel |
| 0.308 | 110 | .300 Blackout |
| 0.308 | 165 | .308 Win, .300 Win Mag |
| 0.308 | 180 | .30-06, .300 WSM, .300 Win Mag, .300 Wby Mag, .300 RUM |
| 0.308 | 190 | .300 PRC |
| 0.338 | 225 | .338 Win Mag |

Look at: `https://www.hornady.com/bullets/cx/` — these should all be on the CX product line page or individual SKU pages.

### Priority 2 — Hornady V-MAX (14 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.172 | 17 | .17 HMR |
| 0.204 | 32 | .204 Ruger |
| 0.224 | 30 | .22 WMR |
| 0.224 | 50 | .223 Rem, .22-250 Rem, .222 Rem |
| 0.224 | 53 | .223 Rem |
| 0.224 | 55 | .223 Rem, .22-250 Rem, .220 Swift |
| 0.224 | 60 | .224 Valkyrie |
| 0.243 | 75 | .243 WSSM, .243 Win |
| 0.243 | 87 | .243 Win |

Look at: `https://www.hornady.com/bullets/v-max/`

### Priority 3 — Hornady ELD-X (11 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.243 | 90 | .243 Win |
| 0.257 | 110 | .257 Wby Mag, .25-06 Rem |
| 0.284 | 150 | 7mm-08 Rem, .280 Rem |
| 0.284 | 162 | .28 Nosler, 7mm Rem Mag, 7mm WSM, .280 Ackley |

Look at: `https://www.hornady.com/bullets/eld-x/`

### Priority 4 — Hornady SST (10 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.264 | 129 | 6.5 Creedmoor, .260 Rem, 6.5 PRC |
| 0.277 | 130 | .270 Win |
| 0.308 | 125 | .308 Win, .30-06 |
| 0.308 | 150 | .308 Win, .300 Savage, .30-30 Win |
| 0.308 | 180 | .308 Win |

Look at: `https://www.hornady.com/bullets/sst/`

### Priority 5 — Barnes TSX (9 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.224 | 55 | .223 Rem |
| 0.224 | 78 | .224 Valkyrie |
| 0.257 | 100 | .25-06 Rem |
| 0.264 | 130 | 6.5 Creedmoor |
| 0.277 | 130 | .270 Win |
| 0.284 | 140 | .280 Rem, 7mm-08 Rem |
| 0.308 | 165 | .308 Win, .300 WSM |
| 0.308 | 180 | .30-06, .300 Win Mag |

Look at: `https://www.barnesbullets.com/bullets/tsx/` — Barnes uses ALL CAPS names and their URLs are typically `barnesbullets.com/bullets/[line]/` with individual products listed.

### Priority 6 — Federal Fusion & Trophy Bonded Tip (10 mismatches)

**Fusion:**
| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.264 | 120 | 6.5 Grendel |
| 0.277 | 115 | 6.8 SPC |
| 0.284 | 150 | 7mm Rem Mag |
| 0.308 | 180 | .308 Win, .300 Win Mag |

**Trophy Bonded Tip:**
| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.277 | 130 | .270 Win |
| 0.284 | 140 | .280 Rem, 7mm-08 Rem |
| 0.308 | 180 | .300 WSM |

Note: Federal component bullets are at `federalpremium.com/bullets/` — these may be harder to find as individual product pages. Federal often publishes BCs on their component bullet pages.

### Priority 7 — Hornady Other Lines (misc, 10+ mismatches)

**InterLock:**
| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.308 | 150 | .308 Win, .30-06, .30-30 Win |
| 0.357 | 150 | .350 Legend |
| 0.357 | 170 | .350 Legend |

**ECX (Hornady International):**
| Diameter | Weight (gr) | Notes |
|----------|------------|-------|
| 0.264 | 140 | 6.5x55mm Swedish |
| 0.308 | 125 | (already in DB at 125gr — verify) |
| 0.308 | 150 | .30-06 |

**Other one-offs:**
- 0.308, 135gr FTX (.300 Blackout)
- 0.308, 155gr Critical Defense (.308 Win)
- 0.308, 175gr Sub-X (.30-30 Win subsonic)
- 0.308, 178gr BTHP Match (.308 Win)
- 0.308, 195gr ELD Match (.300 Win Mag)
- 0.308, 208gr ELD Match (.300 Blackout)
- 0.308, 225gr ELD Match (.300 PRC)
- 0.308, 168gr ELD Match (.30-06 M1 Garand)
- 0.284, 160gr CX (7mm PRC)
- 0.284, 162gr ELD-X (.28 Nosler — may overlap with Priority 3)

### Priority 8 — Federal Terminal Ascent (4 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.284 | 170 | 7mm PRC, 7mm Backcountry |
| 0.308 | 200 | .300 WSM, .300 Win Mag |

Look at: `federalpremium.com/bullets/` or the Terminal Ascent product line.

### Priority 9 — Large Bore (2 mismatches)

| Diameter | Weight (gr) | Caliber Context |
|----------|------------|-----------------|
| 0.458 | 500 | .458 Lott, .458 Win Mag (DGX Bonded, DGS) |

## What We Already Have (avoid duplicates)

Don't submit URLs for bullets we already have. Key existing inventory:

- Hornady CX: 130gr 6.5mm, 150gr .308
- Hornady ELD-X: 143gr 6.5mm, 175gr 7mm, 178gr .308, 200gr .308, 212gr .308, 220gr .308
- Hornady ELD Match: 140gr 6.5mm, 147gr 6.5mm, 178gr .308, 225gr .338
- Hornady SST: 165gr .308
- Barnes TSX: 150gr .308 (30-30), plus many LRX and TTSX variants
- Federal Fusion: 150gr .277, 180gr .308 (component), others
- Federal Trophy Bonded Tip: 165gr .308, 200gr .308

## Tips for URL Discovery

1. **Hornady**: Well-structured site. Product lines at `hornady.com/bullets/[line]/`. Individual bullets often have SKU-based URLs. They publish G1 BCs on most bullet pages.
2. **Barnes**: `barnesbullets.com/bullets/[line]/`. Individual bullets may be on line overview pages rather than individual URLs. They publish G1 BCs.
3. **Federal**: `federalpremium.com/bullets/`. Component bullet catalog. Good BC data (often both G1 and G7).
4. **Sierra**: `sierrabullets.com/products/`. Good BC data for all products.
5. **Nosler**: BCs are typically NOT on product pages (only in load data). Still useful to get the bullet into our DB even without BCs.

## Deliverable

A single JSON file with all discovered URLs. Aim for **60-90 entries** covering all the gaps above. Name the file based on the research scope, e.g., `missing_grain_weights_research.json`.
