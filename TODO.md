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
- [ ] 8 cartridge→bullet mislinks remain — 3 self-loading brand mislinks (1 Hornady 338 Lapua→Sierra SMK, 1 Nosler .223 55gr→Hornady SP, 1 Nosler .375 H&H→Barnes Banded Solid) + 5 Winchester non-BST cross-mfr links (.223 62gr/69gr→Hornady, 6.5 CM/PRC 140gr→Lapua 139gr, .308 169gr→Sierra). 19 Winchester BST→Nosler are expected. Also 8 weight mismatches (mostly 1gr rounding: 80.5→80, 139→140, 123→124, etc.). (source: data audit, updated 2026-04-06)
- [x] ~~4 MatchKing->Nosler HPBT false matches~~ Partially resolved — Sierra 175gr TMK and 155gr TMK created in patch 026 for BH fixes. Remaining MatchKing gaps may exist but no longer blocking active mislinks. (source: patch 026, 2026-03-26)
- [ ] Lapua G580 100gr bullet (id=8e35868b) has wrong diameter 0.264, should be 0.308 — pipeline confused "6,5 g" weight with 6.5mm caliber. Fix the existing DB record via curation patch. Regression guard added 2026-04-19 (`src/drift/pipeline/normalization.py`, step 6 of entity_resolution_review.md): grams→grains / mm→inches heuristics between EXTRACT and RESOLVE so re-extraction won't recreate it. (source: QA report C9, 2026-03-19)
- [ ] 17 rifle bullets (diam ≤ .375) missing all BC fields, excl CE/Nosler/Winchester — Sierra 4 (2026 new products, BCs not yet published), Federal 4, Lehigh 4, Lapua 3, Norma 1, Swift 1. None are match/LR-critical. Down from 33 after metadata enrichment patches 028-030. (source: QA report, 2026-03-06, updated 2026-03-29)
- [ ] C13: Sako TRG Precision .308 174gr (id=afee55ff) wrong weight (174→175gr) and wrong G1 BC (0.472→0.467). Other Sako 174gr entries (Powerhead Blade, Powerhead Blade Pro) may also be wrong. Sako SPA prevents direct verification — needs curation patch. (source: QA spot-check, 2026-04-06)
- [ ] Norma BondStrike 6.5 Creedmoor 143gr cartridge has BC enrichment opportunity — G1=0.629, G7=0.313 available on Norma site but not yet captured (source: QA spot-check, 2026-04-06)
- [ ] Investigate 37 same-diameter cartridge→bullet relinks surfaced during v6 store-commit dry-run (product_line tier vs composite_key scoring shift + alias auto-promote interaction). Forensic evidence: data/forensic/v6-resolver-regression-2026-04-22/relinks.tsv. Mixed signal — some look like improvements, some downgrades. Needs replay-with-toggle to diagnose. (source: agent, 2026-04-22)

## Pipeline Improvements

