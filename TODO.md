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

## Pipeline Improvements

- [ ] Cutting Edge HTML at ~200KB after reduction — worst of all manufacturers, needs per-manufacturer CSS selector hints (source: pipeline working notes)
- [ ] Sierra/Nosler/Barnes at ~70KB — 2-3x over 30KB reducer target, still works but wastes tokens (source: pipeline working notes)
- [ ] Seed missing calibers (pistol, shotgun, exotic rifle) — blocks ~145 cartridge resolutions (source: pipeline working notes)
- [ ] Nosler BCs only in load data section — product pages return null BC, need to scrape load data pages separately (source: pipeline working notes)
- [ ] Bullet name normalization inconsistent — ALL CAPS (Sierra), metric prefix (Lapua), caliber in name (Hornady), trademark symbols (source: pipeline working notes)
- [ ] Cartridge→bullet resolver can't match generic extracted names to DB records — "ELD-X", "Berger Hybrid", "Fusion Soft Point" etc. don't fuzzy-match "30 Cal .308 178 gr ELD® Match" or "Fusion Component Bullet, .308, 180 Grain". Blocks 100+ cartridge resolutions. Resolver needs type+weight+diameter matching, not just name similarity (source: agent, 2026-03-06)
- [ ] No retry on transient httpx errors — `TimeoutException`/`ConnectError` permanently skip a URL with no retry (source: code review, 2026-03-06)
- [ ] `HttpxFetcher` creates new `AsyncClient` per request — no connection reuse/keep-alive across same-host URLs; same issue with `FirecrawlFetcher` reinstantiating `FirecrawlApp` per call (source: code review, 2026-03-06)
- [ ] `FirecrawlFetcher` has no timeout — `asyncio.to_thread` call blocks indefinitely if Firecrawl is down (source: code review, 2026-03-06)
- [ ] Batch poll doesn't catch `anthropic.RateLimitError` — only catches `APIConnectionError`/`InternalServerError` (source: code review, 2026-03-06)
- [ ] `--limit` applies to file count, not pending count — `--limit 10` slices first 10 reduced files; if all cached, nothing runs (source: code review, 2026-03-06)
- [ ] Stale flagged entries persist on re-extraction — `_write_flagged` deduplicates by hash, so old warnings stick around (source: code review, 2026-03-06)

## Code / Tooling

- [x] Curation dry-run leaks savepoint commits — `session.begin_nested()` + `sp.commit()` persists through outer `session.rollback()` on SQLite. Deletes and creates in dry-run mode actually modify the DB (source: agent, 2026-03-06)
- [ ] No `ondelete` cascade on any FK relationship — `BulletBCSource.bullet_id` especially needs `ondelete="CASCADE"` (source: code review, 2026-03-06)
- [ ] Missing indexes on FK columns used by resolver — `bullet.manufacturer_id`, `bullet.bullet_diameter_inches`, `cartridge.caliber_id`, etc. (source: code review, 2026-03-06)
- [ ] Missing composite unique constraints on natural keys — `Bullet(manufacturer_id, name, weight_grains, diameter)` and `Cartridge(manufacturer_id, name, caliber_id)` (source: code review, 2026-03-06)
- [ ] `Optic.reticle_id` non-nullable — blocks storing optics with unknown/custom reticles (source: code review, 2026-03-06)
- [ ] No controlled-vocabulary validation on `base_type`, `tip_type`, `type_tags`, `used_for` in extraction schemas — config defines valid values but Pydantic doesn't enforce them (source: code review, 2026-03-06)
- [ ] Confusing script names: `validate_manifest.py` (JSON format) vs `manifest_validate.py` (DB cross-check) (source: code review, 2026-03-06)
- [ ] Session created outside try block in `pipeline_store.py` — leaks if exception occurs before try (source: code review, 2026-03-06)

## Documentation

_(empty — add items as docs drift from code)_
