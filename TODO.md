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

- [ ] 70+ cartridge-bullet weight mismatches (30% of cartridges) — likely wrong bullet_id linkages from pre-abbreviation-expansion pipeline runs (source: QA report, 2026-03-06)
- [ ] 99 existing cartridges with wrong bullet_id — re-run pipeline-store-commit after ensuring correct bullets exist in DB (source: pipeline working notes)
- [ ] 7 Hornady International cartridges with zero velocity — pages don't publish MV, need supplementary data source (source: QA report, 2026-03-06)
- [ ] 4 MatchKing->Nosler HPBT false matches — Sierra MatchKing bullets missing at certain weights, causing cross-manufacturer false positives (source: pipeline working notes)
- [ ] 22 bullets missing BC data entirely — no BulletBCSource records (source: QA report, 2026-03-06)
- [ ] BulletBCSource rows never deduplicated on re-runs — no unique constraint on `(bullet_id, bc_type, bc_value, source_url)` and no existence check before insert (source: code review, 2026-03-06)
- [ ] BC tolerance `_BC_TOLERANCE = 1e-4` too tight for 3-decimal-place values — should be `5e-4` or `1e-3`, BC confidence boost almost never fires (source: code review, 2026-03-06)

## Pipeline Improvements

- [ ] Cutting Edge HTML at ~200KB after reduction — worst of all manufacturers, needs per-manufacturer CSS selector hints (source: pipeline working notes)
- [ ] Sierra/Nosler/Barnes at ~70KB — 2-3x over 30KB reducer target, still works but wastes tokens (source: pipeline working notes)
- [ ] Seed missing calibers (pistol, shotgun, exotic rifle) — blocks ~145 cartridge resolutions (source: pipeline working notes)
- [ ] Nosler BCs only in load data section — product pages return null BC, need to scrape load data pages separately (source: pipeline working notes)
- [ ] Bullet name normalization inconsistent — ALL CAPS (Sierra), metric prefix (Lapua), caliber in name (Hornady), trademark symbols (source: pipeline working notes)
- [ ] `match_cartridge` Tier 2 returns first weight match, not best — should track best composite score like `match_bullet` does; threshold 0.3 also too low vs bullet's 0.55 (source: code review, 2026-03-06)
- [ ] `LLMProviderError` not retried in sync extraction — transient 5xx/connection errors abort immediately instead of retrying like `LLMRateLimitError` (source: code review, 2026-03-06)
- [ ] `stop_reason == "max_tokens"` not detected — truncated JSON silently produces 0 entities with no warning in sync or batch mode (source: code review, 2026-03-06)
- [ ] No retry on transient httpx errors — `TimeoutException`/`ConnectError` permanently skip a URL with no retry (source: code review, 2026-03-06)
- [ ] `HttpxFetcher` creates new `AsyncClient` per request — no connection reuse/keep-alive across same-host URLs; same issue with `FirecrawlFetcher` reinstantiating `FirecrawlApp` per call (source: code review, 2026-03-06)
- [ ] `FirecrawlFetcher` has no timeout — `asyncio.to_thread` call blocks indefinitely if Firecrawl is down (source: code review, 2026-03-06)
- [ ] Batch poll doesn't catch `anthropic.RateLimitError` — only catches `APIConnectionError`/`InternalServerError` (source: code review, 2026-03-06)
- [ ] `--limit` applies to file count, not pending count — `--limit 10` slices first 10 reduced files; if all cached, nothing runs (source: code review, 2026-03-06)
- [ ] `EntityAlias` re-queried from DB on every `resolve_caliber()` call — other lookups are cached, this one isn't (source: code review, 2026-03-06)
- [ ] Zero-entity extractions cached and silently skipped on re-run — should flag or force re-extract (source: code review, 2026-03-06)
- [ ] Stale flagged entries persist on re-extraction — `_write_flagged` deduplicates by hash, so old warnings stick around (source: code review, 2026-03-06)
- [x] Duplicate rule number 7 in extraction system prompt — second occurrence shadows the first (source: code review, 2026-03-06)

## Code / Tooling

- [ ] `stats["created"]` incremented before DB write succeeds in `pipeline_store.py` — on savepoint failure, `created` count is never decremented, report double-counts (source: code review, 2026-03-06)
- [ ] `test_seed_data.py` imports non-existent `seed_data` module — moved to `_archive/`, all ~30 tests never run (source: code review, 2026-03-06)
- [ ] `BulletBCSource` missing `TimestampMixin` — only entity table without `created_at`/`updated_at` (source: code review, 2026-03-06)
- [ ] No `ondelete` cascade on any FK relationship — `BulletBCSource.bullet_id` especially needs `ondelete="CASCADE"` (source: code review, 2026-03-06)
- [ ] Missing indexes on FK columns used by resolver — `bullet.manufacturer_id`, `bullet.bullet_diameter_inches`, `cartridge.caliber_id`, etc. (source: code review, 2026-03-06)
- [ ] Missing composite unique constraints on natural keys — `Bullet(manufacturer_id, name, weight_grains, diameter)` and `Cartridge(manufacturer_id, name, caliber_id)` (source: code review, 2026-03-06)
- [ ] `Optic.reticle_id` non-nullable — blocks storing optics with unknown/custom reticles (source: code review, 2026-03-06)
- [x] `bc_type` and `source` in `ExtractedBCSource` are unconstrained strings — should use `Literal["g1","g7"]` and validate against `BC_SOURCE_TYPES` (source: code review, 2026-03-06)
- [ ] No controlled-vocabulary validation on `base_type`, `tip_type`, `type_tags`, `used_for` in extraction schemas — config defines valid values but Pydantic doesn't enforce them (source: code review, 2026-03-06)
- [ ] Duplicate `url_hash()` implementations in `pipeline_fetch.py` and `pipeline_extract.py` — should be a shared util (source: code review, 2026-03-06)
- [ ] Confusing script names: `validate_manifest.py` (JSON format) vs `manifest_validate.py` (DB cross-check) (source: code review, 2026-03-06)
- [x] `pipeline-clean` Makefile target cleans non-existent dirs (`cache/`, `tmp/`) instead of real pipeline dirs (source: code review, 2026-03-06)
- [ ] `openai` extras not included in any install target — `make pipeline-install` installs `[dev,pipeline]` but not `[openai]`, provider tests fail on fresh install (source: code review, 2026-03-06)
- [ ] Session created outside try block in `pipeline_store.py` — leaks if exception occurs before try (source: code review, 2026-03-06)
- [x] Duplicate `db` fixture in `test_resolver.py` shadows `conftest.py` (source: code review, 2026-03-06)
- [ ] Legacy `session.query()` API used throughout resolver — inconsistent with SQLAlchemy 2.0 model style (source: code review, 2026-03-06)

## Documentation

_(empty — add items as docs drift from code)_
