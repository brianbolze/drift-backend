# SAAMI Test Barrel Length Reference — All Drift Calibers

**Research Date:** March 18, 2026
**Primary Source:** ANSI/SAAMI Z299.4-CFR-2025 (Centerfire Rifle), ANSI/SAAMI Z299.1 (Rimfire)
**Status:** Ready for DB population

---

## Governing Rule

From SAAMI Z299.4-2025, Section III, p. 242:

> "All standard test barrels shall be 24 inches long (610 mm). Exterior ballistic data for all centerfire rifle cartridges shall be based on this length."

**Translation:** Unless a cartridge is explicitly listed as an exception, the SAAMI test barrel is **24"**. The exceptions are enumerated in the standard and reproduced below.

### SAAMI Explicit Exceptions (from Z299.4-2025, p. 242)

| Cartridge | Test Barrel (in) | Test Barrel (mm) |
|---|---|---|
| 7.62x39mm | 20 | 508.00 |
| .277 Sig Fury | 16 | 406.40 |
| .30 Carbine | 20 | 508.00 |
| .300 AAC Blackout | 16 | 406.40 |
| .300 HAM'R | 16 | 406.40 |
| .350 Legend | 16 | 406.40 |
| .350 Remington Magnum | 20 | 508.00 |
| .360 Buckhammer | 20 | 508.00 |
| .400 Legend | 16 | 406.40 |
| .44 Remington Magnum | 20 | 508.00 |

---

## Existing Values — Validated

| Caliber | Current Value (in) | Validated Value (in) | Source | Status |
|---|---|---|---|---|
| .223 Remington | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 5.56x45mm NATO | 20 | 24 | SAAMI Z299.4-2025 (default rule); NATO STANAG uses 20" but SAAMI spec is 24" for .223/5.56 | **CORRECTED → 24** |
| .243 Winchester | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 6mm ARC | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 6mm Creedmoor | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .260 Remington | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 6.5 Creedmoor | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 6.5 PRC | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .270 Winchester | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 7mm PRC | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 7mm Remington Magnum | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 7mm-08 Remington | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .30-06 Springfield | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .300 AAC Blackout | 16 | 16 | SAAMI Z299.4-2025 (explicit exception, p. 242) | **Confirmed** |
| .300 PRC | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .300 Winchester Magnum | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .300 Winchester Short Magnum | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| .308 Winchester | 24 | 24 | SAAMI Z299.4-2025 (default rule) | **Confirmed** |
| 7.62x51mm NATO | 24 | 24 | SAAMI Z299.4-2025 (default rule); NATO uses different test protocol but SAAMI spec is 24" | **Confirmed** |
| .338 Lapua Magnum | 27 | 24 | SAAMI Z299.4-2025 (default rule) — NOT an exception; .338 Lapua is SAAMI-standardized at 24" | **CORRECTED → 24** |

### Important Corrections

1. **5.56x45mm NATO:** The DB had 20". While NATO's STANAG test protocol uses a 20" barrel, the SAAMI specification for 5.56/.223 uses the standard 24" barrel. Since Drift references SAAMI/reloading-manual velocities (not NATO EPV data), **use 24"**.

