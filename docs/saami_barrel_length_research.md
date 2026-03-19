# SAAMI Test Barrel Length Research Task

## Objective

Populate `caliber.saami_test_barrel_length_inches` for every caliber in the Drift ballistics database.

**Field meaning**: The standardized test barrel length (in inches) used by SAAMI (or the relevant standards body — CIP, NATO, etc.) when measuring velocity and pressure for that cartridge. This is what ballistic data in reloading manuals is referenced to. It directly affects muzzle velocity interpretation in the app.

## Research Notes

- Primary source: [SAAMI Specifications](https://saami.org/technical-information/published-standards/) — look in the free PDF spec sheets for each cartridge.
- Secondary sources: reloading manual headings, Hodgdon load data, Lyman, Sierra, Hornady manuals (most list "test barrel: XX inches" at the top of each cartridge section).
- For **CIP** cartridges (European, 7.62x54mmR, 8x57, 9.3x62, etc.), check CIP documentation or well-cited reloading sources.
- For **wildcat / proprietary cartridges** with no official spec (e.g., 6mm Dasher, 6mm GT, 6BRA), look for the de facto community standard used in published load data. Note the source.
- For **NATO cartridges** (5.56x45, 7.62x51), use the NATO standard test barrel length.
- Common test barrel lengths in SAAMI specs: 24" (most rifle), 26" (some magnums), 22" (some short-action), 20" (some military/compact), 16" (pistol-caliber / .300 BLK).

## Existing Values (Need Validation)

These are already in the DB but should be confirmed against primary sources:

| Caliber | Current Value (in) | Notes |
|---|---|---|
| .223 Remington | 24 | |
| 5.56x45mm NATO | 20 | NATO spec — verify |
| .243 Winchester | 24 | |
| 6mm ARC | 24 | |
| 6mm Creedmoor | 24 | |
| .260 Remington | 24 | |
| 6.5 Creedmoor | 24 | |
| 6.5 PRC | 24 | |
| .270 Winchester | 24 | |
| 7mm PRC | 24 | |
| 7mm Remington Magnum | 24 | |
| 7mm-08 Remington | 24 | |
| .30-06 Springfield | 24 | |
| .300 AAC Blackout | 16 | |
| .300 PRC | 24 | |
| .300 Winchester Magnum | 24 | |
| .300 Winchester Short Magnum | 24 | |
| .308 Winchester | 24 | |
| 7.62x51mm NATO | 24 | NATO spec — verify |
| .338 Lapua Magnum | 27 | CIP/Lapua spec — verify |

## Missing Values (All Calibers Without a Test Barrel Length)

For each row below, find the SAAMI (or CIP/NATO/de facto) test barrel length in inches.

### .17 / .20 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .17 HMR | .17 Hornady Magnum Rimfire, 17HMR | 0.172 | 1.058 | 26,000 | Rimfire |
| .17 Hornet | .17 Ackley Hornet | 0.172 | 1.350 | 50,000 | |
| .17 WSM | .17 Winchester Super Magnum, 17WSM | 0.172 | 1.200 | 33,000 | Rimfire |
| .204 Ruger | 204 Ruger | 0.204 | 1.850 | 57,500 | |

### .22 Caliber (0.223" dia — rimfire/small centerfire)

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| 5.45x39mm | 5.45 Soviet, 5.45x39 | 0.220 | 1.535 | — | Soviet/Russian military |
| .22 Long Rifle | .22 LR, 22LR | 0.223 | 0.613 | 24,000 | Rimfire |

### .22 Caliber (0.224" dia — centerfire)

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .22 Creedmoor | 22 CM | 0.224 | 1.920 | — | No official SAAMI spec yet |
| .22 Hornet | 22 Hornet, 5.6x35mmR | 0.224 | 1.403 | 44,000 | |
| .22 Nosler | 22 Nosler | 0.224 | 1.760 | 55,000 | |
| .22 WMR | .22 Magnum, .22 Winchester Magnum Rimfire | 0.224 | 1.055 | 24,000 | Rimfire |
| .22-250 Remington | 22-250, .22-250 Rem | 0.224 | 1.912 | 65,000 | |
| .220 Swift | 220 Swift | 0.224 | 2.205 | 62,000 | |
| .222 Remington | .222 Rem, Triple Deuce | 0.224 | 1.700 | 50,000 | |
| .222 Remington Magnum | .222 Rem Mag | 0.224 | 1.850 | 50,000 | |
| .223 WSSM | .223 Winchester Super Short Magnum | 0.224 | 1.670 | 65,000 | |
| .224 Valkyrie | 224 Valkyrie, 224 Valk | 0.224 | 1.600 | 55,000 | |

### 6mm / .243 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .240 Weatherby Magnum | .240 Wby Mag, 240 Wby | 0.243 | 2.500 | 62,500 | Weatherby proprietary |
| .243 WSSM | .243 Winchester Super Short Magnum | 0.243 | 1.670 | 65,000 | |
| 6mm BR Remington | 6BR, 6mm BR | 0.243 | 1.560 | 52,000 | |
| 6mm BRA | 6BRA, 6mm BR Ackley | 0.243 | 1.560 | — | Wildcat, no official spec |
| 6mm Dasher | 6 Dasher, Dasher | 0.243 | 1.560 | — | Wildcat; no official SAAMI spec |
| 6mm GT | 6GT | 0.243 | 1.800 | — | Wildcat; no official SAAMI spec |
| 6mm Remington | .244 Remington, 6mm Rem | 0.243 | 2.233 | 65,000 | |
| 6mm XC | 6XC | 0.243 | 1.920 | — | Wildcat |
| 6mm-284 | 6-284, 6mm/284 | 0.243 | 2.170 | — | Wildcat |
| 6x45mm | 6x45, 6mm-223 | 0.243 | 1.760 | 55,000 | Wildcat (6mm/.223 case) |

### .25 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .25 Creedmoor | 25 CM, 25 Creedmoor | 0.257 | 1.920 | 62,000 | |
| .25 GT | 25 GT | 0.257 | 1.800 | — | Wildcat |
| .25 Weatherby RPM | 25 WBY RPM, 25 RPM | 0.257 | 2.400 | 65,000 | Weatherby proprietary |
| .25-06 Remington | .25-06 Rem, 25-06 | 0.257 | 2.494 | 63,000 | |
| .257 Roberts | .257 Bob, .257 Roberts +P | 0.257 | 2.233 | 54,000 | |
| .257 Weatherby Magnum | .257 Wby Mag, 257 Wby | 0.257 | 2.549 | 62,500 | Weatherby proprietary |
| .25x47 Lapua | 25×47, .25x47L | 0.257 | 1.850 | 62,000 | |

### 6.5mm / .264 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .26 Nosler | 26 Nosler | 0.264 | 2.590 | 65,000 | |
| .260 Ackley Improved | .260 AI | 0.264 | 2.035 | — | Wildcat/AI variant |
| .264 Winchester Magnum | .264 Win Mag | 0.264 | 2.500 | 64,000 | |
| 6.5 Grendel | 6.5 Grendel, 6.5x39mm | 0.264 | 1.520 | 52,000 | |
| 6.5 SAUM | 6.5 RSAUM, 6.5mm SAUM | 0.264 | 2.015 | 65,000 | |
| 6.5 Weatherby RPM | 6.5 WBY RPM, 6.5 RPM | 0.264 | 2.570 | 65,000 | Weatherby proprietary |
| 6.5-284 Norma | 6.5-284, 6.5x284 | 0.264 | 2.170 | 58,740 | |
| 6.5x55mm Swedish | 6.5x55 Swede, 6.5x55 SE | 0.264 | 2.165 | 46,000 | CIP / older SAAMI |

### .270 / 6.8mm Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .270 WSM | .270 Winchester Short Magnum | 0.277 | 2.100 | 65,000 | |
| .270 Weatherby Magnum | .270 Wby Mag | 0.277 | 2.549 | 62,500 | Weatherby proprietary |
| .277 Fury | 6.8x51mm, .277 SIG Fury | 0.277 | 2.015 | 80,000 | SIG/military spec |
| 6.8 SPC | 6.8 SPC II, 6.8x43mm SPC | 0.277 | 1.686 | 55,000 | |
| 6.8 Western | 6.8 West | 0.277 | 2.020 | 65,000 | |

### 7mm / .284 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .28 Nosler | 28 Nosler | 0.284 | 2.590 | 65,000 | |
| .280 Ackley Improved | .280 AI, 280 Ackley | 0.284 | 2.525 | 60,000 | Now SAAMI-standardized |
| .280 Remington | 7mm Express Remington, 7mm-06 | 0.284 | 2.540 | 60,000 | |
| .284 Winchester | .284 Win | 0.284 | 2.170 | 56,000 | |
| 7mm Backcountry | 7mm BC | 0.284 | — | 80,000 | SIG/military-derived |
| 7mm SAUM | 7mm SA Ultra Mag, 7 SAUM | 0.284 | 2.015 | 65,000 | |
| 7mm WSM | 7mm Winchester Short Magnum | 0.284 | 2.100 | 65,000 | |
| 7x57mm Mauser | 7mm Mauser, .275 Rigby | 0.284 | 2.235 | 51,000 | CIP |

### .30 / .308 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .30 Nosler | 30 Nosler | 0.308 | 2.556 | 65,000 | |
| .30 Remington AR | .30 RAR | 0.308 | 1.528 | 55,000 | |
| .30-30 Winchester | .30 WCF, .30-30 Win | 0.308 | 2.039 | 42,000 | |
| .300 HAM'R | 300 HAMR | 0.308 | 1.610 | 57,500 | Wilson Combat proprietary |
| .300 Norma Magnum | .300 NM, 300 Norma | 0.308 | 2.492 | 63,800 | CIP spec |
| .300 RSAUM | .300 Remington Short Action Ultra Magnum, 300 SAUM | 0.308 | 2.015 | 65,000 | |
| .300 RUM | .300 Remington Ultra Magnum, .300 Ultra Mag | 0.308 | 2.850 | 65,000 | |
| .300 Ruger Compact Magnum | .300 RCM | 0.308 | 2.100 | 65,000 | |
| .300 Savage | 300 Savage | 0.308 | 1.871 | 46,000 | |
| .300 Weatherby Magnum | .300 Wby Mag | 0.308 | 2.825 | 62,500 | Weatherby proprietary |
| .308 Marlin Express | .308 MX | 0.308 | 2.015 | 52,000 | |
| 7.62x40mm WT | 7.62x40 Wilson Tactical | 0.308 | 1.565 | 45,000 | Wilson Combat proprietary |

### .303 / 7.62x39 / Other Soviet

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .303 British | 303 British, 7.7x56mmR | 0.311 | 2.222 | 49,000 | CIP/British spec |
| 7.62x39mm | 7.62 Soviet, x39 | 0.312 | 1.528 | 45,000 | Soviet/Russian military |
| 7.62x54mmR | 7.62x54R, 7.62 Russian | 0.312 | 2.115 | 56,600 | Russian military/CIP |

### 8mm

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .325 WSM | 8mm Remington Short Magnum | 0.323 | 2.100 | 65,000 | |
| 8x57mm Mauser | 8mm Mauser, 7.92x57mm | 0.323 | 2.244 | 37,000 | CIP (old SAAMI spec varies) |

### .338 / .340 Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .338 EnABELR | 338 EnABELR | 0.338 | — | — | Very limited data |
| .338 Federal | 338 Federal | 0.338 | 2.015 | 62,000 | |
| .338 Norma Magnum | .338 NM, 338 Norma | 0.338 | 2.492 | 63,800 | CIP spec |
| .338 RUM | .338 Remington Ultra Magnum | 0.338 | 2.760 | 63,000 | |
| .338 Winchester Magnum | .338 Win Mag | 0.338 | 2.500 | 64,000 | |
| .338-378 Weatherby Magnum | .338-378 Wby Mag | 0.338 | 2.913 | 62,500 | Weatherby proprietary |
| .340 Weatherby Magnum | .340 Wby Mag | 0.338 | 2.825 | 62,500 | Weatherby proprietary |

### .35+ Caliber

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .350 Legend | 350 Legend | 0.357 | 1.710 | 55,000 | |
| .35 Whelen | 35 Whelen | 0.358 | 2.494 | 52,000 | |
| 9.3x62mm Mauser | 9.3x62, 9.3 Mauser | 0.366 | 2.441 | 56,600 | CIP |
| 9.3x74mmR | 9.3x74R | 0.366 | 2.953 | — | CIP rimmed |

### Long-Range / Anti-Material Calibers

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .375 CheyTac | 375 CT, 9.5x77mm | 0.375 | 3.030 | — | Proprietary/wildcat |
| .375 EnABELR | 375 EnABELR | 0.375 | — | — | Very limited data |
| .375 H&H Magnum | .375 Holland & Holland Magnum | 0.375 | 2.850 | 62,400 | |
| .375 Ruger | 375 Ruger | 0.375 | 2.580 | 62,000 | |
| .408 CheyTac | 408 CT, 10.36x77mm | 0.408 | 3.047 | — | Proprietary |
| .416 Barrett | 416 Barrett | 0.416 | 3.350 | 60,000 | |
| .416 Remington Magnum | .416 Rem Mag | 0.416 | 2.850 | 62,000 | |
| .416 Rigby | 416 Rigby | 0.416 | 2.900 | 52,000 | |

### .45+ Big Bore

| Caliber | Alt Names | Bullet Dia (in) | Case Length (in) | Max PSI | Notes |
|---|---|---|---|---|---|
| .450 Bushmaster | 450 BM, 450 Bush | 0.452 | 1.700 | 38,500 | |
| .45-70 Government | .45-70 Govt | 0.458 | 2.105 | 28,000 | |
| .458 Lott | 458 Lott | 0.458 | 2.800 | 62,000 | |
| .458 SOCOM | 458 SOCOM | 0.458 | 1.575 | 35,000 | |
| .458 Winchester Magnum | .458 Win Mag | 0.458 | 2.500 | 62,000 | |
| .50 Beowulf | 12.7x42mm | 0.500 | 1.650 | 33,000 | Alexander Arms proprietary |
| .50 BMG | 12.7x99mm NATO, .50 Browning | 0.510 | 3.910 | 55,000 | |

---

## Output Format

For each caliber, return:

```
| Caliber Name | Test Barrel Length (in) | Source | Confidence | Notes |
```

- **Source**: e.g., "SAAMI ANSI/SAAMI Z299.5-2015", "CIP", "NATO STANAG", "Hodgdon 2024 Annual Manual", "community standard"
- **Confidence**: high / medium / low
- **Notes**: anything ambiguous, conflicting, or where no official spec exists

For wildcats/proprietary with no official spec, use the de facto standard from published load data if available, and mark confidence=low.
