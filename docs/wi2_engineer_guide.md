# WI-2: Engineer Onboarding Guide

*Quick-start for the engineer taking this to implementation.*

---

## Read These, In This Order

1. **`docs/engineering_overview.md`** — Project context, domain concepts, architecture philosophy. Read once to orient.
2. **`docs/wi2_design_proposal.md`** — **The source of truth.** Approved schema, pipeline architecture, design decisions, MVP scope, next steps. This is your spec.
3. **`docs/wi2-doro-learnings.md`** — Engineering lessons from a prior data pipeline (Doro). Dense and practical. The pipeline patterns, entity resolution tiers, and search architecture recommendations here directly informed the design proposal. Read this before writing pipeline code.
4. **`docs/wi2_research_findings.md`** and **`docs/ammo_db_research_notes.md`** — Domain research on caliber naming, BC data, manufacturer product structures. Skim these to understand *why* certain schema decisions were made (e.g., why bullet diameter is stored explicitly, why alt_names is a JSON array).
5. **`docs/python-code-patterns.md`** -- Before writing any code - lays out preferences for writing Python code.

## You Can Skip

- **`eng_work_items.md` WI-2 section** — The original brief. Superseded by the design proposal. It has a deprecation notice.
- **`docs/wi2_goals_and_strategy.md`** — Strategic context that's been absorbed into the design proposal's principles section.
- **`docs/wi2_research_plan.md`** — The research plan that produced the findings above. The findings are what matter; the plan is done.

## The Work, Concretely

The design proposal's "Next Steps" section is your task list. Here's the short version:

**Step 1: Schema → Code.** Turn the entity tables in `wi2_design_proposal.md` into SQLAlchemy models + an initial Alembic migration. The schema is well-defined; this is mostly transcription. Don't forget the `chamber_accepts_caliber` join table.

**Step 2: Seed data.** Hand-curate Manufacturer (~15), Caliber (~15–20), and Chamber (~20–25) records. These are editorial, not scraped. Most Chamber records are auto-generated 1:1 from Caliber; only 5–8 need manual curation (.223/.556/.308/7.62 family). Validate your "priority loads" list against community data before scaling.

**Step 3: Pipeline.** Build the DISCOVER → STORE pipeline end-to-end with Hornady + 6.5 Creedmoor as the proving ground. Firecrawl for fetching, LLM extraction at ingestion time, tiered entity resolution. The Doro learnings doc is your playbook here.

**Step 4: Human review tooling.** Build this *before* you scale ingestion. CLI that shows a record, links to source URL, lets you approve/edit/reject. You will use this constantly.

**Steps 5–7: Search + export.** FTS5 with abbreviation expansion, trigram correction, chamber-aware ranking. Then the export script from backend → bundled SQLite.

## Things to Watch Out For

- **BC data is the hardest part.** Manufacturers publish inconsistent values across G1/G7, velocity bands, and product pages vs. spec sheets. The published/estimated split in the schema handles this, but you'll spend real time on reconciliation during human review.
- **Entity resolution between bullets and cartridges.** Hornady #26331 (bullet) and #81500 (cartridge containing that bullet) — the pipeline needs to correctly link these. SKU matching is the highest-confidence path; fall back to name+weight+caliber composite keys.
- **The abbreviation dictionary is never done.** Seed it with the vocabulary from the Doro learnings doc, but plan to expand it from search-miss data post-launch.

---

## Where We Are (as of 2026-02-20)

**Steps 1 and 2 are done.**

- SQLAlchemy models for all 8 entities (Manufacturer, Caliber, Chamber, ChamberAcceptsCaliber, Bullet, BulletBCSource, Cartridge, RifleModel, EntityAlias) are implemented under `src/rangefinder/models/`.
- Initial Alembic migration exists.
- `scripts/seed_data.py` seeds 32 manufacturers, 25 calibers, 26 chambers, 30 chamber-caliber links, and 83 entity aliases. Two rounds of domain expert review incorporated. Idempotent via `--reset`. 20 tests, lint clean.
- The Bullet, BulletBCSource, Cartridge, and RifleModel tables exist in the schema but are empty. These are pipeline-populated, not hand-curated.

