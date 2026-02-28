# Caliber & Chamber Data Curation Task

## Context

We're building a precision ballistics app called **Drift**. The backend maintains a curated reference database of calibers, chambers, and their relationships. This data is **editorially curated** (not scraped) and serves as the backbone for profile creation, search, and contextual ranking in the app.

We currently have **25 calibers** and **26 chambers** covering the most popular long-range and tactical cartridges. We need to expand this to a **comprehensive list** — covering hunting, competition, tactical, classic/legacy, magnum, and modern niche cartridges that a user of a ballistics calculator might reasonably own or encounter.

## Your Task

Produce three JSON files with the data described below. Prioritize accuracy — if you're unsure about a value, leave it `null` rather than guess.

---

## 1. `calibers.json` — New Calibers to Add

We already have these 25 calibers in the database. **Do not include them** — only provide new ones:

```
6.5 Creedmoor, .308 Winchester, 6mm Dasher, 6mm GT, 6mm Creedmoor,
.223 Remington, 5.56x45mm NATO, .300 Winchester Magnum, .300 PRC,
6.5 PRC, 7mm PRC, .338 Lapua Magnum, .270 Winchester,
.30-06 Springfield, 7mm Remington Magnum, .260 Remington,
7.62x51mm NATO, .243 Winchester, .300 Winchester Short Magnum,
7mm-08 Remington, 6.5x55mm Swedish, .300 AAC Blackout,
.338 Winchester Magnum, 6mm ARC, 6.5-284 Norma
```

Each new caliber should be a JSON object with these fields:

```jsonc
{
  // REQUIRED
  "name": "string — canonical name (e.g., '.280 Ackley Improved')",
  "bullet_diameter_inches": 0.284,  // float, measured diameter

  // STRONGLY DESIRED — provide if known
  "case_length_inches": 2.525,      // float, SAAMI spec case length
  "coal_inches": 3.330,             // float, max cartridge overall length
  "max_pressure_psi": 58000,        // integer, SAAMI MAP or CIP equivalent
  "rim_type": "rimless",            // one of: "rimless", "belted", "rebated", "rimmed", "semi-rimmed"
  "action_length": "long",          // one of: "short", "long", "magnum", "mini"
  "year_introduced": 2007,          // integer, year first commercially available
  "alt_names": ["abbreviation1", "abbreviation2"],
      // Common abbreviations and alternate names that a user might type
      // when searching. e.g., for ".280 Ackley Improved": [".280 AI", "280 AI"]
  "description": "string — 1-2 sentence description focusing on typical use case and key characteristics",

  // OPTIONAL — include if readily known
  "is_common_lr": true,             // boolean — is this commonly used for long-range shooting (500+ yards)?
  "parent_caliber_name": ".280 Remington",
      // If this is a derivative (wildcat, improved, necked-down variant),
      // name the parent caliber. Use the canonical name as it would appear
      // in the "name" field of the parent. null if not a derivative.

  // LEAVE NULL — we will populate these later
  "saami_designation": null,
  "notes": null,
  "source_url": null,
  "popularity_rank": null
}
```

### Categories to Cover

Aim for **80–120 new calibers** across these categories. You don't need to be exhaustive for every obscure wildcat, but do cover anything a reasonable owner of a ballistics calculator might use:

**Centerfire Rifle — Common Hunting & Sporting:**
.204 Ruger, .22-250 Remington, .220 Swift, .222 Remington, .22 Hornet, .25-06 Remington, .257 Weatherby Magnum, .257 Roberts, .264 Winchester Magnum, .270 Weatherby Magnum, .270 WSM, .280 Remington, .280 Ackley Improved, .30-30 Winchester, .30-40 Krag, .300 Savage, .300 Weatherby Magnum, .300 Ruger Compact Magnum, .303 British, .32 Winchester Special, .338 Federal, .338 Ruger Compact Magnum, .35 Remington, .35 Whelen, .350 Legend, .375 H&H Magnum, .375 Ruger, .375 CheyTac, .416 Rigby, .416 Remington Magnum, .45-70 Government, .450 Bushmaster, .450 Marlin, .458 Winchester Magnum, .458 Lott, .470 Nitro Express, .500 Nitro Express, etc.

**Competition & Precision (not already included):**
6mm BR Norma, 6XC, .22 Creedmoor, .224 Valkyrie, 6.5 Grendel, .22 Nosler, .28 Nosler, .30 Nosler, .33 Nosler, .26 Nosler, .300 Norma Magnum, .338 Norma Magnum, 6.5 SAUM, 7mm SAUM, .300 SAUM, .300 RUM, 7mm RUM, etc.

**Tactical / AR-Platform:**
6.8 SPC, .458 SOCOM, .50 Beowulf, .277 SIG Fury (6.8x51mm), etc.

