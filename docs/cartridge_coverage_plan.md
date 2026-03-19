# Cartridge Coverage Plan

**Date:** 2026-03-18
**Status:** Planning

## Current State

- **266 total cartridges** from 2 manufacturers: Hornady (153), Federal (113)
- **1,293 bullets** from 14 manufacturers — bullet coverage is solid
- All target manufacturers already exist in the DB (from bullet ingestion) but have **zero cartridges**

## Key Caliber Coverage

| Caliber | Bullets | Cartridges | Estimated Need |
|---|---|---|---|
| .308 Winchester | 245 | 21 | 30+ more |
| 6.5 Creedmoor | 115 | 16 | 20+ more |
| .223 Remington | 140 | 16 | 20+ more |
| .30-06 Springfield | 245 | 15 | 15+ more |
| .300 Winchester Magnum | 245 | 14 | 15+ more |
| .270 Winchester | 75 | 11 | 10+ more |
| .243 Winchester | 92 | 10 | 10+ more |
| 6mm Creedmoor | 92 | 7 | 8+ more |
| 6.5 PRC | 115 | 7 | 10+ more |
| .224 Valkyrie | 140 | 7 | — |
| 7mm PRC | 104 | 6 | 10+ more |
| .300 AAC Blackout | 245 | 6 | 5+ more |
| .300 Winchester Short Magnum | 245 | 6 | 8+ more |
| .338 Lapua Magnum | 74 | 6 | 5+ more |
| .300 PRC | 245 | 5 | 8+ more |
| 7mm Remington Magnum | 104 | 5 | 8+ more |
| 6.5 Grendel | 115 | 5 | 5+ more |
| 6mm ARC | 92 | 5 | 5+ more |
| .260 Remington | 115 | **0** | Critical gap |

## Manufacturer Priorities

### Tier 1 — Must-have for launch credibility

These manufacturers are what precision/competitive shooters expect. Missing them undermines the app.

#### 1. Berger

The gold standard for PRS competitors. Berger sells factory loaded ammo (relatively recent).

- **Elite Hunter** — high-BC Hybrid hunting bullets in loaded form
- **Target** — Hybrid Target bullets for competition (PRS, F-Class)
- **Classic Hunter** — traditional hunting loads
- **OTM Tactical** — military/LE focused

Key calibers: .223 Rem, 6mm Creedmoor, 6.5 Creedmoor, 6.5 PRC, .308 Win, .30-06, .300 Win Mag, .300 WSM, .300 PRC, .338 Lapua, 7mm PRC.

**Priority lines:** Elite Hunter, Target.

#### 2. Black Hills

Default ammo for serious competitive shooters. Small-batch quality, beloved in the precision community.

- **Black Hills Gold** — premium hunting (Hornady, Barnes, Nosler bullets)
- **Black Hills (blue box)** — match/target (Sierra MatchKing, etc.)
- Only "Factory New" is relevant (they also sell remanufactured)

Key calibers: .223 Rem/5.56, .243 Win, .260 Rem, .308 Win, .30-06, 6.5 Creedmoor, .300 Win Mag, .338 Lapua.

**Priority lines:** Standard match (blue box) in .308/.223/.338 Lapua, Gold in hunting calibers.

#### 3. Nosler

Widely available, high quality. Strong brand recognition.

- **Trophy Grade** — AccuBond and Partition bullets, broad caliber range
- **Trophy Grade Long Range** — AccuBond Long Range bullets, high BC
- **Match Grade** — Custom Competition and RDF bullets
- **Varmageddon** — varmint-focused (lower priority)

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, .300 Win Mag, 7mm Rem Mag, plus Nosler proprietary (.26/.27/.28/.30/.33 Nosler).

**Priority lines:** Match Grade, Trophy Grade Long Range.

### Tier 2 — Major gaps users will notice

#### 4. Winchester

One of the "Big 3" ammo manufacturers. General users will expect Winchester.

- **Match** — BTHP target/competition
- **Ballistic Silvertip** — polymer-tip hunting, wide caliber range
- **Expedition Big Game** — AccuBond bullets
- **Expedition Big Game Long Range** — AccuBond Long Range bullets
- **Deer Season XP** — Extreme Point hunting, high volume seller
- **Copper Impact** — lead-free solid copper
- **Super-X Power Point** — legacy soft-point, budget

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, 6.5 PRC, .300 WSM, .300 Win Mag, 7mm Rem Mag.

**Priority lines:** Match, Expedition Big Game Long Range, Ballistic Silvertip.

#### 5. Barnes

All-copper leader. Popular with hunters, especially in lead-free-mandate areas (California, etc.).