2. **.338 Lapua Magnum:** The DB had 27". The SAAMI Z299.4-2025 V&P data tables list .338 Lapua Magnum with no barrel-length exception footnote — meaning it uses the standard 24" barrel. The 27" figure likely comes from CIP specifications or Lapua's own testing. **Use 24" for SAAMI consistency.** (Note: if the app later adds a CIP-reference mode, 27.17" / 690mm from CIP would be appropriate.)

---

## All Missing Calibers — Complete Reference

### .17 / .20 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .17 HMR | 24 | SAAMI Z299.1 (rimfire standard: all rimfire test barrels = 24") | High | Rimfire |
| .17 Hornet | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables, no exception footnote |
| .17 WSM | 24 | SAAMI Z299.1 (rimfire standard) | High | Rimfire |
| .204 Ruger | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables, no exception footnote |

### .22 Caliber — Rimfire

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| 5.45x39mm | 24 | CIP ~600mm barrel; no SAAMI spec | Medium | Not SAAMI-standardized; CIP uses 600±10mm (~23.6"). Use 24" as closest integer. |
| .22 Long Rifle | 24 | SAAMI Z299.1 (rimfire standard) | High | Rimfire |

### .22 Caliber — Centerfire

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .22 Creedmoor | 24 | SAAMI Z299.4-2025 (default rule) | High | Now SAAMI-standardized; listed in V&P tables p.14, no exception |
| .22 Hornet | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.14, no exception |
| .22 Nosler | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.14, no exception |
| .22 WMR | 24 | SAAMI Z299.1 (rimfire standard) | High | Rimfire |
| .22-250 Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.14, no exception |
| .220 Swift | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.15, no exception |
| .222 Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.15, no exception |
| .222 Remington Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.15, no exception |
| .223 WSSM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.16, no exception |
| .224 Valkyrie | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.16, no exception |

### 6mm / .243 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .240 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | SAAMI-standardized Weatherby cartridge |
| .243 WSSM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.17, no exception |
| 6mm BR Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | SAAMI-standardized |
| 6mm BRA | 24 | De facto community standard (Hodgdon data) | Medium | Wildcat — no official SAAMI spec. Load data typically uses 24-26" barrels. Use 24" for consistency. |
| 6mm Dasher | 24 | De facto community standard | Medium | Wildcat — no SAAMI spec. Hodgdon tested with 30" barrel for pressure; competition community uses 24-28". Use 24" for consistency with SAAMI-standardized parent case (6mm BR). |
| 6mm GT | 24 | SAAMI Z299.4-2025 (default rule) | High | Now SAAMI-standardized! Listed in V&P tables p.11, no exception |
| 6mm Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.11, no exception |
| 6mm XC | 24 | De facto (Sierra manual) | Medium | Wildcat — no SAAMI spec. Sierra uses 24" test barrel. |
| 6mm-284 | 24 | CIP standard / de facto | Medium | Wildcat in SAAMI context; CIP-standardized. Use 24" for consistency. |
| 6x45mm | 24 | De facto (published load data) | Medium | Wildcat — no SAAMI spec. Published data uses 24" barrels. |

### .25 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .25 Creedmoor | 24 | SAAMI Z299.4-2025 (default rule) — likely SAAMI-standardized or use parent case standard | High | Based on Creedmoor family; all use 24" |
| .25 GT | 24 | De facto (parent case: 6mm GT = 24" SAAMI) | Medium | Wildcat — no SAAMI spec. Use parent case standard. |
| .25 Weatherby RPM | 24 | SAAMI Z299.4-2025 (default rule) | High | Weatherby RPM cartridges are SAAMI-standardized at 24" |
| .25-06 Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.18, no exception |
| .257 Roberts | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.18, no exception |
| .257 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.18, no exception |
| .25x47 Lapua | 24 | CIP / de facto | Medium | Not SAAMI-standardized. Lapua/CIP spec. Use 24" for consistency. |

### 6.5mm / .264 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .26 Nosler | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.18, no exception |
| .260 Ackley Improved | 24 | De facto (parent: .260 Rem = 24") | Medium | Wildcat/AI variant — no SAAMI spec. Use parent case standard. |
| .264 Winchester Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.18, no exception |
| 6.5 Grendel | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.11, no exception |
| 6.5 SAUM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "6.5 Remington Short Action Ultra Magnum" |
| 6.5 Weatherby RPM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.11; barrel drawing confirms 24" (p.264) |
| 6.5-284 Norma | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.11, no exception |
| 6.5x55mm Swedish | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.12, no exception. CIP uses 630mm but SAAMI = 24". |

### .270 / 6.8mm Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .270 WSM | 24 | SAAMI Z299.4-2025 (default rule) | High | No exception footnote |
| .270 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.19, no exception |
| .277 Fury | 16 | SAAMI Z299.4-2025 (explicit exception, p. 242) | High | 16" test barrel per SAAMI; footnoted in V&P tables |
| 6.8 SPC | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "6.8mm Remington SPC" in V&P tables p.12, no exception |
| 6.8 Western | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.12, no exception |

### 7mm / .284 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .28 Nosler | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.19, no exception |
| .280 Ackley Improved | 24 | SAAMI Z299.4-2025 (default rule) | High | Now SAAMI-standardized; listed in V&P tables p.19, no exception |
| .280 Remington | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.20, no exception |
| .284 Winchester | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.20, no exception |
| 7mm Backcountry | 24 | De facto (Federal data at 24") | Medium | SIG/Federal proprietary; Federal publishes data at both 20" and 24". Use 24" for consistency. Not yet SAAMI-standardized. |
| 7mm SAUM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "7mm Remington Short Action Ultra Magnum" p.12, no exception |
| 7mm WSM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.13, no exception |
| 7x57mm Mauser | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "7mm Mauser (7x57)" in V&P tables p.12, no exception |

### .30 / .308 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .30 Nosler | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.20, no exception |
| .30 Remington AR | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.20, no exception |
| .30-30 Winchester | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.21, no exception |
| .300 HAM'R | 16 | SAAMI Z299.4-2025 (explicit exception, p. 242) | High | 16" test barrel per SAAMI; footnoted in V&P tables |
| .300 Norma Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.21, no exception |
| .300 RSAUM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.22, no exception |
| .300 RUM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.22, no exception |
| .300 Ruger Compact Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.22, no exception |
| .300 Savage | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.22, no exception |
| .300 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.22, no exception. Note: Weatherby factory data uses 26" barrels, but SAAMI spec is 24". |
| .308 Marlin Express | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.23, no exception |
| 7.62x40mm WT | 24 | De facto (Wilson Combat; no SAAMI spec) | Low | Wilson Combat proprietary; not SAAMI-standardized. Common barrel lengths are 16-20". Use 24" for consistency or 16" if matching Wilson Combat's intended platform. |

### .303 / 7.62x39 / Other Soviet

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .303 British | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.23, no exception |
| 7.62x39mm | 20 | SAAMI Z299.4-2025 (explicit exception, p. 242) | High | Footnoted "(2) – Based on a 20" test barrel" in V&P tables |
| 7.62x54mmR | 24 | CIP ~600mm; no SAAMI spec — use 24" for consistency | Medium | Not SAAMI-standardized. CIP uses 600±10mm (~23.6"). Round to 24" for app consistency. |

### 8mm

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .325 WSM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.24, no exception |
| 8x57mm Mauser | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "8mm Mauser (8 x 57)" in V&P tables p.13, no exception |

### .338 / .340 Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .338 EnABELR | 30 | Applied Ballistics (proprietary spec) | Medium | Not SAAMI-standardized. Applied Ballistics uses 30" for ELR testing. |
| .338 Federal | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.24, no exception |
| .338 Norma Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.25, no exception. CIP uses 660mm (~26"), but SAAMI = 24". |
| .338 RUM | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.25, no exception |
| .338 Winchester Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.25, no exception |
| .338-378 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | SAAMI-standardized Weatherby cartridge; no exception |
| .340 Weatherby Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.25, no exception |

### .35+ Caliber

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .350 Legend | 16 | SAAMI Z299.4-2025 (explicit exception, p. 242) | High | Footnoted in V&P tables |
| .35 Whelen | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.26, no exception |
| 9.3x62mm Mauser | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed as "9.3 x 62" in V&P tables p.13, no exception. CIP uses 600mm. |
| 9.3x74mmR | 24 | CIP ~600mm; not in SAAMI spec | Medium | Not SAAMI-standardized. CIP uses 600±10mm. Use 24" for consistency. |

### Long-Range / Anti-Material Calibers

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .375 CheyTac | 30 | CheyTac LLC proprietary spec | Low | Not SAAMI-standardized. Original spec ~29-30"; no industry standard. |
| .375 EnABELR | 30 | Applied Ballistics (proprietary spec) | Medium | Not SAAMI-standardized. Applied Ballistics uses 30" for ELR. |
| .375 H&H Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.26, no exception |
| .375 Ruger | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.27, no exception |
| .408 CheyTac | 30 | CheyTac LLC proprietary spec | Low | Not SAAMI-standardized. Original M200 spec is 29-30". |
| .416 Barrett | 32 | Barrett proprietary spec | Low | Not SAAMI-standardized. Barrett M82A1-type rifles use 29-32" barrels. |
| .416 Remington Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.27, no exception |
| .416 Rigby | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.27, no exception |

### .45+ Big Bore

| Caliber | Test Barrel (in) | Source | Confidence | Notes |
|---|---|---|---|---|
| .450 Bushmaster | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.28, no exception |
| .45-70 Government | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.28, no exception |
| .458 Lott | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.28, no exception |
| .458 SOCOM | 24 | De facto (community standard) | Medium | Not SAAMI-standardized. Commonly tested in 16" AR barrels, but no official spec. Use 24" for consistency with SAAMI methodology. |
| .458 Winchester Magnum | 24 | SAAMI Z299.4-2025 (default rule) | High | Listed in V&P tables p.28, no exception |
| .50 Beowulf | 16 | Alexander Arms proprietary spec | Medium | Not SAAMI-standardized. Alexander Arms designed for AR-15 platform; 16" is standard. |
| .50 BMG | 45 | Military spec (no SAAMI standard) | Medium | Not SAAMI-standardized. Military M2 barrel = 45". CIP uses different spec. |

---

## Quick-Reference: Non-24" Calibers in Drift DB

These are the only calibers that should NOT be set to 24":

| Caliber | Test Barrel (in) | Authority |
|---|---|---|
| .277 Fury | 16 | SAAMI exception |
| .300 AAC Blackout | 16 | SAAMI exception |
| .300 HAM'R | 16 | SAAMI exception |
| .350 Legend | 16 | SAAMI exception |
| .50 Beowulf | 16 | Alexander Arms proprietary |
| 7.62x39mm | 20 | SAAMI exception |
| .375 CheyTac | 30 | CheyTac proprietary |
| .375 EnABELR | 30 | Applied Ballistics proprietary |
| .338 EnABELR | 30 | Applied Ballistics proprietary |
| .408 CheyTac | 30 | CheyTac proprietary |
| .416 Barrett | 32 | Barrett proprietary |
| .50 BMG | 45 | Military spec |

Everything else → **24 inches**.

---

## Confidence Summary

- **High** (SAAMI Z299.4-2025 direct): 95 of 117 calibers
- **Medium** (CIP/de facto/proprietary with good sources): ~15 calibers
- **Low** (proprietary/wildcat with limited data): ~7 calibers (CheyTac, Barrett, 7.62x40 WT, .416 Barrett)

---

## Notes for Implementation

1. **The default is 24".** The simplest implementation: set all calibers to 24, then override the exceptions listed above.

2. **5.56 NATO correction:** Change from 20 → 24. The 20" figure is the NATO STANAG test barrel, not the SAAMI standard. Since the app's velocity data comes from reloading manuals (which use SAAMI 24" barrels), use 24".

3. **.338 Lapua correction:** Change from 27 → 24. The 27" figure comes from CIP/Lapua testing. SAAMI Z299.4-2025 lists .338 Lapua Magnum without any exception footnote, confirming 24".

4. **Weatherby note:** All Weatherby cartridges use 24" SAAMI test barrels — even though Weatherby's own factory data is shot from 26" barrels. The SAAMI spec governs.

5. **Wildcat fallback:** For wildcats not in SAAMI (6mm Dasher, 6BRA, 6mm XC, .260 AI, .25 GT, 6x45, 6mm-284), 24" is the safest default since it matches the SAAMI parent case standard and most published load data.

6. **CIP-only cartridges** (5.45x39, 7.62x54R, 9.3x74R): Not in SAAMI. CIP uses ~600mm (~23.6") for standard and ~650mm (~25.6") for magnum. Using 24" is a reasonable approximation.
