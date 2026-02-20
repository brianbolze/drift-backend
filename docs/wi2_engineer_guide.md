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

*Last updated: February 2026*
