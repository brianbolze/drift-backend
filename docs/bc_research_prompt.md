# BC Research Prompt — CoWork Agent

Use this prompt with a Claude CoWork research agent to find missing ballistic coefficient (BC) data for bullets in the Drift database.

---

## Task

Research and collect G1 and G7 ballistic coefficient values for the bullets listed below. These bullets exist in our database but have no BC data recorded.

## Background

- **G1 BC** is the traditional drag model. Valid range: **0.100–0.800**. Most common model, published by virtually all manufacturers.
- **G7 BC** is the modern long-range drag model (better for boat-tail rifle bullets). Valid range: **0.050–0.450**. Published by Hornady, Sierra, Berger, and some others. Barnes/Nosler/Federal typically only publish G1.
- Values outside these ranges are almost certainly errors.
- Some manufacturers publish BCs at multiple velocities (e.g., Sierra publishes BCs at 2800, 2400, and 2000 fps). **Record the highest-velocity BC** (closest to muzzle velocity) as it's most commonly used for trajectory calculation.

## Output Format

For each bullet where you find BC data, provide a row in this format:

```
manufacturer | bullet_name | weight_gr | diameter_in | bc_g1 | bc_g7 | source_url | notes
```

Example:
```
Federal | Fusion Component Bullet, .308, 180 Grain | 180 | 0.308 | 0.503 | — | https://www.federalpremium.com/... | G1 from ammo product page, G7 not published
```

Use `—` for values you cannot find. Add notes explaining where you found the data or why it wasn't available.

---

## Bullets Missing BC Data

### Priority 1: Federal (17 bullets — no BCs at all)

Federal does **not** publish BCs on their component bullet product pages. Try these strategies:
1. Check the **loaded ammunition** pages that use each bullet — Federal sometimes lists BCs on ammo pages even when the component page omits them
2. Check the Federal ammunition catalog PDF (usually at federalpremium.com)
3. Search for "Federal [bullet name] ballistic coefficient" — third-party reviews and reloading forums often cite Federal BCs

| Bullet Name | Weight | Diameter |
|---|---|---|
| Fusion Component Bullet, .224 | 90 gr | 0.224" |
| Fusion Component Bullet, .264 | 140 gr | 0.264" |
| Fusion Component Bullet, .277 | 150 gr | 0.277" |
| Fusion Component Bullet, .284 | 140 gr | 0.284" |
| Fusion Component Bullet, .308 | 180 gr | 0.308" |
| Terminal Ascent Component Bullet, .264 | 130 gr | 0.264" |
| Terminal Ascent Component Bullet, .277 | 136 gr | 0.277" |
| Terminal Ascent Component Bullet, .284 | 155 gr | 0.284" |
| Terminal Ascent Component Bullet, .308 | 175 gr | 0.308" |
| Trophy Bonded Bear Claw Component Bullet, .375 | 250 gr | 0.375" |
| Trophy Bonded Sledgehammer Solid Component Bullet, .375 | 300 gr | 0.375" |
| Trophy Bonded Sledgehammer Solid Component Bullet, .416 | 400 gr | 0.416" |
| Trophy Bonded Sledgehammer Solid Component Bullet, .458 | 500 gr | 0.458" |
| Trophy Bonded Tip Component Bullet, .277 | 130 gr | 0.277" |
| Trophy Bonded Tip Component Bullet, .284 | 160 gr | 0.284" |
| Trophy Bonded Tip Component Bullet, .308 | 165 gr | 0.308" |
| Trophy Bonded Tip Component Bullet, .338 | 200 gr | 0.338" |

### Priority 2: Cutting Edge Bullets (26 missing)

Cutting Edge publishes BCs on most product pages, but these specific bullets were missed during extraction. Visit each product page at `cuttingedgebullets.com/products/[slug]`.

**Tip**: Many of these are handgun, safari, and lever-gun bullets where BCs are less commonly published. If the product page doesn't list a BC, note "not published" rather than searching elsewhere — Cutting Edge is the only authoritative source for their proprietary bullet designs.

| Bullet Name | Weight | Diameter |
|---|---|---|
| .243/6mm 55gr ESP Raptor | 55 gr | 0.243" |
| .257 80gr ESP Raptor | 80 gr | 0.257" |
| .277/6.8mm 110gr ESP Raptor | 110 gr | 0.277" |
| .284/7mm 130gr ESP Raptor | 130 gr | 0.284" |
| .311 124gr MTAC (Match/Tactical) | 124 gr | 0.311" |
| .311 130gr ESP Raptor | 130 gr | 0.311" |
| .323/8mm 175gr ESP Raptor | 175 gr | 0.323" |
| .338 175gr ESP Raptor | 175 gr | 0.338" |
| .357 105gr Handgun Raptor | 105 gr | 0.357" |
| .357 140gr Handgun Raptor | 140 gr | 0.357" |
| .357 165gr Handgun Solid | 165 gr | 0.357" |
| .358 153gr ER Raptor LEVER GUN | 153 gr | 0.358" |
| .366(9.3mm) 200gr Flat Base Raptor | 200 gr | 0.366" |
| .366/9.3mm 210gr ESP Raptor | 210 gr | 0.366" |
| .375 200gr Handgun Raptor | 200 gr | 0.375" |
| .375 220gr Handgun Solid | 220 gr | 0.375" |
| .375 230gr ESP Raptor | 230 gr | 0.375" |
| .416 180gr Flat Base Raptor | 180 gr | 0.416" |
| .416 300gr ESP Safari Raptor | 300 gr | 0.416" |
| .45 240gr Handgun Raptor | 240 gr | 0.452" |
| .452 250gr Flat Base Raptor | 250 gr | 0.452" |
| .458 265gr Flat Base Raptor | 265 gr | 0.458" |
| .500 335gr Safari Raptor Super Short | 335 gr | 0.500" |
| .500 340gr Handgun Raptor | 340 gr | 0.500" |
| .500 350gr ESP Safari Raptor | 350 gr | 0.500" |
| .500 400gr Handgun Solid | 400 gr | 0.500" |

