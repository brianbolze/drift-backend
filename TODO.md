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

- [ ] Populate cartridge.bc_g1, bc_g7, bullet_length_inches — columns added via migration but not yet extracted/populated from manufacturer pages (source: human, 2026-03-06) -- IN PROGRESS
- [ ] 6 cartridge-bullet weight mismatches (non-placeholder) — .22 WMR 30→35gr + .308 155→160gr Critical Defense + Federal 250th 30-06 150→147gr + Winchester M1 Garand 30-06 150→147gr + Winchester 308 185→180gr + Winchester 7.62 NATO 149→147gr. (source: QA report, 2026-03-06, updated 2026-03-19)
- [ ] ~40 cartridge→bullet mislinks — two root causes: ~27 cross-mfr false positives (resolver ignores mfr affinity) + ~13 same-mfr type confusion (wrong variant, e.g. ELD-X→ELD Match, BTSP→RN). Worst: 25-06 BTSP→RN has 38% BC error. 60% of cartridges have own cart-level BC mitigating solver impact, but UI shows wrong bullet metadata. See known_issues.json C10/C11/C12. (source: merged FK audits, 2026-03-25)
- [ ] Create 5 missing Hornady bullets blocking correct linkages — 178gr ELD-X (7 cartridges), 165gr CX (2+), 129gr SST (1+), 120gr CX (1+), 117gr InterLock BTSP (1+). All have BCs available on Hornady product pages. See known_issues.json C12. (source: FK audit, 2026-03-25)
- [x] ~~104 cartridges with zero velocity~~ Resolved: 95 filled/deleted via patches 019-023 (Barnes 33, Winchester 43, Nosler 12, Hornady 2, Federal 5 deleted). 9 remain: 8 Hornady ECX International (velocity intentionally unpublished) + 1 Nosler 300 Wby NoslerCustom (no factory spec). (source: QA report, 2026-03-06, resolved 2026-03-19)
- [ ] Lapua G580 100gr bullet (id=8e35868b) has wrong diameter 0.264, should be 0.308 — pipeline confused "6,5 g" weight with 6.5mm caliber. Fix via curation patch. (source: QA report C9, 2026-03-19)
- [ ] 4 MatchKing->Nosler HPBT false matches — Sierra MatchKing bullets missing at certain weights, causing cross-manufacturer false positives (source: pipeline working notes)
- [ ] Norma .300 Norma Mag 230gr Berger Hybrid Target — exact duplicate cartridge row, delete one via curation patch (source: FK audit, 2026-03-25)
- [ ] 18 rifle bullets (diam ≤ .375) missing all BC fields, excl CE/Nosler/Winchester — Sierra 4 (2026 new products, BCs not yet published), Federal 4, Lehigh 4, Lapua 3, Norma 1, Swift 1. None are match/LR-critical. (source: QA report, 2026-03-06, updated 2026-03-16)

## Pipeline Improvements

- [ ] Cartridge→bullet resolver can't match generic extracted names to DB records — "ELD-X", "Berger Hybrid", "Fusion Soft Point" etc. don't fuzzy-match "30 Cal .308 178 gr ELD® Match" or "Fusion Component Bullet, .308, 180 Grain". Blocks 100+ cartridge resolutions. Resolver needs type+weight+diameter matching, not just name similarity (source: agent, 2026-03-06)
- [ ] Bullet name normalization inconsistent — ALL CAPS (Sierra), metric prefix (Lapua), caliber in name (Hornady), trademark symbols (source: pipeline working notes)
- [ ] Cutting Edge HTML at ~200KB after reduction — worst of all manufacturers, needs per-manufacturer CSS selector hints (source: pipeline working notes)
- [ ] Sierra/Nosler/Barnes at ~70KB — 2-3x over 30KB reducer target, still works but wastes tokens (source: pipeline working notes) -- Idea: Multiple reducer strategies -- use manufacturer-based lookup table to choose strategy
- [ ] Nosler BCs only in load data section — product pages return null BC, need to scrape load data pages separately (source: pipeline working notes)
- [ ] `HttpxFetcher` creates new `AsyncClient` per request — no connection reuse/keep-alive across same-host URLs; same issue with `FirecrawlFetcher` reinstantiating `FirecrawlApp` per call (source: code review, 2026-03-06)
- [ ] Stale flagged entries persist on re-extraction — `_write_flagged` deduplicates by hash, so old warnings stick around (source: code review, 2026-03-06)
- [x] `pipeline_fetch.py` stale `reduced_cache` variable — `reduced_cache` was set in the skip-check loop but not re-assigned in the processing loop, causing all reduced JSON sidecars to write to the same file path. Fixed by adding `reduced_cache = REDUCED_DIR / f"{uhash}.json"` in the processing loop. 519 pages affected in cartridge fetch. (source: agent, 2026-03-19)

## Code / Tooling

- [ ] No `ondelete` cascade on any FK relationship — `BulletBCSource.bullet_id` especially needs `ondelete="CASCADE"` (source: code review, 2026-03-06)
- [ ] Missing indexes on FK columns used by resolver — `bullet.manufacturer_id`, `bullet.bullet_diameter_inches`, `cartridge.caliber_id`, etc. (source: code review, 2026-03-06)
- [ ] Missing composite unique constraints on natural keys — `Bullet(manufacturer_id, name, weight_grains, diameter)` and `Cartridge(manufacturer_id, name, caliber_id)` (source: code review, 2026-03-06)
- [ ] `Optic.reticle_id` non-nullable — blocks storing optics with unknown/custom reticles (source: code review, 2026-03-06)
- [ ] No controlled-vocabulary validation on `base_type`, `tip_type`, `type_tags`, `used_for` in extraction schemas — config defines valid values but Pydantic doesn't enforce them (source: code review, 2026-03-06)

## Coverage Gaps (JBM Audit 2026-03-15)

- [ ] Scrape JBM BC values as supplementary BulletBCSource — 3,520 entries with BCs, 261 Litz-measured (gold standard). Could fill 66 Drift bullets missing BCs. (source: JBM coverage audit, 2026-03-15)

## iOS Search / Filtering Support

- [ ] Add bullet entity_aliases for common abbreviations — ELDM→ELD Match, SMK→MatchKing, TMK→Tipped MatchKing, ABLR→AccuBond Long Range, VLD→VLD Target/Hunting, GMM→Gold Medal Match, etc. Currently zero bullet aliases exist. Add via curation patches so they export to `alt_names` JSON. (source: reference DB analysis, 2026-03-18)
- [ ] Curate `popularity_rank` on top ~50 factory loads and top ~50 bullets — no ranking data exists today. Needed for "recommended" sort in ammunition picker. Small enough to do manually via curation patches. (source: reference DB analysis, 2026-03-18)

## Documentation

_(empty — add items as docs drift from code)_