- **VOR-TX** — TSX/TTSX all-copper hunting, wide caliber selection
- **VOR-TX LR** — Long Range variant with LRX bullets, higher BC
- **Precision Match** — OTM Match Burner for competition/target

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, 6mm Creedmoor, .300 WSM, .300 Win Mag, 7mm Rem Mag, .338 Lapua.

**Priority lines:** Precision Match, VOR-TX LR.

#### 6. Norma

We already have 74 Norma bullets from the gap-fill session but zero Norma cartridges.

- **Golden Target** — match/competition
- **BondStrike** — bonded polymer-tip, long-range hunting, high BC
- **TipStrike** — polymer-tip hunting, medium range
- **Whitetail** — soft point budget hunting, very popular in US
- **Ecostrike** — lead-free copper

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, 6.5 PRC, 6mm Creedmoor, .300 Win Mag, .300 WSM, 7mm Rem Mag.

**Priority lines:** Golden Target, BondStrike.

**Note:** Norma pages are 2.3MB SPAs — the standard pipeline reducer can't handle them. May need JSON-LD extraction or curation patches (same approach used for Norma bullets).

### Tier 3 — Good to have, lower urgency

#### 7. Sig Sauer

Growing ammo line, narrower than the majors.

- **Elite Match** — OTM for competition/target
- **Elite Hunter Tipped** — polymer-tip hunting
- **Elite Copper Hunting** — all-copper lead-free

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, 6mm Creedmoor, .300 Win Mag.

#### 8. Remington

Rebuilding post-bankruptcy. Limited current match offerings.

- **Core-Lokt Tipped** — polymer-tip upgrade of classic Core-Lokt
- **Core-Lokt** — original controlled-expansion hunting bullet, iconic
- **Premier Match** — limited current production

Key calibers: .223 Rem, .243 Win, .270 Win, .308 Win, .30-06, 6.5 Creedmoor, .300 Win Mag, 7mm Rem Mag.

#### 9. Lapua

Tiny loaded ammo catalog but prestigious name. Known primarily for brass and bullets.

- **Scenar** — match/target with Scenar and Scenar-L bullets
- **Mega** — soft-point hunting
- **Naturalis** — lead-free copper hunting

Key calibers (limited): .223 Rem, .243 Win, 6.5 Creedmoor, .308 Win, .30-06, .338 Lapua Mag.

**Priority:** Scenar in .308 and .338 Lapua only.

### Skip

- **Sierra** — bullet manufacturer only, not a meaningful factory ammo source. Bullets already in DB.

## Pipeline Inventory Check

What do we already have fetched/extracted that could be leveraged?

| Manufacturer | Fetched Pages | Entity Type | Notes |
|---|---|---|---|
| Berger | 32 loaded ammo pages | Extracted as `bullet` | **Quick win.** All cartridge data present in HTML (MV, caliber, energy) but classified as bullets during extraction. Needs re-extraction or curation. |
| Nosler | 209 pages | All bullets | Component bullet pages only (`XXct.html`). No Trophy Grade / Match Grade ammo pages in manifest. |
| Barnes | 95 pages | All bullets | Component bullet pages only. No VOR-TX / Precision Match ammo pages. |
| Lapua | 60 pages | All bullets | Component bullet pages only. No Scenar loaded ammo pages. |
| Norma | 49 pages | All bullets | From gap-fill session. Ammo pages are 2.3MB SPAs (known issue). |
| Winchester | 0 | — | No winchester.com pages in pipeline at all. |
| Sig Sauer | 0 | — | Not in pipeline. |
| Black Hills | 0 | — | Not in pipeline. |
| Remington | 0 | — | Not in pipeline. |

The cartridge URL manifest (`url_manifest_cartridges.json`) currently only covers Hornady (443 URLs), Federal (391), and Sierra (224, not useful — Sierra doesn't sell loaded ammo).

## Estimated Impact

Adding Tier 1 + Tier 2 across key calibers would add an estimated **200-300 cartridges**, roughly doubling coverage to ~500-550 total. That's a solid launch number.

## Ingestion Approach

| Manufacturer | Approach | Notes |
|---|---|---|
| Berger | Pipeline or curation | Product pages likely scrapable |
| Black Hills | Curation patches | Smaller catalog, may not have structured product pages |
| Nosler | Pipeline | Good product pages with specs |
| Winchester | Pipeline | Large catalog, structured pages |
| Barnes | Pipeline | Product pages available (already in manifest for bullets) |
| Norma | Curation patches | SPA pages too large for pipeline (known issue) |
| Sig Sauer | Pipeline or curation | Moderate catalog size |
| Remington | Pipeline or curation | Post-bankruptcy site may have changed |
| Lapua | Curation patches | Very small catalog, not worth pipeline effort |