**What's next: Step 3 — the pipeline.** Everything below is sequenced by "what unblocks the most with the least ceremony."

### 3a. Prove you can scrape one product page end-to-end

Pick a single, concrete target: **Hornady 140gr ELD Match in 6.5 Creedmoor** (bullet page + cartridge page). Build the thinnest possible vertical slice:

1. **Fetch** a cached copy of the product page (Firecrawl or plain httpx — doesn't matter yet, the abstraction can come later).
2. **Extract** structured fields into a Pydantic schema using an LLM call. The schema should match the Bullet and Cartridge models exactly — `weight_grains`, `bc_g7_published`, `caliber_id`, `sku`, etc.
3. **Resolve** the extracted data against existing seed data. The caliber name from extraction needs to map to a Caliber row. The manufacturer name needs to map to a Manufacturer row. This is where the EntityAlias table earns its keep.
4. **Store** the resolved Bullet and Cartridge rows in the database.

The goal is a script you can run that takes a URL and produces a database row. No batching, no scheduling, no retry logic. Just: URL in, validated record out. This forces you to confront every hard problem (HTML structure, LLM prompt design, entity resolution, data validation) on a single example before building infrastructure around it.

Deliverable: `scripts/ingest_one.py` (or similar) that you can run against a Hornady product URL and get a Bullet + Cartridge record in the DB.

### 3b. Pydantic extraction schemas

Define the Pydantic models that the LLM extraction step targets. These are separate from the SQLAlchemy models — they represent what the LLM returns, before entity resolution and normalization. They should enforce constraints the LLM is likely to violate (e.g., `bc_g7` must be between 0.05 and 1.0, `weight_grains` must be positive, caliber name must be a string not a number).

These schemas live in `src/rangefinder/schemas/` (already stubbed). They'll be reused by both the single-page ingest script and the eventual batch pipeline.

### 3c. Entity resolution layer

The bridge between "the LLM said the manufacturer is 'Hornady Manufacturing'" and "that's Manufacturer row X in our database." This is where the alias table, alt_names, and fuzzy matching come together.

Start simple: exact match on `name`, then exact match on `alt_names` JSON array, then exact match on `EntityAlias.alias`. That covers >90% of cases for the seed data we have. Fuzzy/trigram matching is a later refinement — don't build it until you have real extraction failures that need it.

### 3d. Human review tooling (Step 4, but build it early)

The design proposal says to build this before scaling ingestion. Agreed. After 3a proves the extraction works, build a minimal CLI review tool before ingesting more pages. It doesn't need to be fancy:

- Show the extracted record (all fields, formatted).
- Show the source URL (clickable in the terminal).
- Show confidence scores and match methods.
- Accept approve / edit / reject.
- Write the decision back to the DB (a `review_status` field, or a separate review log).

This is Step 4 in the original plan, but it's tightly coupled with Step 3 in practice. You'll want it as soon as you start ingesting real data.

### 3e. Scale to Hornady's full 6.5 CM lineup

Once 3a–3d work for one page, run the pipeline across all Hornady 6.5 Creedmoor bullets and cartridges. This is maybe 8–12 products. It will surface:

- Pages with different HTML structures than your first example.
- Extraction edge cases (missing fields, multiple BC values, bullet/cartridge disambiguation).
- Entity resolution ambiguities that need the review tool.

Fix what breaks. Then expand to a second manufacturer (Sierra or Berger — both are bullet-only, which simplifies things since there's no cartridge entity to resolve).

### After that

The path from "Hornady 6.5 CM works" to "200–300 factory loads across priority calibers" is iteration, not architecture. Expand by manufacturer, then by caliber. The hard problems are all in 3a–3c. Steps 5–7 (FTS5 search, abbreviation expansion, bundled SQLite export) are well-understood and can be built in parallel once the pipeline is producing data.

---

*Last updated: February 2026*
