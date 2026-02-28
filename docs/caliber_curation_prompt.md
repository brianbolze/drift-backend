# Caliber & Chamber Data Curation Task

## Context

We're building a precision ballistics app called **Drift**. The backend maintains a curated reference database of calibers, chambers, and their relationships. This data is **editorially curated** (not scraped) and serves as the backbone for profile creation, search, and contextual ranking in the app.

We currently have **25 calibers** and **26 chambers** covering the most popular long-range and tactical cartridges. We need to expand this to a **comprehensive list** — covering hunting, competition, tactical, classic/legacy, magnum, and modern niche cartridges that a user of a ballistics calculator might reasonably own or encounter.

## Your Task

Produce four JSON files with the data described below. Prioritize accuracy — if you're unsure about a value, leave it `null` rather than guess.

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
  "year_introduced": 2007,          // integer, year first commercially available or standardized
  "alt_names": ["abbreviation1", "abbreviation2"],
      // Common abbreviations, nicknames, and alternate names that a user
      // might type when searching for this caliber in-app.
  "description": "string — 1-2 sentence description focusing on typical use case and key characteristics",

  // OPTIONAL — include if readily known
  "is_common_lr": true,             // boolean — is this commonly used for long-range shooting (500+ yards)?
  "parent_caliber_name": ".280 Remington",
      // If this is a derivative (wildcat, improved, necked-down variant),
      // name the parent caliber. Use the canonical name as it would appear
      // in the "name" field of the parent. null if not a derivative or
      // if the lineage isn't clear-cut.

  // LEAVE NULL — we will populate these later
  "saami_designation": null,
  "notes": null,
  "source_url": null,
  "popularity_rank": null
}
```

### Scope

Aim for **80–120 new calibers**. Use your judgment on what belongs — the guiding question is: **"Would a reasonable owner of a ballistics calculator ever set up a profile for this cartridge?"** That includes everything from common hunting rounds to precision competition wildcats to military surplus to ELR. Rimfire is your call. Obscure proprietary or wildcat cartridges that have never been SAAMI/CIP standardized and don't have meaningful commercial availability can be skipped.

### Naming Conventions (for consistency with existing data)

- Use periods for imperial bore designations: `.308 Winchester`, `.30-06 Springfield`
- No periods for metric bore designations: `6.5 Creedmoor`, `7x57mm Mauser`
- Include "mm" where conventional for metric cartridges
- Put the most widely recognized name in `name`; abbreviations and variants go in `alt_names`

### Enum Constraints

These fields must use one of the listed values:

- **`rim_type`**: `"rimless"`, `"belted"`, `"rebated"`, `"rimmed"`, `"semi-rimmed"`
- **`action_length`**: `"short"`, `"long"`, `"magnum"`, `"mini"`

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

**Every new caliber needs a corresponding chamber entry.** Most are 1:1 with the same name. The interesting cases are chambers that differ from the caliber name or accept multiple calibers — use your expertise here.

Each chamber object:

```jsonc
{
  "name": "string — chamber name",
  "alt_names": ["string"],     // alternate names, if any. null if none.
  "notes": "string or null",   // only for genuinely useful context
                               // (e.g., hybrid chambers, safety/interchangeability notes)
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

For chambers that accept multiple calibers, include one entry per accepted caliber. One should be `is_primary: true` (the native/designed cartridge) and the others `is_primary: false`.

We already have mappings for the existing 26 chambers. Only provide mappings for the **new** chambers/calibers you're adding.

---

## 4. `caliber_platforms.json` — Platform Compatibility Mappings

We track which calibers are commercially available on which **firearm platforms**. There are currently three platforms in our database:

| Platform     | `short_name` | Notes |
|-------------|------------|-------------|
| Bolt Action | `bolt`     | Most flexible platform. |
| AR-15       | `ar15`     | AR-15 pattern rifles. |
| AR-10       | `ar10`     | AR-10 / SR-25 / LR-308 pattern. |

For each new caliber, provide mappings to the platforms it's commercially available on. **A row existing means "this caliber is available on this platform."** Not every caliber belongs on every platform — only include mappings that reflect real commercial availability.

```jsonc
{
  "caliber_name": ".280 Ackley Improved",
  "platform": "bolt",       // one of: "bolt", "ar15", "ar10"
  "rank": null,              // integer or null — popularity rank within this platform
                             // (1 = most popular on that platform). null is fine if
                             // you're not confident in relative ranking.
  "notes": "string or null"  // only if there's a meaningful caveat
}
```

We already have platform mappings for all 25 existing calibers. Only provide mappings for **new** calibers.

---

## Quality Guidelines

1. **Accuracy over completeness.** If you're unsure about a value, leave it `null`. Wrong data is worse than missing data.
2. **`alt_names` should be search-friendly.** Think about what a user would actually type into a search bar when looking for this cartridge.
3. **Descriptions** should be concise and opinionated — this is editorial content, not an encyclopedia. Focus on what makes the cartridge notable and who uses it.
4. **`parent_caliber_name`** — only set when the parent-child relationship is well-known. Use the exact canonical `name` of the parent as it appears (or would appear) in the calibers list.

## Output Format

Return four valid JSON arrays — one per file:
1. `calibers.json`
2. `chambers.json`
3. `chamber_accepts_caliber.json`
4. `caliber_platforms.json`

No markdown wrapping, no commentary mixed into the data. Use `null` (not empty strings) for unknown values.
