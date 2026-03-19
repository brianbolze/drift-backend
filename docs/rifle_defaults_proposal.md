# Rifle Defaults Seed Data — Proposal

*2026-03-19*

## Problem

The profile creation flow shows 2-5 options for barrel length and twist rate, with supporting text like "typical for {caliber} {platform}." Today these are hardcoded on the iOS side with no structured backing data. Trust risk: if defaults are wrong, we sound like we don't know what we're doing.

## Solution

Add structured default specs to `CaliberPlatform` (the existing junction table), with a confidence tier that tells the iOS app how aggressively to present them.

### New Columns on `caliber_platform`

| Column | Type | Purpose |
|---|---|---|
| `typical_barrel_lengths_inches` | JSON `[float]` | Options to show (e.g., `[20, 22, 24]`) |
| `default_barrel_length_inches` | Float, nullable | Which to preselect (`null` = don't preselect) |
| `typical_twist_rates` | JSON `[str]` | Options to show (e.g., `["1:7", "1:8", "1:9"]`) |
| `default_twist_rate` | String, nullable | Which to preselect (`null` = don't preselect) |
| `spec_confidence` | `high` / `medium` / `low` | Controls iOS UX behavior |

### Confidence Tiers → iOS Behavior

| `spec_confidence` | Preselect default? | Show "typical for X" text? | Show options? |
|---|---|---|---|
| `high` | Yes | Yes | Yes |
| `medium` | No | No | Yes |
| `low` / null | No | No | No (manual entry only) |

### Data Population

**Tier 1 — High confidence (~30 combos, curation patch).**
Hand-curated from established industry norms. Covers the top caliber-platform pairs that represent ~90% of user profiles.

Examples:

| Platform | Caliber | Barrel Options | Default | Twist Options | Default |
|---|---|---|---|---|---|
| Bolt | 6.5 Creedmoor | 22, 24 | 24 | 1:8 | 1:8 |
| Bolt | .308 Winchester | 20, 22, 24 | 22 | 1:10 | 1:10 |
| Bolt | .300 Win Mag | 24, 26 | 26 | 1:10 | 1:10 |
| Bolt | 7mm PRC | 22, 24 | 24 | 1:8, 1:8.5 | 1:8 |
| Bolt | .338 Lapua Mag | 26, 27 | 26 | 1:9.3, 1:10 | 1:10 |
| Bolt | .270 Winchester | 22, 24 | 22 | 1:10 | 1:10 |
| Bolt | .30-06 Springfield | 22, 24 | 22 | 1:10 | 1:10 |
| Bolt | 6.5 PRC | 24, 26 | 24 | 1:8 | 1:8 |
| Bolt | 6mm Creedmoor | 22, 24, 26 | 24 | 1:7.5, 1:8 | 1:8 |
| Bolt | 6mm GT | 22, 24 | 24 | 1:7.5, 1:8 | 1:8 |
| Bolt | 6mm Dasher | 24, 26 | 26 | 1:7.5, 1:8 | 1:8 |
| Bolt | .223 Remington | 20, 24 | 24 | 1:7, 1:8, 1:9 | 1:8 |
| Bolt | 7mm Rem Mag | 24, 26 | 26 | 1:9, 1:9.5 | 1:9.5 |
| Bolt | .300 PRC | 24, 26 | 26 | 1:9, 1:10 | 1:10 |
| AR-15 | .223 Remington | 14.5, 16, 18, 20 | 16 | 1:7, 1:8, 1:9 | 1:8 |
| AR-15 | 5.56x45mm NATO | 14.5, 16, 18, 20 | 16 | 1:7, 1:8 | 1:7 |
| AR-15 | .300 AAC Blackout | 8, 10.3, 16 | 10.3 | 1:7, 1:8 | 1:7 |
| AR-15 | 6mm ARC | 18, 20, 24 | 18 | 1:7.5 | 1:7.5 |
| AR-15 | 6.5 Grendel | 18, 20, 24 | 20 | 1:8 | 1:8 |
| AR-10 | .308 Winchester | 16, 18, 20 | 20 | 1:10, 1:11 | 1:10 |
| AR-10 | 6.5 Creedmoor | 18, 20, 22 | 22 | 1:8 | 1:8 |
| AR-10 | 7.62x51mm NATO | 16, 18, 20 | 20 | 1:10, 1:11, 1:12 | 1:11 |
| AR-10 | .243 Winchester | 20, 22, 24 | 22 | 1:8, 1:10 | 1:8 |
| AR-10 | 6mm Creedmoor | 20, 22, 24 | 22 | 1:7.5, 1:8 | 1:8 |
| AR-10 | .260 Remington | 20, 22, 24 | 22 | 1:8 | 1:8 |

**Tier 2 — Medium confidence (~30-40 combos).** Less common calibers where we can provide reasonable options but shouldn't claim "typical." Populated via LLM-assisted research + human review, or expanded curation patches as needed.

**Tier 3 — Low / no data (remainder).** Obscure calibers — `spec_confidence` stays null. iOS shows manual-entry-only UX.

### Implementation Plan

1. Alembic migration adding columns to `caliber_platform`
2. Curation patch for Tier 1 data (~30 rows)
3. Update production DB export (columns should pass through automatically)
4. iOS reads `spec_confidence` + default fields to drive the rifle details step

### Future: Barrel-Length MV Adjustment

With `default_barrel_length_inches` alongside `saami_test_barrel_length_inches` (on Caliber) and `test_barrel_length_inches` (on Cartridge), the iOS app could eventually show:

> "Published velocities are tested in a 24" barrel. Your 20" barrel will typically see ~80-100 fps less."

Would require a `fps_per_inch_delta` column on Caliber (roughly 25-50 fps/inch for most cartridges, varies by case capacity). Separate effort.
