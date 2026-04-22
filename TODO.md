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

- [ ] **Data-pollution sweep across all manufacturers.** Patch 036 deleted 9 Berger "cartridge-named bullet" rows (names containing "Ammunition", "Magnum", or a full caliber prefix like "338 Lapua Magnum 300 Grain …"). The same LLM misclassification almost certainly exists for other manufacturers (Nosler Trophy Grade / Hornady factory ammo / Winchester Super-X / Federal Gold Medal pages). Query shape: `bullet.name LIKE '%Ammunition%'` OR `LIKE '% Magnum %'` OR `starts_with_caliber_pattern` — triage the hits per manufacturer, verify they're misclassifications (vs. legitimate names that happen to contain those words), patch the carts that reference them, then delete. Each cycle will likely need `--skip-pk-check` until the PK-removal allowlist mechanism lands. (source: v6 resolver regression investigation, 2026-04-22)
- [ ] Populate cartridge.bc_g1, bc_g7, bullet_length_inches — columns added via migration but not yet extracted/populated from manufacturer pages (source: human, 2026-03-06) -- IN PROGRESS
- [ ] 8 cartridge→bullet mislinks remain — 3 self-loading brand mislinks (1 Hornady 338 Lapua→Sierra SMK, 1 Nosler .223 55gr→Hornady SP, 1 Nosler .375 H&H→Barnes Banded Solid) + 5 Winchester non-BST cross-mfr links (.223 62gr/69gr→Hornady, 6.5 CM/PRC 140gr→Lapua 139gr, .308 169gr→Sierra). 19 Winchester BST→Nosler are expected. Also 8 weight mismatches (mostly 1gr rounding: 80.5→80, 139→140, 123→124, etc.). (source: data audit, updated 2026-04-06)
- [x] ~~4 MatchKing->Nosler HPBT false matches~~ Partially resolved — Sierra 175gr TMK and 155gr TMK created in patch 026 for BH fixes. Remaining MatchKing gaps may exist but no longer blocking active mislinks. (source: patch 026, 2026-03-26)
- [ ] Lapua G580 100gr bullet (id=8e35868b) has wrong diameter 0.264, should be 0.308 — pipeline confused "6,5 g" weight with 6.5mm caliber. Fix the existing DB record via curation patch. Regression guard added 2026-04-19 (`src/drift/pipeline/normalization.py`, step 6 of entity_resolution_review.md): grams→grains / mm→inches heuristics between EXTRACT and RESOLVE so re-extraction won't recreate it. (source: QA report C9, 2026-03-19)
- [ ] 17 rifle bullets (diam ≤ .375) missing all BC fields, excl CE/Nosler/Winchester — Sierra 4 (2026 new products, BCs not yet published), Federal 4, Lehigh 4, Lapua 3, Norma 1, Swift 1. None are match/LR-critical. Down from 33 after metadata enrichment patches 028-030. (source: QA report, 2026-03-06, updated 2026-03-29)
- [ ] C13: Sako TRG Precision .308 174gr (id=afee55ff) wrong weight (174→175gr) and wrong G1 BC (0.472→0.467). Other Sako 174gr entries (Powerhead Blade, Powerhead Blade Pro) may also be wrong. Sako SPA prevents direct verification — needs curation patch. (source: QA spot-check, 2026-04-06)
- [ ] Norma BondStrike 6.5 Creedmoor 143gr cartridge has BC enrichment opportunity — G1=0.629, G7=0.313 available on Norma site but not yet captured (source: QA spot-check, 2026-04-06)
- [x] ~~BLOCKER-v6: Product-line tier scoring regression in `match_bullet`~~ Diagnosed + fixed 2026-04-22. Root cause was two bugs, not one: (1) `match_cartridge` composite_key/fuzzy cross-matched sibling products with different SKUs (e.g. Hornady SST TIPPED SKU 81509 ↔ InterLock AW SKU 81489, both 6.5 CM 129gr); the store-commit then overwrote the existing cart's bullet_id with the new extraction's bullet — accounted for 18/25 "downgrades." (2) In `match_bullet` from the cartridge→bullet path, the cross-brand search produced tied composite_key scores (Hornady BTHP 0.95 vs Sierra HPBT 0.95 via BTHP↔HPBT expansion) and the dedup picked whichever came first — accounted for 3 more. Fixes: **Fix 1** SKU-mismatch disqualifier in `match_cartridge` candidate pool; **Fix 2** two-pass cart→bullet resolution (narrow same-mfr first at `cart_bullet_mfr_preferred_min_confidence=0.9`, fall back to cross-brand — preserves Federal-loaded Sierra MatchKing case). 7 new regression tests. Diagnostic: 21/25 V5-better cases recover against forensic DB; 11/12 V6-better cases preserve their v6 pick (the one "regression" is an identical-name Winchester↔Federal FMJ swap — same visible bullet). Remaining 4 non-PK-breaker downgrades (cases 6, 10, 23, 26) are separate issues: cases 6/10 LLM extraction dropped the variant suffix ("InterLock" vs "InterLock BTSP/RN"), case 23 is within-Barnes-TSX variant ambiguity needing caliber-aware scoring, case 26 is the "Berger 338 LM 300gr Lapua Scenar" data-pollution bullet that needs a curation patch. (source: agent, 2026-04-22)

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
- [ ] **Lock the 3 remaining v6 resolver tech-debt carts** (cases 6/10/23). Every `pipeline-store-commit` silently re-breaks these cart bullet_ids; they only survive because patch 027 re-asserts the correct bullet_id on the next `make curate-commit`. Make it structural: a small curation patch that sets `is_locked=true` on carts `86685620` (Hornady 25-06 117gr InterLock BTSP AW), `a65f25b2` (Hornady 30-30 150gr RN Interlock AW), and `0761bf5c` (Federal Gold Medal Barnes TSX 308 150gr). Reuses the patch 034/036 locking pattern. ~30 min. Separate from the deeper resolver fixes below. (source: v6 publish, 2026-04-22)
- [ ] Cartridge→bullet resolver: variant-suffix disambiguation within a product line. Cases 6 and 10 of the v6 regression (Hornady 25-06 117gr InterLock BTSP vs RN, 30-30 150gr InterLock RN vs SP) tied on composite_key within the same manufacturer because the LLM extraction dropped the BTSP/RN/SP suffix and bullet_name was just "InterLock". Either harden extraction to preserve variant suffixes, or augment the bullet stub with tokens from the cartridge name before scoring. Non-PK-breaking but still a silent wrong pick. (source: v6 resolver regression investigation, 2026-04-22)
- [ ] Cartridge→bullet resolver: within-brand variant ambiguity when bullet name contains a conflicting caliber marker. Case 23 (Federal Gold Medal Barnes TSX 308 150gr) picked Barnes "30-30 WIN TSX 150 GR FN FB" over the correct "30 CAL TSX BT 150 GR" — both are 0.308" Barnes TSX bullets, composite_key tied. The "30-30 WIN" vs "30 CAL" marker in the bullet name should penalize when the cartridge caliber is .308 Win. Needs caliber-token-in-bullet-name scoring. (source: v6 resolver regression, 2026-04-22)
- [ ] **Resolver ambiguity gate.** `MatchResult.is_ambiguous` is computed (runner-up within 0.2 of the top) but never gates bullet FK assignment. If it did — `flagged_low_confidence` instead of silent pick — cases 6/10/23 would have surfaced before v6 shipped. Product call first: trades more flagged carts for fewer silent wrong picks. Probably a knob: `ambiguity_blocks_assignment: bool = True` + tighter gap threshold (~0.03). (source: v6 resolver regression, 2026-04-22)

