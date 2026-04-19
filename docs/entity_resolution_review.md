# Entity Resolution Review & Refactor Plan

Status: step 1 implemented (merged 2026-04-19 on `claude/unified-lookups-8dp6m`, commit `0355b74` — deterministic lookups now flow through `drift.resolution.aliases.lookup_entity` for both curation and the pipeline resolver; cross-system consistency test added). Other steps pending. Findings map to specific files/lines as of 2026-04-19.

This document captures a thorough code review of how Drift resolves extracted entities (bullets, cartridges, rifles, manufacturers, calibers, chambers) against existing DB records, plus a prioritized refactor sequence. The review was prompted by observed shortcomings in bullet and cartridge matching (see TODO.md) but the overall architecture has enough issues that a broader refactor is warranted.

Relevant files:

- `src/drift/pipeline/resolution/resolver.py` — main resolver used during the RESOLVE pipeline stage
- `src/drift/curation.py` — parallel resolver used by YAML curation patches
- `scripts/pipeline_store.py` — wraps the resolver, applies thresholds, decides create / match / flag
- `src/drift/models/entity_alias.py`, `src/drift/models/bullet_product_line.py` — alias/product-line tables
- Related docs: `docs/bullet_matching_design.md`, `docs/bullet_product_line_design.md`

---

## Top-level findings (priority order)

### 1. Two divergent resolution systems that can disagree on the same input

- `EntityResolver.resolve_manufacturer/caliber/chamber` (`resolver.py:399-552`) applies Python-side normalization + fuzzy matching.
- `curation._resolve_entity` (`curation.py:298-331`) does case-insensitive SQL equality → EntityAlias fallback. No fuzzy, no `_normalize_caliber` period-stripping.

A curation patch that resolves `"308 Win"` via EntityAlias may still fail a pipeline run that relies on `_normalize_caliber` — or vice-versa. This is the most consequential structural issue: **there is no single source of truth for "what does this string mean."**

**Fix:** extract lookup into one module (`drift/resolution/aliases.py`) that both paths call, parametrized by matching strictness.

### 2. EntityAlias is advertised as canonical normalization, but barely used

CLAUDE.md says: *"Always use EntityAlias table for normalization, never raw string matching."*

Reality:

- Only `resolve_caliber` hits EntityAlias (`resolver.py:478-490`).
- `resolve_manufacturer` (`resolver.py:399-434`) uses the on-model `alt_names` JSON but **never consults EntityAlias** — new manufacturer aliases added by curation are invisible at pipeline time.
- `match_bullet` doesn't consult EntityAlias for `entity_type="bullet"` or `"bullet_product_line"`. The `BulletProductLine` table exists with proper alias support, but `_normalize_product_line` matches the raw `bullet.product_line` string column instead (`resolver.py:606-635`). **The "ELDM → ELD Match, SMK → MatchKing, ABLR → AccuBond Long Range" TODO (TODO.md line 49) cannot be addressed without code changes** — curators have no channel for the resolver to learn new product-line aliases.
- `match_cartridge` and `match_rifle` never consult EntityAlias.

**Fix:** every `match_*` should have a consistent pre-pass: lookup `(entity_type, alias)` in EntityAlias before running fuzzy tiers.

### 3. Jaccard on word sets is the wrong metric for asymmetric product names

`_name_similarity` (`resolver.py:186-197`) uses `intersection / union`. That penalizes every extra word equally, so "ELD-X" vs "30 Cal .308 178 gr ELD-X®" scores ~0.14 — far below any threshold. This is exactly the TODO.md line 32 issue ("Cartridge→bullet resolver can't match generic extracted names").

`_bullet_name_score` (`resolver.py:270-316`) was bolted on as a containment-based score, but:

- It's bullet-specific; cartridge and rifle still use pure Jaccard (`match_rifle:796`).
- It stacks another hand-tuned length-factor formula on top of more magic constants.
- Abbreviation expansion is a static dict of 14 entries (`resolver.py:236-251`) — not curator-editable.

**Fix:** replace `_name_similarity` with `rapidfuzz.fuzz.token_set_ratio` (handles long-vs-short asymmetry natively). Keep abbreviation expansion, but source abbreviations from EntityAlias rows with `entity_type="bullet_product_line"` so curation can extend the vocabulary.

