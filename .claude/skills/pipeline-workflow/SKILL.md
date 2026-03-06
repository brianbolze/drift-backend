---
name: pipeline-workflow
description: Data pipeline operations for fetching, extracting, and storing ballistics product data from manufacturer websites
---

# Pipeline Workflow

## Pipeline Stages

```
1. SHOPPING LIST  ->  Gap analysis: what's missing in DB
2. COWORK PROMPTS ->  Generate research prompts for URL discovery
3. MERGE COWORK   ->  Ingest CoWork JSON into manifest
4. VALIDATE       ->  Check manifest structure
5. FETCH          ->  Download HTML from URLs (httpx, no browser needed)
6. REDUCE         ->  Clean HTML for LLM context (target: <30KB per page)
7. EXTRACT        ->  LLM extracts structured JSON from reduced HTML
8. RESOLVE        ->  Match extracted entities to DB records (manufacturer, caliber, bullet)
9. STORE          ->  Write resolved entities to drift.db
```

## Make Targets

| Target | What it does |
|---|---|
| `make pipeline-status` | Show counts at each stage |
| `make pipeline-shopping-list` | Gap analysis output |
| `make pipeline-fetch` | Download HTML |
| `make pipeline-extract` | Auto-detect provider, extract |
| `make pipeline-extract-batch` | Anthropic batch (50% cheaper) |
| `make pipeline-extract-sync` | Sequential with retries |
| `make pipeline-extract-openai` | OpenAI sync mode |
| `make pipeline-store` | **Dry-run** -- resolve and report |
| `make pipeline-store-commit` | **Commit** -- write to DB |
| `make pipeline-review` | List flagged items |
| `make pipeline-env-check` | Verify API keys |
| `make pipeline-models` | List available LLM models |

## Environment Variables

- `PIPELINE_PROVIDER`: `anthropic` (default) or `openai`
- `PIPELINE_MODEL`: e.g. `claude-haiku-4-5`, `claude-opus-4-6`, `gpt-5`, `gpt-5-nano`
- `PIPELINE_LIMIT`: Max URLs to process (0 = all)

Example: `make pipeline-extract PIPELINE_MODEL=claude-opus-4-6 PIPELINE_LIMIT=5`

## Extraction Modes

**Batch** (Anthropic only): Submit all items, poll for results. 50% cheaper, no rate limits. Default for Anthropic.
**Sync**: Sequential with exponential backoff. Required for OpenAI. Use `--limit` for testing.

Resume a batch: `python scripts/pipeline_extract.py --poll msgbatch_abc123`

## Store Workflow

ALWAYS dry-run first:
1. `make pipeline-store` -- preview what will be created/matched/flagged
2. Review the output: check created vs flagged counts
3. `make pipeline-store-commit` -- commit to DB

## Resolution Strategy

The resolver (`src/drift/pipeline/resolution/resolver.py`) matches extracted data to DB entities:

**Manufacturer**: normalize -> exact match name/alt_names/EntityAlias -> fuzzy word-overlap
**Caliber**: normalize (strip leading period, expand abbreviations) -> match name/alt_names/EntityAlias
**Bullet** (from cartridges): diameter + weight narrows candidates, name scoring picks best match. Cross-manufacturer matching is supported (Federal loads Sierra bullets). Threshold: name_score > 0.55.

## Common Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| Many `flagged_unresolved` | Manufacturer name mismatch | Add EntityAlias entries |
| Null BC values | Not on product page (e.g. Nosler) | Cross-reference load data section |
| Extraction JSON parse error | LLM copied raw JSON-LD | Check extraction prompt constraints |
| Caliber not found | Missing from seed data | Add to `data/seed.sql` and run `make seed` |
| Wrong bullet_id on cartridge | Name match below threshold | Check abbreviation map in resolver.py |

## File Structure

```
data/pipeline/
├── url_manifest.json           # Master URL list (bullets)
├── url_manifest_cartridges.json # Cartridge URLs
├── fetched/*.html              # Raw HTML + metadata JSON
├── reduced/*.html              # Cleaned HTML for extraction
├── extracted/*.json            # Structured product data
├── batch/*.json                # Anthropic batch metadata
└── review/flagged.json         # Items needing manual review
```

## Reduction Quality by Manufacturer

Pages over 30KB cost more tokens. Sierra/Nosler/Barnes at ~70KB still work but are 2-3x over target. Cutting Edge at ~200KB is problematic. Lapua is cleanest (~27KB).
