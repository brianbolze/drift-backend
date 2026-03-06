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

## Code / Tooling

- [ ]

## Documentation

_(empty — add items as docs drift from code)_