## Code / Tooling

- [ ] **Replace `--skip-pk-check` with a surgical allowlist in `scripts/publish_db.py`.** v6 publish bypassed the whole PK safety net to land 9 intentional Berger data-pollution bullet deletes (patch 036). The next curation-driven removal round will hit the same wall. Add an `--allow-removed-pks bullet:<id>,<id>,... cartridge:<id>,...` flag so curator-verified removals pass through while accidents still fail loudly. Current bypass is documented in the v6 commit message (commit c9aa2a5). (source: v6 publish, 2026-04-22)
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
- [x] ~~Delete the "338 Lapua Magnum 300gr Lapua Scenar" Berger bullet~~ Shipped 2026-04-22 in patch 036 alongside 8 other Berger data-pollution bullets. Cart now correctly resolves to Lapua "19,4 g / 300 gr Scenar OTM GB528".

## iOS Search / Filtering Support

- [ ] Add bullet entity_aliases for common abbreviations — ELDM→ELD Match, SMK→MatchKing, TMK→Tipped MatchKing, ABLR→AccuBond Long Range, VLD→VLD Target/Hunting, GMM→Gold Medal Match, etc. Currently zero bullet aliases exist. Add via curation patches so they export to `alt_names` JSON. (source: reference DB analysis, 2026-03-18)
- [ ] Curate `popularity_rank` on top ~50 factory loads and top ~50 bullets — no ranking data exists today. Needed for "recommended" sort in ammunition picker. Small enough to do manually via curation patches. (source: reference DB analysis, 2026-03-18)

## Documentation

_(empty — add items as docs drift from code)_