### 4. Confidence thresholds are magic constants scattered across two files, no calibration harness

Inventory of tunable constants:

| Constant | Location | Value |
|---|---|---|
| Composite key confidence formula | `resolver.py:654` | `0.85 + name_score * 0.1` |
| Product-line + weight match | `resolver.py:630` | 0.93 |
| Product-line no weight match | `resolver.py:633` | 0.80 |
| Fuzzy weight-agrees factor | `resolver.py:675` | 0.8 |
| Fuzzy weight-mismatch factor | `resolver.py:675` | 0.4 |
| Composite weight tolerance | `resolver.py:646` | ±0.5 gr |
| Fuzzy weight tolerance | `resolver.py:669` | ±1.0 gr |
| Bullet weight gate | `resolver.py:968` | ±5.0 gr |
| Diameter tolerance | `resolver.py:590` | ±0.001" |
| BC tolerance | `resolver.py:969` | 5e-4 |
| BC/weight boost per signal | `resolver.py:994,1003,1013` | +0.05 |
| Fuzzy manufacturer threshold | `resolver.py:421` | 0.5 / ×0.9 |
| Fuzzy caliber threshold | `resolver.py:499` | 0.4 / ×0.85 |
| Name-score threshold (Tier 2) | `resolver.py:653,740` | 0.55 |
| Fuzzy name threshold (Tier 3) | `resolver.py:666,753` | 0.5 |
| `MATCH_CONFIDENCE_THRESHOLD` | `pipeline_store.py:38` | 0.7 |
| `AUTO_CREATE_CONFIDENCE_CEILING` | `pipeline_store.py:44` | 0.5 |
| Auto-create weight tolerance | `pipeline_store.py:274,280` | 1.0gr bullet / 2.0gr cartridge |

No documented rationale, no golden-set regression test.

**Fix:** consolidate into a `ResolutionConfig` dataclass with per-field comments explaining calibration. Add a fixtures-based regression that locks accuracy % on a curated "ground truth" subset.

### 5. Ambiguity is computed but never acted upon

`MatchResult.is_ambiguous` (`resolver.py:59-64`) flags matches where the runner-up is within 0.2 confidence. `pipeline_store.py:439` only gates on `confidence >= MATCH_CONFIDENCE_THRESHOLD` — so **0.88 vs. runner-up 0.85 auto-matches silently**, even though that's exactly the scenario where a human should review. The ambiguity flag writes to `review.json` but drives no behavior.

**Fix:** route `is_ambiguous` matches to a new `flagged_ambiguous` action in `pipeline_store.py`.

### 6. Cartridge→bullet sub-resolution ignores same-manufacturer preference

`resolver.py:911` calls `match_bullet(bullet_stub, None, diameter)` — passes `None` for manufacturer. The comment correctly notes factory ammo often uses foreign bullets, but the current code is first-best-wins with no tiebreaker. This is the mechanism for the "4 MatchKing→Nosler HPBT false matches" TODO.

**Fix:** score same-manufacturer candidates slightly higher (e.g. +0.05) rather than filtering them exclusively. Also worth filtering by `product_line_id` when the cartridge extraction includes a product line.

### 7. `_normalize()` destroys hyphens

`resolver.py:97` replaces `[^\w\s.]` with space, turning `"ELD-X"` into `"eld x"`. Then Jaccard splits on whitespace and compares `{eld, x}` to DB tokens — `x` alone is a noise match. `_normalize_product_line` handles hyphens correctly, but it's only used in the product-line tier. All fuzzy paths use `_normalize` and inherit the bug.

**Fix:** preserve hyphens and internal punctuation meaningful to identifier strings (ELD-X, A-Tip, Match-Grade). Fold into whichever `_normalize` variant survives the rapidfuzz migration.

### 8. The "always use EntityAlias for manufacturers" claim in CLAUDE.md is unenforced

`Manufacturer.alt_names` is a JSON array on the model; the `Hornady` variants ("Hornady Inc", "Hornady Inc.", "Hornady Manufacturing") are handled by `_normalize` trailing-period stripping + alt_names — not by EntityAlias. This works today because the Hornady row has those in alt_names, but new manufacturer variants added via curation `add_entity_alias` won't hit.

