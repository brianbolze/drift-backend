# JBM Coverage Audit — 2026-03-15

## Methodology

Scraped all 3,520 bullet entries from the JBM Ballistics drift calculator library dropdown
(`jbmballistics.com/cgi-bin/jbmtraj_drift-5.1.cgi`). Parsed manufacturer, caliber (inches),
weight (grains), and bullet name. Matched against Drift DB on (manufacturer + diameter + weight).

**Matching rules**: Manufacturer names normalized via alias table. Diameter and weight compared
as rounded floats. A "match" means at least one Drift bullet exists for the same manufacturer,
diameter, and weight — it does NOT verify name/model correspondence.

## High-Level Summary

| Dataset | Count |
|---------|------:|
| JBM total entries | 3,520 |
| JBM rifle-relevant (cal >= 0.204, excl rimfire ammo mfrs) | 3,418 |
| Drift DB bullets | 1,132 |

## Key Manufacturer Coverage (Rifle Bullets Only)

| Manufacturer | Drift | JBM | Matched | Coverage | Gaps | Notes |
|---|---|---|---|---|---|---|
| Nosler | 130 | 251 | 242 | **96%** | 9 | Near-complete |
| Hornady | 173 | 381 | 345 | **91%** | 36 | Gaps are legacy/obscure + pistol-crossover |
| Sierra | 145 | 225 | 202 | **90%** | 23 | Gaps mostly pistol/varmint + legacy |
| Speer | 93 | 167 | 134 | **80%** | 33 | Safari/large-bore + some rifle gaps |
| Barnes | 117 | 280 | 215 | **77%** | 65 | Many large-bore safari + discontinued XLC |
| Berger | 82 | 218 | 165 | **76%** | 53 | Most actionable — .224 and .308 match bullets |
| Lapua | 51 | 133 | 100 | **75%** | 33 | 13 are rimfire (0.223 cal in JBM) |

## Manufacturers in JBM but Missing from Drift

| Manufacturer | JBM Rifle Count | Priority | Notes |
|---|---|---|---|
| **Winchester** | 185 | HIGH | Major ammo + component bullet maker |
| **Woodleigh** | 125 | LOW | Safari/dangerous game specialist |
| **Swift** | 55 | HIGH | A-Frame, Scirocco II — blocks cartridge resolution |
| **Sako** | 63 | MED | European brand, popular in Nordic markets |
| **Peregrine** | 271 | LOW | South African, niche in US market |
| **Prvi Partizan** | 165 | LOW | Budget/surplus, limited BC data |
| **Norma** | 38 | MED | Already 0 in DB despite being in manifest |
| **GS Custom** | 138 | LOW | South African monolithic specialist |
| **Sellier & Bellot** | 37 | LOW | European budget brand |

## Actionable Rifle Bullet Gaps (Excluding Pistol, Safari .450+, Rimfire)

### Berger — 53 gaps, HIGH priority
Biggest cluster: **19 missing in .224** (30-90gr Match/VLD/Hybrid), **14 missing in .308**
(110-210gr Match/VLD/BT). These are core competition shooting bullets.

Key missing:
- .224 75gr/82gr/90gr Match Target BT/VLD (PRS/NRL staples)
- .308 190gr/210gr VLD and Match BT Long Range (F-class, ELR)
- .243 60-100gr Match variants (6mm competition)

### Hornady — 36 gaps, MED priority
Mostly legacy/discontinued (Jet, old Spire Points) and niche calibers (.222, .227, .268).
Only 2 gaps in .224 (68gr BTHP Match — may actually be in DB under different name).

### Sierra — 23 gaps, MED priority
.224 gaps include 40gr BlitzKing and 95gr HPBT MatchKing (uncommon). 52gr MatchKing
variants may be name mismatches. .308 240gr MatchKing is notable for ELR.

### Nosler — 9 gaps, LOW priority
Near-complete. Gaps are legacy (Solid Base, Fail Safe) and niche weights.

### Lapua — 33 gaps, MED priority
13 gaps are .22 LR rimfire mislabeled as 0.223. Real rifle gaps: .243 HP variants,
.308 Scenar CD variant, .338 AP (military). The .510 Bullex-N (5 entries) are
.50 BMG competition bullets — potentially relevant.

### Speer — 33 gaps, MED priority
Mix of rifle (DeepCurl, Hot-Cor hunting) and large-bore safari. The .243 6-entry
gap (DeepCurl, Spitzer SP) is the most rifle-relevant cluster.

## JBM as BC Data Source

JBM includes published BC values for all 3,520 entries. Notable:
- **261 entries marked "(Litz)"** — Bryan Litz independently measured BCs (gold standard)
- Could supplement our `BulletBCSource` records, especially for the 66 Drift bullets missing BC data
- JBM BC values are G1 with drag function specified — would need to note drag model in BC source

## Raw Data

Parsed CSVs saved at session time:
- `/tmp/jbm_bullets.csv` — all 3,520 JBM entries (manufacturer, caliber_inches, weight_gr, bullet_name)
- `/tmp/drift_bullets.csv` — all 1,132 Drift bullets for comparison
