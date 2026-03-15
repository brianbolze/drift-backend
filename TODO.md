# TODO

Lightweight tech debt and engineering improvement tracker. Agents and humans append items here during normal work. For features and large work items, use Linear.

## How to Use

**Adding items**: Append to the appropriate section. Include a one-line description, optional context, and who/what discovered it (agent session, QA report, code review, etc.).

**Format**:
```
- [ ] Short description — context if needed (source: agent/human, date)
```

**Prioritizing**: Items stay unchecked until someone picks them up. Check the box when done or delete the line. Periodically review and prune stale items.

**Graduating to Linear**: If an item grows beyond a quick fix (>1 hour), move it to Linear and delete it from here.

---

## Data Quality

- [ ] Populate cartridge.bc_g1, bc_g7, bullet_length_inches — columns added via migration but not yet extracted/populated from manufacturer pages (source: human, 2026-03-06)

- [ ] 67 cartridge-bullet weight mismatches (30% of cartridges) — likely wrong bullet_id linkages from pre-abbreviation-expansion pipeline runs (source: QA report, 2026-03-06)
- [ ] 99 existing cartridges with wrong bullet_id — re-run pipeline-store-commit after ensuring correct bullets exist in DB (source: pipeline working notes)
- [ ] 7 Hornady International cartridges with zero velocity — pages don't publish MV, need supplementary data source (source: QA report, 2026-03-06)
- [ ] 4 MatchKing->Nosler HPBT false matches — Sierra MatchKing bullets missing at certain weights, causing cross-manufacturer false positives (source: pipeline working notes)
- [ ] 22 bullets missing BC data entirely — no BulletBCSource records (source: QA report, 2026-03-06)
- [ ] Hornady .300 WM Custom International metric conversion — barrel=9.45" (from 24cm), MV=2961 (from 902 m/s). Fix via curation patch. Audit remaining Hornady International cartridges for same pattern. (source: QA report, 2026-03-06)
- [ ] Sierra 22 CAL 60gr TMK (f4facb6b) — bad record with diam=0.220 still in DB as of 2026-03-15. Previously marked resolved but re-confirmed present. Needs deletion via curation patch. (source: QA report, 2026-03-15)
- [ ] Sierra 6.5mm 107gr TMK (adb2ba7f) misnamed as "6MM" — diameter and BCs correct for 6.5mm, only display name wrong. Fix name to "6.5MM 107 GR Tipped MatchKing (TMK)" via curation patch. (source: QA report, 2026-03-15)
- [ ] 12 Berger loaded ammunition product pages stored as bullet records — duplicates component bullet data (e.g., "300 Winchester Magnum 185 Grain Classic Hunter Rifle Ammunition"). Clean up via curation delete or pipeline filter. (source: QA report, 2026-03-14)
- [ ] Hornady .308 220gr RN Custom International — barrel=9.45" (from "24cm" mislabel), should be 24". Same Hornady Intl metric pattern as C5. Fix via curation patch. (source: QA report, 2026-03-06)
- [ ] 5 Federal "Custom Rifle Ammo" placeholder cartridges — zero weight, zero MV, no barrel length. Useless records, delete via curation patch. (source: QA report, 2026-03-09)
- [ ] Speer .264 140gr Impact (c22dc78f) wrong source_url — points to dead DeepCurl handgun page. Correct: speer.com/bullets/rifle-bullets/impact-bullet/19-TB264H1.html (source: QA report, 2026-03-09)
- [ ] Hornady 8x57 JS 195gr SP Custom International — barrel=9.45" (from 24cm metric), MV=2568 (likely metric conversion). Third instance of Hornady International metric bug (see C5, C7). (source: QA report, 2026-03-09)

## Pipeline Improvements

- [ ] Cartridge→bullet resolver can't match generic extracted names to DB records — "ELD-X", "Berger Hybrid", "Fusion Soft Point" etc. don't fuzzy-match "30 Cal .308 178 gr ELD® Match" or "Fusion Component Bullet, .308, 180 Grain". Blocks 100+ cartridge resolutions. Resolver needs type+weight+diameter matching, not just name similarity (source: agent, 2026-03-06)
- [ ] Bullet name normalization inconsistent — ALL CAPS (Sierra), metric prefix (Lapua), caliber in name (Hornady), trademark symbols (source: pipeline working notes)
- [ ] Cutting Edge HTML at ~200KB after reduction — worst of all manufacturers, needs per-manufacturer CSS selector hints (source: pipeline working notes)
- [ ] Sierra/Nosler/Barnes at ~70KB — 2-3x over 30KB reducer target, still works but wastes tokens (source: pipeline working notes) -- Idea: Multiple reducer strategies -- use manufacturer-based lookup table to choose strategy
- [ ] Nosler BCs only in load data section — product pages return null BC, need to scrape load data pages separately (source: pipeline working notes)
- [ ] `HttpxFetcher` creates new `AsyncClient` per request — no connection reuse/keep-alive across same-host URLs; same issue with `FirecrawlFetcher` reinstantiating `FirecrawlApp` per call (source: code review, 2026-03-06)
- [ ] Stale flagged entries persist on re-extraction — `_write_flagged` deduplicates by hash, so old warnings stick around (source: code review, 2026-03-06)

## Code / Tooling

- [ ] No `ondelete` cascade on any FK relationship — `BulletBCSource.bullet_id` especially needs `ondelete="CASCADE"` (source: code review, 2026-03-06)
- [ ] Missing indexes on FK columns used by resolver — `bullet.manufacturer_id`, `bullet.bullet_diameter_inches`, `cartridge.caliber_id`, etc. (source: code review, 2026-03-06)
- [ ] Missing composite unique constraints on natural keys — `Bullet(manufacturer_id, name, weight_grains, diameter)` and `Cartridge(manufacturer_id, name, caliber_id)` (source: code review, 2026-03-06)
- [ ] `Optic.reticle_id` non-nullable — blocks storing optics with unknown/custom reticles (source: code review, 2026-03-06)
- [ ] No controlled-vocabulary validation on `base_type`, `tip_type`, `type_tags`, `used_for` in extraction schemas — config defines valid values but Pydantic doesn't enforce them (source: code review, 2026-03-06)

## Coverage Gaps (JBM Audit 2026-03-15)

- [ ] Winchester missing entirely — 185 rifle bullets in JBM, 0 in Drift. Major ammo + component bullet maker. (source: JBM coverage audit, 2026-03-15)
- [ ] Swift missing entirely — 55 rifle bullets in JBM (A-Frame, Scirocco II). Blocks ~182 flagged cartridge resolutions. (source: JBM coverage audit, 2026-03-15)
- [ ] Berger 53 rifle bullet gaps — 19 in .224, 14 in .308. Core competition bullets (Match/VLD/Hybrid). (source: JBM coverage audit, 2026-03-15)
- [ ] Scrape JBM BC values as supplementary BulletBCSource — 3,520 entries with BCs, 261 Litz-measured (gold standard). Could fill 66 Drift bullets missing BCs. (source: JBM coverage audit, 2026-03-15)
- [ ] Sako missing entirely — 63 rifle bullets in JBM. Popular European brand. (source: JBM coverage audit, 2026-03-15)
- [ ] Norma missing entirely — 38 rifle bullets in JBM despite being in manifest. Pipeline may not have stored. (source: JBM coverage audit, 2026-03-15)

## Documentation

_(empty — add items as docs drift from code)_