- [ ] Cartridge→bullet resolver can't match generic extracted names to DB records — "ELD-X", "Berger Hybrid", "Fusion Soft Point" etc. don't fuzzy-match "30 Cal .308 178 gr ELD® Match" or "Fusion Component Bullet, .308, 180 Grain". Blocks 100+ cartridge resolutions. Resolver needs type+weight+diameter matching, not just name similarity (source: agent, 2026-03-06)
- [ ] Bullet name normalization inconsistent — ALL CAPS (Sierra), metric prefix (Lapua), caliber in name (Hornady), trademark symbols (source: pipeline working notes)
- [ ] Cutting Edge HTML at ~200KB after reduction — worst of all manufacturers, needs per-manufacturer CSS selector hints (source: pipeline working notes)
- [ ] Sierra/Nosler/Barnes at ~70KB — 2-3x over 30KB reducer target, still works but wastes tokens (source: pipeline working notes) -- Idea: Multiple reducer strategies -- use manufacturer-based lookup table to choose strategy
- [ ] Nosler BCs only in load data section — product pages return null BC, need to scrape load data pages separately (source: pipeline working notes)
- [ ] `HttpxFetcher` creates new `AsyncClient` per request — no connection reuse/keep-alive across same-host URLs; same issue with `FirecrawlFetcher` reinstantiating `FirecrawlApp` per call (source: code review, 2026-03-06)
- [ ] Stale flagged entries persist on re-extraction — `_write_flagged` deduplicates by hash, so old warnings stick around (source: code review, 2026-03-06)
- [x] ~~Sierra parser (PR #3 of parser-first rollout)~~ Landed 2026-04-22. 240/248 parsed; 127/141 DB matches with only SKU-suffix mismatches (14 DB rows in inconsistent state). See `docs/parser_agreement_sierra.md`.
- [ ] Investigate 15 Hornady pages where the parser declines — likely missing inline product JSON, empty title, or no diameter in title. LLM handles them fine; worth understanding the shape before adding more domain parsers. Run `python scripts/parser_vs_db_report.py hornady` to list them. (source: parser rollout, 2026-04-22)
- [ ] After Sierra, pick a cartridge-heavy manufacturer (Nosler / Federal / Black Hills) for PR #4 rather than another bullet-only site — Hornady and Sierra both stress the bullet path; the cartridge path (bullet_name linkage + resolver BC-boost) should be exercised on a second manufacturer before the parser pattern is generalized further (source: rollout review, 2026-04-22)
- [x] ~~Post-Nosler: batch curation pass to land parser-derived quality wins~~ Partially addressed via patch 034 (locked the 3 known-defect rows). The larger `product_line` backfill from parser output is still open — preserved as a separate follow-up since the wins are dependent on sitemap-watch surfacing new pages for re-ingestion.
- [x] ~~Sierra 35 cal 155gr Pro-Hunter G1 BC inconsistency~~ Locked in patch 034 (DB keeps 0.182; parser's 0.176 can't create a duplicate bc_source because is_locked skips all updates).
- [x] ~~Nosler parser (PR #4 of parser-first rollout)~~ Landed 2026-04-22. 422/454 parsed; 229/231 DB matches with only 2 Nosler-page typos as diffs. See `docs/parser_agreement_nosler.md` + `docs/parser_vs_db_nosler.md`. BaseParser ABC held.
- [x] ~~Nosler page typos flagged for curation~~ Locked in patch 034 (both 416-cal 400gr and 458-cal 500gr Solid rows).
- [x] ~~Nosler cartridge → bullet_id=None on 37% (84/228)~~ Recovered 47/84 via the cartridge→bullet relaxed-diameter fallback (see next item). Remaining ~37 are bullet families not yet ingested at the needed weight — will resolve naturally when sitemap-watch surfaces them.
- [x] ~~Cartridge→bullet resolver missing diameter-filter fallback~~ Shipped 2026-04-22 via `enable_relaxed_diameter_fallback` in `ResolutionConfig`. Retroactive DB-wide dry-run: 165/686 previously-unmatched cartridges recovered (24.1%) — Hornady +61, Nosler +51, Federal +32, Winchester +15, Barnes +6, Berger unchanged. See `scripts/retroactive_resolver_recovery.py`.
- [ ] **Nosler product_line backfill (parser win unclaimed)**: 209 Nosler bullet rows in DB have `product_line=NULL` while parser extracts canonical values from the `Bullet Type` spec row ("AccuBond Long Range", "Partition", "Ballistic Tip Hunting"…). Also applies to ~150+ Sierra bullets whose `Product Family` was null in the LLM-era cache. Blocked on the batch curation generator — the right fix is probably a dedicated "promote parser-derived field where DB is null" tool, not a hand-written YAML with 350+ operations. Revisit after sitemap-watch ships. (source: rollout review + parser vs DB, 2026-04-22)
- [ ] **Nosler 270 WSM 130gr Expansion Tip BC page defect.** Nosler's page publishes `BC G1: 15` and `BC G7: 11` with missing leading zeros. Parser correctly falls through to LLM via validate_ranges (15 > 1.2). DB has 0.459/? G1 from an older extraction. Low priority — no active corruption, just a page defect to be aware of. (source: Nosler BC investigation, 2026-04-22)

## Code / Tooling

- [ ] No `ondelete` cascade on any FK relationship — `BulletBCSource.bullet_id` especially needs `ondelete="CASCADE"` (source: code review, 2026-03-06)
- [ ] Missing indexes on FK columns used by resolver — `bullet.manufacturer_id`, `bullet.bullet_diameter_inches`, `cartridge.caliber_id`, etc. (source: code review, 2026-03-06)
- [ ] Missing composite unique constraints on natural keys — `Bullet(manufacturer_id, name, weight_grains, diameter)` and `Cartridge(manufacturer_id, name, caliber_id)` (source: code review, 2026-03-06)
- [ ] `Optic.reticle_id` non-nullable — blocks storing optics with unknown/custom reticles (source: code review, 2026-03-06)
- [ ] No controlled-vocabulary validation on `base_type`, `tip_type`, `type_tags`, `used_for` in extraction schemas — config defines valid values but Pydantic doesn't enforce them (source: code review, 2026-03-06)

## Coverage Gaps (JBM Audit 2026-03-15)

- [ ] Scrape JBM BC values as supplementary BulletBCSource — 3,520 entries with BCs, 261 Litz-measured (gold standard). Could fill 66 Drift bullets missing BCs. (source: JBM coverage audit, 2026-03-15)

## Chamber / Caliber Data Gaps

- [ ] .303 British missing chamber record — caliber exists with 2 factory loads (Hornady, Federal) but no chamber, no `chamber_accepts_caliber` link, and no `caliber_platform` assignment. Users can't select it in profile creation. Fix: create chamber, link as primary, assign bolt-action platform. (source: data audit, 2026-03-30)
- [ ] .45-70 Government missing platform assignment — chamber and caliber exist but no `caliber_platform` record, so it won't appear in the platform-filtered caliber picker. Fix: add bolt-action platform link. (source: data audit, 2026-03-30)
- [ ] Add `.30-40 Krag` caliber + reassign Winchester 30-40 Krag 180gr cartridge currently resolved to `.30-06 Springfield` — curation patch post-v6 (source: agent, 2026-04-22)

## iOS Search / Filtering Support

- [ ] Add bullet entity_aliases for common abbreviations — ELDM→ELD Match, SMK→MatchKing, TMK→Tipped MatchKing, ABLR→AccuBond Long Range, VLD→VLD Target/Hunting, GMM→Gold Medal Match, etc. Currently zero bullet aliases exist. Add via curation patches so they export to `alt_names` JSON. (source: reference DB analysis, 2026-03-18)
- [ ] Curate `popularity_rank` on top ~50 factory loads and top ~50 bullets — no ranking data exists today. Needed for "recommended" sort in ammunition picker. Small enough to do manually via curation patches. (source: reference DB analysis, 2026-03-18)

## Documentation

_(empty — add items as docs drift from code)_
