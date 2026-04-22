# v6 Publish — Resume Handoff

**Status:** shelved, pending product-line tier resolver bug fix. All infrastructure fixes landed; publish blocked on data-quality regression.

**Last active session:** 2026-04-22. Master is 6 commits ahead of `origin/master`, unpushed.

---

## TL;DR for the next agent

1. Master has 6 unpushed commits (5 resolver/infra fixes + 1 docs). Review + push.
2. `maintenance-primitives` branch + worktree at `../shooting-maintenance/` has a separate PR-ready bundle (sitemap-watch, refresh, bc-reconcile, digest, prompt-cache plumbing, 98 tests). Review + merge independently.
3. v6 publish is blocked by a **product-line tier scoring regression** in `match_bullet`. 25/37 same-diameter cartridge→bullet relinks observed during v6 store-commit dry-run were downgrades (SST→InterLock SP, ELD-X→ELD Match, Hornady→Sierra brand swaps). Forensic evidence in `data/forensic/v6-resolver-regression-2026-04-22/`.
4. Fix the tier bug → re-run `pipeline-store` dry-run → expect zero downgrades → publish v6.

---

## Current repo state

### Master (local, unpushed)

```
9115bd5  Document product-line tier regression blocking v6
237a511  Add forensic dir to gitignore + log resolver follow-ups
96b4594  Add cross-diameter guard to pipeline_store bullet_id overwrite
d9a530b  Enforce caliber compatibility across all match_cartridge tiers
2382040  Fix resolver fallback over-matching via raw name-sim gate
51ed5dc  Fix LLMResponse missing cache_creation/cache_read token fields
81bd533  (origin/master) Add create_manufacturer curation op + patch 035
```

### Working tree

Clean. `data/drift.db` reverted to `81bd533` state after the v6 store-commit was rolled back. `data/production/drift.db` matches v5 published baseline (87/1324/553/136).

### Tests

518 passing. 7 new tests from this session lock the three shipped fixes:

- `TestRelaxedDiameterFallback` (×5) — raw name-sim gate on H3 fallback
- `TestCartridgeCaliberCompatibility` (×2) — caliber filter across match_cartridge tiers
- `TestCrossDiameterGuard` (×4) — pipeline_store diameter check on bullet_id overwrite

### Parallel branch

`maintenance-primitives` at commit `405e02f`, checked out in worktree at `/Users/brianbolze/Development/software/shooting-maintenance/`. 16 files / +3326 lines. Ready for PR review. Do not touch from main repo — coordinate through PR merge instead.

---

## What's shipped this session (on master, unpushed)

All five fixes are independently valuable and should ship regardless of v6 timing.

### 1. `51ed5dc` — LLMResponse missing fields

`LLMResponse` dataclass was missing `cache_creation_input_tokens` / `cache_read_input_tokens` fields that `engine.py` already read, causing 12 test failures on master. Minimal port from `maintenance-primitives` branch (dataclass fields + Anthropic provider population only, not the full prompt-caching feature).

### 2. `2382040` — H3 fallback over-matching

Resolver's relaxed-diameter fallback in `match_bullet` gated on `.confidence ≥ 0.85`, but `composite_key` tier inflates confidence to 0.85–0.95 regardless of name match. Result: any weight-compatible bullet with name_score > 0.55 passed, enabling cross-caliber picks like `30-06 165gr Ballistic Tip → .357 165gr Handgun Solid`.

Fix: added `fallback_min_raw_name_similarity = 0.90` to `ResolutionConfig`. Fallback now gates on raw name similarity against the extracted name, not composite-inflated confidence.

**Files:** `src/drift/pipeline/resolution/resolver.py`, `src/drift/pipeline/resolution/config.py`, `tests/test_resolver.py` (+5 tests).

### 3. `d9a530b` — Caliber compatibility across match_cartridge tiers

`match_cartridge` tiers (exact_sku, alias, composite_key, name fuzzy) did not enforce `candidate.caliber_id == extracted.caliber_id`. Nosler SKU patterns repeat across calibers, producing `exact_sku 1.00` cross-caliber cartridge matches (`.375 H&H 300gr → .308 Winchester`).

Fix: caliber filter applied on all tiers. SKU matches without resolvable caliber are skipped with a warning. 7 skips observed in validation run, all Federal Custom Shop placeholders that get rejected downstream anyway.

### 4. `96b4594` — Cross-diameter store guard