**Classic / Military Surplus:**
7x57mm Mauser, 8x57mm Mauser (8mm Mauser), 7.62x54R, 7.5x55 Swiss, 6.5x52 Carcano, .303 British, 7.65x53 Argentine, .30-40 Krag, etc.

**Rimfire (if applicable to a ballistics calculator):**
.22 LR, .22 WMR, .17 HMR, .17 WSM — use your judgment on whether these belong.

**Large / ELR:**
.408 CheyTac, .375 CheyTac, .50 BMG, .416 Barrett, .338 Lapua Improved, etc.

This list is a starting point — use your domain expertise to add anything I've missed that belongs. Similarly, if something in my list is too obscure to warrant inclusion, skip it.

---

## 2. `chambers.json` — New Chambers to Add

We already have these 26 chambers. **Do not include them**:

```
.223 Remington, .223 Wylde, .243 Winchester, .260 Remington,
.270 Winchester, .30-06 Springfield, .300 AAC Blackout, .300 PRC,
.300 Winchester Magnum, .300 Winchester Short Magnum, .308 Winchester,
.338 Lapua Magnum, .338 Winchester Magnum, 5.56 NATO, 6.5 Creedmoor,
6.5 PRC, 6.5-284 Norma, 6.5x55mm Swedish, 6mm ARC, 6mm Creedmoor,
6mm Dasher, 6mm GT, 7.62x51mm NATO, 7mm PRC, 7mm Remington Magnum,
7mm-08 Remington
```

Most calibers have a 1:1 chamber of the same name. You only need to explicitly create a chamber entry when:

1. **Every new caliber needs a corresponding chamber** (even if the name is identical — just include it).
2. **A chamber accepts multiple calibers** — like `.223 Wylde` accepts both `.223 Rem` and `5.56 NATO`. These are the interesting cases.

Each chamber object:

```jsonc
{
  "name": "string — chamber name",
  "alt_names": ["string"],     // alternate names, if any. null if none.
  "notes": "string or null",   // only if there's something worth noting
                               // (e.g., hybrid chambers, safety considerations)
  "source": "string or null"   // e.g., "SAAMI", "CIP", "Industry standard"
}
```

---

## 3. `chamber_accepts_caliber.json` — Chamber-to-Caliber Mappings

This defines which calibers can be safely fired in which chambers. Every chamber must have at least one mapping.

```jsonc
{
  "chamber_name": ".223 Wylde",
  "caliber_name": ".223 Remington",
  "is_primary": true    // true = this is the native/designed caliber for this chamber
}
```

**Important concepts:**
- Most chambers accept exactly one caliber: `is_primary: true`.
- Some chambers accept multiple calibers (e.g., `.223 Wylde` accepts both `.223 Rem` [primary] and `5.56 NATO` [non-primary]).
- The `.308 Winchester` chamber can fire `7.62x51mm NATO` (and vice versa, the `7.62x51mm NATO` chamber can fire `.308 Win` — though with caveats about pressure).
- For multi-caliber chambers, one caliber should be `is_primary: true` and the others `is_primary: false`.

We already have mappings for the existing 26 chambers. Only provide mappings for the **new** chambers/calibers you're adding.

---

## Quality Guidelines

1. **Accuracy over completeness.** If you're unsure about a dimension, leave it `null`. Wrong data is worse than missing data.
2. **Canonical names matter.** Use the most widely recognized name as `name`. Put abbreviations and variants in `alt_names`. Follow conventions:
   - Use periods for imperial (`.308 Winchester`, `.30-06 Springfield`)
   - No periods for metric (`6.5 Creedmoor`, `7x57mm Mauser`)
   - Include "mm" for metric bore-diameter cartridges
3. **alt_names should be search-friendly.** Think about what a user would type: `.280 AI`, `6.5 CM`, `.300 WM`, `30-06`, `.45-70`, etc.
4. **is_common_lr** means the cartridge is commonly used for precision shooting at 500+ yards. Most hunting cartridges are `false`. Most magnums used for ELR are `true`.
5. **Rim types:** `rimless`, `belted`, `rebated`, `rimmed`, `semi-rimmed`.
6. **Action lengths:** `short` (~2.8" OAL), `long` (~3.34" OAL), `magnum` (~3.6"+ OAL), `mini` (~2.26" OAL). If a cartridge doesn't fit neatly, use the closest match.
7. **parent_caliber_name** traces the lineage. `.280 AI` → `.280 Remington`. `6.5 Creedmoor` → `.30 TC` (or null — only use when the relationship is well-known and clear).
8. **Descriptions** should be concise and opinionated — this is editorial content, not an encyclopedia. Focus on what makes the cartridge notable and who uses it.

## Output Format

Return three valid JSON arrays — one per file. No markdown wrapping, no commentary mixed into the data. Use `null` (not empty strings) for unknown values.