### Priority 3: Other Manufacturers (13 bullets)

| Manufacturer | Bullet Name | Weight | Diameter | Tips |
|---|---|---|---|---|
| Hornady | 50 Cal .500 500 gr DGH | 500 gr | 0.500" | Check hornady.com product page — Hornady publishes both G1/G7 |
| Lapua | 12,0 g / 185 gr Open Tip G574 | 185 gr | 0.366" | Check lapua.com — Lapua publishes G1 (and sometimes G7) on product pages |
| Lapua | 15,0 g / 231 gr Naturalis N508 | 231 gr | 0.338" | Same as above |
| Lapua | 16,2 g / 250 gr Lock Base FMJBT B408 | 250 gr | 0.338" | Same as above |
| Lapua | 5.8 g / 90 gr Naturalis N509 | 90 gr | 0.243" | Same as above |
| Lapua | 7,85 g / 120 gr Open Tip G573 | 120 gr | 0.323" | Same as above |
| Lehigh Defense | .172 20gr Controlled Chaos | 20 gr | 0.172" | Check lehighdefense.com product page |
| Lehigh Defense | .284 135gr Tipped Controlled Chaos | 135 gr | 0.284" | Same as above |
| Lehigh Defense | .416 350gr Wide Flat Nose | 350 gr | 0.416" | WFN bullets often don't have published BCs |
| Lehigh Defense | .510 720gr Match Solid | 720 gr | 0.510" | Check product page |
| Nosler | 308 Win 175g Match Grade RDF HPBT | 175 gr | 0.308" | This is actually ammo, not a bullet — check nosler.com for the 30cal 175gr RDF bullet page instead |
| Nosler | 6mm 55gr SPFB S.H.O.T.S. | 55 gr | 0.243" | Discontinued product line — BC may only be in old catalogs |
| Sierra | 22 CAL 60 GR Tipped MatchKing (TMK) | 60 gr | 0.224" | Check sierrabullets.com — Sierra always publishes G1/G7, this may be a new product |

---

## Manufacturer Research Tips

### Where BCs are published

| Manufacturer | G1 | G7 | Location | Notes |
|---|---|---|---|---|
| Sierra | Always | Always | Product page spec table | Multi-velocity BCs — use highest velocity value |
| Hornady | Always | Usually | Product page spec table | Some older products only have G1 |
| Berger | Always | Always | Product page spec table | Also has sectional density |
| Barnes | Usually | Rarely | Product page spec table | G1 only for most products |
| Nosler | Usually | Rarely | Load data section, NOT product page | Product pages often omit BC — check load data or reloading guide |
| Lapua | Usually | Sometimes | Product page spec table | Metric-first formatting (g before gr) |
| Speer | Usually | Rarely | Product page | Mostly G1 only |
| Federal | Rarely | Never | Ammo product pages, not component pages | BCs almost never on component bullet pages; check loaded ammo pages |
| Cutting Edge | Usually | Sometimes | Product page | Custom bullets may not have published BCs |
| Lehigh Defense | Sometimes | Rarely | Product page | Unconventional designs (Controlled Chaos, Xtreme Defense) — some have no published BC |

### Search strategy for hard-to-find BCs

1. Check the manufacturer's product page first (most reliable source)
2. For Federal: check loaded ammunition pages that use the bullet
3. Search `"[bullet name] [weight]gr ballistic coefficient"` or `"[bullet name] [weight]gr BC"`
4. Check manufacturer PDF catalogs (often have more data than web pages)
5. Reloading forums (accurateshooter.com, snipershide.com, longrangehunting.com) — users sometimes post BCs from reloading manuals
6. Bryan Litz's "Applied Ballistics" books — gold standard for independently measured BCs (but may not be freely available online)

### What to skip

- **Handgun bullets** (.357, .452, etc.) — BCs are less important for handgun ballistics and often not published. Note "not published — handgun bullet" and move on.
- **Safari solids / dangerous game** — flat-nose solids (DGS, Sledgehammer Solid, Woodleigh Hydro Solid) have very low BCs that aren't useful for long-range calculation. Record if found, but don't spend time searching third-party sources.
- **Lever gun bullets** — similar to handgun bullets, BCs are less critical. Record if on the product page, skip deep research.