Defense-in-depth: even if the resolver returns a cross-diameter bullet, `pipeline_store._update_cartridge_bullet_id` now refuses to write. New `_bullet_diameter_compatible()` check (±0.005") logs a `blocked_cross_diameter` action and flags the row instead of overwriting. 50 guard firings observed in the real v6 store-commit before rollback.

### 5. `237a511` — Housekeeping

`.gitignore` excludes `data/forensic/`. `TODO.md` logs the `.30-40 Krag` missing-caliber follow-up and the initial 37-shift investigation note.

### 6. `9115bd5` — Regression documentation

`TODO.md` sharpened to reference the BLOCKER-v6 entry + forensic dir.

---

## What's blocking v6

### The product-line tier regression

When the v6 `pipeline-store-commit` ran (post H3 fix, caliber-compat enforcement, and cross-diameter guard), 37 existing cartridges had their `bullet_id` overwritten with a *same-diameter* bullet. All 37 passed every safety gate (caliber match, diameter match, weight match). But when classified:

| Category | Count |
|---|---|
| v5 pick was better (downgrade) | **25** |
| v6 pick was better (legitimate improvement) | 10 |
| Ambiguous | 2 |

Two of the 25 downgrades tripped the v6 publish's PK stability check because the v6 bullet had no BC, so the production export filter dropped the cartridge. The other 23 would have silently shipped subtly wrong data.

### Failure patterns observed

**Pattern A — product-line sibling swap (10 cases).** Cartridge name explicitly identifies the bullet product, but resolver picks a sibling from the same manufacturer:
- SST → InterLock SP (6.5 CM 129gr American Whitetail TIPPED)
- ELD-X → ELD Match (300 Win Mag 178gr Precision Hunter)
- InterLock BTSP → InterLock RN (25-06 117gr American Whitetail)
- CX → ECX (6.5 CM 120gr Outfitter)
- Terminal Ascent → Scirocco (Federal 6.5 CM 130gr)
- TSX BT → TSX FN FB (Barnes 308 150gr)

**Pattern B — cross-brand swap (11 cases).** Single-brand cartridge matches wrong-brand bullet:
- Hornady BLACK 6mm ARC 105gr → Sierra MatchKing
- Winchester Ballistic Silvertip → Power-Point / Lapua Scenar / Cutting Edge
- Nosler Expansion Tip → Winchester Ballistic Silvertip
- Barnes VOR-TX TTSX → Sierra GameKing

**Pattern C — same-brand wrong type (4 cases).** Manufacturer filter held, but product-type mismatch:
- 30-30 RN → InterLock SP (needs RN for tubular magazines)
- FMJ → Power-Point
- Varmageddon → Expansion Tip

### Root-cause hypothesis

All three patterns cluster around: `product_line_alias` / `product_line` / `composite_key` tiers in `match_bullet` rank wrong bullets above right bullets, especially when `product_line_id` was newly populated on some bullets (patches 028-030) but not uniformly across candidates. The 234 auto-promoted cartridge aliases created mid-run during store-commit may further distort tier rankings.

See `data/forensic/v6-resolver-regression-2026-04-22/product_line_tier_regression.md` for the full 37-row classification and investigation entry points.

---

## Next session: product-line tier investigation

### Goal

Understand why `match_bullet` ranks wrong bullets above right bullets within same-diameter same-manufacturer candidates. Fix the scoring. Confirm the 25 downgrades disappear. Resume v6.

### Reproducer already prepared

```
data/forensic/v6-resolver-regression-2026-04-22/
  drift-post-compound-fix.db           # post-store-commit reproduction target
  production-drift-post-compound-fix.db
  store_report-post-compound-fix.json  # full dry-run report, all tier annotations
  relinks.tsv                          # original 58 relinks (pre-compound-fix)
  v5_better_25_cases.json              # machine-readable cart_ids + rationales
  product_line_tier_regression.md      # full writeup + hypothesis
  resolution_config.json               # active config at time of regression
```

### Suggested approach

1. **Before touching resolver code, add diagnostic logging mode to `match_bullet`.** For each match, dump top-5 candidates with their tier, composite score, and component scores (name, weight, product_line, manufacturer). ~1 hour investment. Run against the 25 V5-better cart_ids and the ranking pathology should be visible directly rather than inferred.

2. **Categorize findings by tier.** Is product_line_alias always winning? Does composite_key's name_score weight wrong bullets via shared tokens ("Ballistic Tip Hunting" vs "Handgun Solid")? Does the manufacturer filter have a bypass path?

3. **Propose minimal fix.** Likely candidates:
   - Product-line tier requires product_line_id match on both sides (skip if either is null instead of treating null as wildcard)
   - Manufacturer filter enforced at every tier, not just primary
   - Composite_key name_score weight raised or tokenization tightened

4. **Write regression tests** seeded with 5-10 of the 25 V5-better cases. All must resolve to the v5 bullet.

5. **Validate with forensic replay.** Re-run `match_bullet` against the 25 cart_ids from `drift-post-compound-fix.db`. Expect the correct bullet_id on each.

### Hard stops (same as always)

- No commit, no push, no publish without explicit user sign-off on dry-run
- Do not touch `data/forensic/` — it's the reproduction
- Do not run `pipeline-store-commit` until the tier fix passes forensic replay
- Do not touch `../shooting-maintenance/` worktree

---

## After the tier fix

### Resume v6 sequence

1. `make pipeline-store` (dry-run) against clean `drift.db`
2. Diff vs v5: expect 0 cross-diameter relinks, **near-zero downgrades** in same-diameter relinks
3. Sign-off → `make pipeline-store-commit`
4. `make export-production-db` → row counts
5. `make publish-db CHANGELOG="..."` (dry-run) → PK stability must pass
6. Sign-off → `make publish-db-commit`
7. Update `MEMORY.md` with v6 state
8. `git push origin master`

### Changelog template for v6

> v6: +N cartridges / +M bullets (fresh parser-tier extractions + resolver caliber fallback recovery), parser-first extraction tier productionized (Hornady/Sierra/Nosler), resolver caliber-compatibility hardening (raw name-sim fallback gate, cross-tier caliber filter, store cross-diameter guard, product-line tier scoring fix), 3 new manufacturers (PMC/Fiocchi/HSM), page-defect curation locks (patch 034), priority-aware pipeline

---

## Key references

- Project conventions: `CLAUDE.md`
- Pipeline docs: `docs/pipeline_README.md`
- Publish flow: `scripts/publish_db.py` (`SCHEMA_VERSION` constant; bump on incompatible schema changes)
- Curation: `docs/curation_README.md`
- Evolving project state: `MEMORY.md` (at `/Users/brianbolze/.claude/projects/-Users-brianbolze-Development-software-shooting/memory/MEMORY.md`)
- Forensic evidence: `data/forensic/v6-resolver-regression-2026-04-22/`
- Parallel workstream: `maintenance-primitives` branch + `../shooting-maintenance/` worktree