**Fix:** either update CLAUDE.md to describe actual behavior, or route manufacturer lookups through EntityAlias (preferred — consistent with intent).

---

## Secondary issues

### 9. No learning loop

When a flagged match is manually accepted (e.g. via a curation patch), nothing in the pipeline records that decision as an alias for next time. Every run relitigates the same fuzzy matches.

**Fix (lightweight):** when `pipeline_store` writes `"action": "matched_existing"` with confidence ≥ threshold but method = fuzzy, emit a candidate EntityAlias suggestion to `review.json` so a human can promote it.

### 10. Resolver caches never invalidate

`EntityResolver.__init__` (`resolver.py:367-373`) caches manufacturers/calibers/chambers/caliber_aliases on first use. Current `pipeline_store.py` doesn't create those mid-run so it's latent, but it's a foot-gun.

**Fix:** add `invalidate_caches()` method; call after any session-level create of a cached entity type.

### 11. Inconsistent SQLAlchemy style

CLAUDE.md: *Use `Session.scalars()` not `Session.execute().scalars()`.* Resolver respects this. `curation.py` uses `session.query(...)` throughout (`curation.py:312, 321, 354, 357, 365, ...`) — legacy 1.x style. Unify on 2.0 style.

### 12. Rejected-caliber handling is a side-channel hack

`pipeline_store.py:75-84` string-matches `unresolved_refs` entries to detect rejected calibers. If resolver ever changes the unresolved-ref format (`"caliber: X"` → `"caliber=X"`), this silently breaks.

**Fix:** move rejection into the resolver as either a structured `result.rejected: bool` field or a first-class Tier 0.

### 13. `bullet_match_confidence` written, never read

`resolver.py:950` assigns `result.bullet_match_confidence`, but `pipeline_store.py` only reads `resolution.match.confidence`.

**Fix:** either route it into the gating logic (so a low-confidence bullet FK doesn't block an otherwise-good cartridge match, or vice-versa), or delete the field.

### 14. `# flake8: noqa: E501 B950` at top of `resolver.py:1`

Blanket suppression lets long lines accumulate. CLAUDE.md mandates 120-char black. Remove blanket and fix individually.

### 15. Test coverage gap: no cross-system consistency test

`tests/test_resolver.py` and `tests/test_curation.py` don't share fixtures. No test like "a manufacturer added to EntityAlias by curation is findable by the pipeline resolver" — which would have caught finding #2.

**Fix:** add `tests/test_resolution_consistency.py` that exercises both paths against the same EntityAlias rows.

### 16. Extraction schemas exist (Pydantic) but resolver takes `dict`

Losing type safety at the handoff. `_get_value` papers over both wrapped and unwrapped dicts (`resolver.py:1023-1030`).

**Fix:** accept `ExtractedBullet | ExtractedCartridge | ExtractedRifle` to kill a class of `KeyError` / wrong-field-name bugs.

### 17. No telemetry aggregation

`methods_tried` is captured per match but never summarized. Basic health metric — "X% of bullet matches via exact_sku, Y% composite, Z% fuzzy with N% confidence < 0.5" — is absent.

**Fix:** add a `stats["methods"]` dict in `pipeline_store.py`; print aggregates at end of run.

---

## Additional findings from `wi2-doro-learnings.md` cross-check

Comparing the Doro learnings doc against the codebase surfaced three further items the team planned but never shipped.

### 18. `bullet_match_confidence` and `bullet_match_method` are dead columns

Both exist on `Cartridge` (`cartridge.py:46-47`) and the resolver computes `bullet_match_confidence` (`resolver.py:950`), but `_make_cartridge` in `pipeline_store.py:129-156` writes neither. Only archived seed data populates them. This blocks Doro's key retrospective audit query — *"all cartridges with `bullet_match_confidence < 0.95` via `fuzzy_name`"* — which is directly relevant to TODO.md's *"99 existing cartridges with wrong bullet_id."*

**Fix:** persist both fields from every pipeline cartridge creation and match-update path. Two-line change in `_make_cartridge` plus a write in the match_updated branch of `pipeline_store.py`.

### 19. Unit normalization heuristics never shipped

Doro pattern: *"if `muzzle_velocity < 500`, probably m/s; multiply by 3.281. If `bullet_weight < 5`, probably grams."* No such guards exist. TODO.md already records the exact failure this would have caught: *"Lapua G580 100gr bullet — pipeline confused '6,5 g' weight with 6.5mm caliber."*

**Fix:** a normalization step between EXTRACT and RESOLVE that applies numeric-range heuristics, flags suspicious values, and rejects-don't-stores the outliers. Include BC (0.05–0.90), MV (1500–4500 fps), bullet weight (15–750 gr), bullet diameter (0.10–0.60 in) range checks as flag-don't-store guards.

### 20. Source quality ≠ extraction confidence

We store `extraction_confidence` per entity but not source quality. Doro's rule `effective = min(source_quality, extraction_confidence)` would drive `BulletBCSource` reconciliation (Litz-measured > manufacturer bullet page > manufacturer ammo page). Currently last-write-wins. The `BulletBCSource` table exists for this purpose but reconciliation logic is underused.

**Fix:** add `source_quality` to `BulletBCSource` (already has the field — confirm it's populated with meaningful values, not always 1.0), implement a `ReconciliationConfig`-style picker for choosing the canonical `Bullet.bc_g1_published` / `bc_g7_published` across sources. Larger scope than findings #18–19; likely its own phase.

### Also noted, lower priority

- No `upc` column on `Cartridge` — would give cartridge resolution a second deterministic tier (Doro scores UPC at 0.99).
- Numeric range validation (BC G1 0.1–0.8, G7 0.05–0.45) is stated in CLAUDE.md but not enforced in the pipeline as flag-don't-store guards (overlaps with finding #19).
- `match_method` persistence on `Bullet` and `RifleModel`, not just `Cartridge` — same audit-query logic should apply across entity types.
- No coverage dashboard (automated *"15/18 calibers defined, Hornady 89/95"* report) — orthogonal to resolver but would make "what do I curate next" obvious.
- No interactive review CLI with `[o]pen URL` shortcut — `review.json` works but is not ergonomic.

---

## Recommended refactor sequence

Mostly independent; tackle in roughly this order.

1. ✅ **DONE** — Unified lookup module on `claude/unified-lookups-8dp6m` (commit `0355b74`). Addressed findings #1, #2, #8, #11.
2. **Replace Jaccard with `rapidfuzz.token_set_ratio`** in `_name_similarity`; preserve hyphens in normalization. Delete `_bullet_name_score` if redundant; otherwise unify between bullet/cartridge/rifle. Addresses findings #3, #7.
3. **Wire `bullet_product_line` EntityAlias lookups into `match_bullet`** (use `product_line_id` FK + aliases, not the string column). Addresses finding #2 for bullets, unblocks TODO.md line 49.
4. **Consolidate thresholds into `ResolutionConfig`** dataclass; add golden-set regression test. Addresses finding #4.
5. **Resolver small wins.** Act on `is_ambiguous` in `pipeline_store.py` (new `flagged_ambiguous` action, finding #5); same-manufacturer bias in cartridge→bullet as score boost not filter (finding #6); persist `bullet_match_confidence` + `bullet_match_method` from every pipeline write path (finding #18, resolves finding #13 by using the field instead of deleting it); type the resolver inputs with Pydantic schemas (finding #16).
6. **Normalization hardening.** Unit-confusion heuristics (m/s→fps, grams→grains, mm→inches) and numeric-range flag-don't-store guards between EXTRACT and RESOLVE. Addresses finding #19 and the range-validation sub-item.
7. **Learning loop + telemetry.** Surface EntityAlias suggestions for fuzzy matched-existing cases in `review.json`; aggregate `methods_tried` into an end-of-run breakdown. Addresses findings #9, #17.
8. **BC reconciliation** (deferred, larger). `ReconciliationConfig`-style picker for canonical `Bullet.bc_g1_published`/`bc_g7_published` across `BulletBCSource` rows, weighted by source quality × extraction confidence. Addresses finding #20.

The Jaccard swap (step 2) and the EntityAlias wiring for product lines (step 3) are the two changes most likely to move the needle on the cartridge→bullet miss rate.
