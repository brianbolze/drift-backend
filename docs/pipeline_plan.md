# DR-39: Scraping + Extraction Pipeline — Implementation Plan

*March 3, 2026*

## Context

Drift's bundled database has 86 manufacturers and 116 calibers but only 15 bullets, 15 cartridges, and 15 rifle models — all in 6.5 CM and .308 Win. The top 15 long-range calibers need coverage (13 of 15 have zero bullets/cartridges). V1 requires ~150-200 bullets, ~200-300 factory loads, and ~50-80 rifle models across priority calibers.

DR-39 is the pipeline that fills this gap: discover manufacturer/retailer URLs, fetch and reduce HTML, extract structured product data via LLM, resolve entities against the existing DB, and store validated records. The pipeline operates as a set of simple scripts with file-based caching between stages.

### Key Design Decisions
- **No general datapoints abstraction** — BC multi-source tracking uses existing `BulletBCSource` model only
- **Curated seed URLs** via AI deep research (not automated crawling)
- **Simple scripts** for orchestration (no framework)
- **Hallucination protection** via source text anchoring + numeric range validation (see spike findings below)
- **Claude API (Anthropic SDK)** for LLM extraction — Haiku is sufficient as primary model
- **httpx-first fetching** — Firecrawl only as optional fallback; most manufacturer sites embed structured JSON in static HTML
- **Smart HTML reduction** — Remove CSS aggressively, scripts selectively; preserve inline JSON/JSON-LD data
- **pyproject.toml update**: Replace `openai>=1.0` with `anthropic>=0.40`, add `python-dotenv>=1.0` in `[project.optional-dependencies.pipeline]`

### Spike Findings (DR-99)

Tested across 5 manufacturer sites: Hornady, Berger Bullets, Sierra Bullets, Federal Premium, Bergara. Key learnings:

1. **Firecrawl rarely needed.** Hornady (Angular), Berger (WooCommerce), Sierra (BigCommerce), and Federal (Demandware) all embed structured product data as JSON inside inline `<script>` tags in static HTML. httpx alone extracts BC values, specs, SKUs — no JS rendering required.

2. **Smart script categorization is critical.** Blindly removing all `<script>` tags (the original approach) destroyed the richest extraction data. The revised reducer categorizes scripts: external (`src=...`) → always remove; tracking/analytics (gtag, fbq, etc.) → remove; inline with JSON-like data (3+ quoted keys, JSON-LD, `__NEXT_DATA__`) → preserve as data nodes.

3. **CSS class substring selectors are dangerous.** `[class*=modal]` matched Berger's `<body class="...avada-has-boxed-modal-shadow-none...">` and nuked the entire page. Replaced with word-boundary matching that splits on hyphens.

4. **Haiku alone is reliable.** Across all 5 sites, Haiku extracted fields with high confidence (0.85-1.0) and correct source_text anchoring. Multi-model (Haiku + Sonnet) diffing adds cost and complexity without meaningful accuracy gains. Recommend: Haiku primary, Sonnet only for manual re-extraction of flagged items.

5. **Token cost is trivial.** 5K-15K input tokens, 600-750 output tokens per page extraction. At Haiku rates, < $0.01 per page. Running the full V1 manifest (~400 URLs) would cost ~$2-4.

6. **Multi-variant pages work.** Bergara's HMR rifle page lists 7 caliber variants in one spec table; Haiku extracted all of them correctly. Requires max_tokens ≥ 8192 for pages with multiple entities.

---

## Phase 0: Quick Validation Scripts

Before building the full pipeline, we build three small standalone scripts that validate each stage works in isolation. Each can be run manually in ~5 minutes and proves a key assumption.

### V1. `scripts/spike_fetch.py` — Prove fetching works
- Takes a single URL as CLI arg (e.g., a Hornady product page)
- Fetches it with httpx (and optionally Firecrawl if `--firecrawl` flag)
- Prints: status code, content length, first 500 chars of HTML
- Saves raw HTML to `data/pipeline/spike/raw.html`
- **What this validates**: httpx can reach manufacturer sites; Firecrawl API key works; we see the HTML structure we'll be parsing

### V2. `scripts/spike_reduce.py` — Prove HTML reduction works
- Reads `data/pipeline/spike/raw.html` (output of V1)
- Runs the adapted HTML reducer
- Prints: original size → reduced size, reduction ratio
- Saves reduced HTML to `data/pipeline/spike/reduced.html`
- **What this validates**: The reducer preserves product data (specs, BCs, weights) while stripping navigation/chrome; output fits in LLM context window

### V3. `scripts/spike_extract.py` — Prove LLM extraction works
- Reads `data/pipeline/spike/reduced.html` (output of V2)
- Takes `--entity-type bullet|cartridge|rifle` CLI arg
- Sends to Claude Haiku with the extraction prompt + schema
- Prints: extracted JSON with source_text for each field
- Saves to `data/pipeline/spike/extracted.json`
- **What this validates**: Claude can parse reduced HTML into structured product data; source_text anchoring works; confidence scores are reasonable; the extraction schema is complete enough

**Suggested order**: Run V1 → V2 → V3 on a known Hornady 6.5 CM ELD Match bullet page. Then try V1 → V2 → V3 on a different manufacturer (e.g., Sierra, Berger) to check generalization. Total: ~30 min of manual testing.

These three scripts become the foundation for the real pipeline scripts (C1, D2) — they're not throwaway, they get promoted into the full implementation.

---

## Workstream A: Infrastructure

### A1. Pipeline config and constants
Create `src/drift/pipeline/config.py`:
- Pydantic Settings class for API keys (`FIRECRAWL_API_KEY`, `ANTHROPIC_API_KEY`) loaded from `.env`
- Cache directory paths (`data/pipeline/fetched/`, `data/pipeline/reduced/`, `data/pipeline/extracted/`)
- Numeric validation ranges (e.g., BC: 0.05–1.2; MV: 400–4000 fps; weight: 15–750 gr; barrel: 10–34 inches)
  - MV floor at 400 fps covers subsonic calibers (.300 BLK, 8.6 BLK, .22 LR)
- Controlled vocabulary constants for `type_tags`, `used_for`, `base_type`, `tip_type` (from wi2 design proposal addendum §2)

### A2. Fetching backends
Create `src/drift/pipeline/fetching/`:
- `httpx.py` — `HttpxFetcher` with browser-like headers, 30s timeout, redirect following (proven in spike)
- `firecrawl.py` — `FirecrawlFetcher` as optional fallback for truly client-rendered SPAs (v4 API: `app.scrape(url, formats=["html"])`)
- `schemas.py` — `FetchResult` Pydantic model: `url`, `html`, `status_code`, `fetched_at`, `fetcher_backend`, `content_hash`

**Spike finding**: httpx-first is sufficient for all tested manufacturer sites (Hornady/Angular, Berger/WooCommerce, Sierra/BigCommerce, Federal/Demandware). Firecrawl is only needed if a site truly has zero product data in static HTML. No domain→fetcher mapping needed — just try httpx, fall back to Firecrawl on empty extraction.

### A3. HTML reducer
Create `src/drift/pipeline/reduction/`:
- `reducer.py` — `HtmlReducer` class (promoted from `scripts/spike_reduce.py`)
- **Key principle: remove CSS aggressively, scripts selectively**
- Step order: styles → smart script removal (categorize: external/tracking/data-bearing) → noscript → comments → nav chrome → widgets (word-boundary class matching) → images → SVGs → attrs → sidebars → forms → empty containers
- Preserves: JSON-LD (`application/ld+json`), inline scripts with JSON data (3+ quoted keys), `__NEXT_DATA__` / framework bootstrap, `<meta>` tags (og:*, product:*)
- Word-boundary class matching (`_remove_by_class_word`) instead of `[class*=X]` CSS selectors to avoid nuking `<body>`
- Target ~30KB for LLM context; output: reduced HTML string + reduction metadata

### A4. Extraction schemas (Pydantic)
Create `src/drift/pipeline/extraction/schemas.py`:

Core wrapper for every extracted field:
```python
class ExtractedValue(BaseModel, Generic[T]):
    value: T
    source_text: str          # exact snippet from the HTML that supports this value
    confidence: float          # 0.0–1.0, LLM self-assessed
```

Entity schemas (each field is `ExtractedValue[T]`):
- `ExtractedBullet` — name, manufacturer, caliber, weight_grains, bc_g1, bc_g7, length_inches, sectional_density, base_type, tip_type, type_tags, used_for
- `ExtractedCartridge` — name, manufacturer, caliber, bullet_name, bullet_weight_grains, muzzle_velocity_fps, test_barrel_length_inches, round_count, product_line, sku
- `ExtractedRifleModel` — model, manufacturer, chamber/caliber, barrel_length_inches, twist_rate, weight_lbs, barrel_material, barrel_finish, model_family
- `ExtractedBCSource` — bullet_name, bc_type (g1/g7), bc_value, source, source_methodology

All schemas follow the project's Pydantic patterns from `docs/python-code-patterns.md` (localized `Fields` class, `BaseSchema` config).

---

## Workstream B: Discovery

### B1. Shopping list generator
Create `scripts/generate_shopping_list.py`:
- Queries the DB for calibers ordered by `lr_popularity_rank` (then `overall_popularity_rank`)
- For each caliber, counts existing bullets, cartridges, rifle models
- Outputs a structured JSON "shopping list" with gaps and priorities:
  ```json
  {
    "calibers": [
      {
        "name": "6mm Dasher", "lr_rank": 2, "overall_rank": 53,
        "bullets": {"have": 0, "target": 10},
        "cartridges": {"have": 0, "target": 8},
        "rifle_models": {"have": 0, "target": 4}
      }
    ],
    "manufacturers": [
      {"name": "Hornady", "website_url": "https://www.hornady.com", "type_tags": ["bullet", "ammo"]}
    ]
  }
  ```
- Target counts derived from caliber popularity tier (LR top 5 → more coverage, etc.)

### B2. URL manifest format and seed file
Define `data/pipeline/url_manifest.json` schema:
```json
[
  {
    "url": "https://www.hornady.com/bullets/eld-match/6.5mm-264-140-gr-eld-match",
    "entity_type": "bullet",
    "expected_caliber": "6.5 Creedmoor",
    "expected_manufacturer": "Hornady",
    "source_type": "manufacturer",
    "discovery_method": "ai_research",
    "priority": 1
  }
]
```

The initial manifest is produced by an AI deep research agent given:
1. The shopping list from B1
2. The existing manufacturer table (with website_url)
3. Instructions to find product pages (not category pages) for each gap

A `scripts/validate_manifest.py` script validates the manifest (URL format, required fields, deduplication).

---

## Workstream C: Fetch + Reduce

### C1. Fetch and reduce script
Create `scripts/pipeline_fetch.py`:
- Reads `data/pipeline/url_manifest.json`
- For each URL:
  1. Check cache (`data/pipeline/fetched/{url_hash}.json`) — skip if fresh
  2. Fetch via `FetcherRegistry` (httpx first, Firecrawl fallback for JS-rendered sites)
  3. Save raw fetch result to cache
  4. Reduce HTML via `HtmlReducer`
  5. Save reduced HTML to `data/pipeline/reduced/{url_hash}.json`
- Rate limiting: configurable delay between Firecrawl calls (default 1s)
- Resume-safe: skips already-fetched URLs based on cache files
- Output: summary of fetched/skipped/failed counts

---

## Workstream D: Extract + Validate

### D1. LLM extraction engine
Create `src/drift/pipeline/extraction/engine.py`:
- `ExtractionEngine` class that takes reduced HTML + entity_type → `ExtractedBullet | ExtractedCartridge | ExtractedRifleModel`
- System prompt templates per entity type (bullet, cartridge, rifle_model) with:
  - Schema definition with full JSON examples (proven effective in spike — Haiku follows the structure exactly)
  - Controlled vocabulary for enums (type_tags, base_type, tip_type, used_for)
  - Instruction to cite `source_text` for every field
  - Instruction to return confidence scores
  - Rules: only extract explicit data, null for missing fields, no hallucination
- Uses Anthropic SDK (`anthropic` Python client), default model: `claude-haiku-4-5-20251001`
- **Single-model primary extraction**: Haiku is sufficient based on spike testing across 5 sites. Sonnet available via `--model` flag for manual re-extraction of flagged items only.
- **Numeric range validation**: Post-extraction check against ranges from A1 config — any out-of-range value flagged for review
- **BC-specific extraction**: When entity_type is bullet, also extracts BC data into `ExtractedBCSource` entries for the multi-source audit trail
- **max_tokens=8192**: Required for multi-variant pages (e.g., Bergara HMR with 7 caliber variants)
- **JSON fallback parser**: Handles markdown-fenced code blocks (` ```json ``` `) which Haiku sometimes emits

### D2. Extraction script
Create `scripts/pipeline_extract.py`:
- Reads reduced HTML from `data/pipeline/reduced/`
- For each file, runs `ExtractionEngine`
- Saves extraction results to `data/pipeline/extracted/{url_hash}.json`
- Flags disagreements and validation failures in a `data/pipeline/review/flagged.json` file
- Resume-safe: skips already-extracted URLs
- Output: summary of extracted/flagged/failed counts

---

## Workstream E: Entity Resolution + Store

### E1. Entity resolver
Create `src/drift/pipeline/resolution/resolver.py`:
- `EntityResolver` class with tiered matching:
  1. **Exact SKU match** — if extracted SKU matches existing `bullet.sku` or `cartridge.sku`
  2. **Composite key match** — manufacturer + caliber + weight + name substring
  3. **Fuzzy name match** — Levenshtein distance on name, weighted by manufacturer match
- Resolution for FK references:
  - `manufacturer` — match by name or alt_names (already 86 manufacturers in DB)
  - `caliber` — match by name or alt_names (already 116 calibers)
  - `chamber` — match by name or alt_names (117 chambers)
  - `bullet` (for cartridge→bullet FK) — match by manufacturer + caliber + weight + name
- Returns match confidence score and match method for each resolution
- Unresolved references flagged for review

### E2. Store script
Create `scripts/pipeline_store.py`:
- Reads extraction results from `data/pipeline/extracted/`
- Runs `EntityResolver` to link to existing entities and detect duplicates
- For new entities: creates DB records with `source_url`, `extraction_confidence`
- For existing entities: reports matches (does NOT auto-update — human decision)
- For bullets with BC data: creates `BulletBCSource` rows
- Writes results to `data/pipeline/store_report.json` (created/matched/flagged counts per entity type)
- **Dry-run mode** (`--dry-run`): resolves and reports without writing to DB

---

## Workstream F: Human Review

### F1. Review CLI
Create `scripts/pipeline_review.py`:
- Interactive CLI that reads `data/pipeline/review/flagged.json`
- For each flagged item, shows: extracted values, source text snippets, disagreements, validation failures
- Actions: approve (store as-is), edit (modify values), skip (defer), reject (discard)
- Approved items written back to extraction results for `pipeline_store.py` to process

### F2. Coverage dashboard
Create `scripts/pipeline_status.py`:
- Queries the DB and reports current coverage vs. V1 targets
- Output table: caliber | bullets (have/target) | cartridges (have/target) | rifle_models (have/target)
- Highlights gaps in priority calibers
- Shows pipeline progress: URLs in manifest, fetched, extracted, stored

---

## Workstream G: Integration

### G1. Makefile targets
Add to `Makefile`:
```makefile
pipeline-fetch:
	$(VENV)/python scripts/pipeline_fetch.py

pipeline-extract:
	$(VENV)/python scripts/pipeline_extract.py

pipeline-store:
	$(VENV)/python scripts/pipeline_store.py --dry-run

pipeline-store-commit:
	$(VENV)/python scripts/pipeline_store.py

pipeline-review:
	$(VENV)/python scripts/pipeline_review.py

pipeline-status:
	$(VENV)/python scripts/pipeline_status.py

shopping-list:
	$(VENV)/python scripts/generate_shopping_list.py
```

### G2. E2E smoke test
Create `tests/pipeline/test_extraction_e2e.py`:
- Uses a fixture HTML file (saved from a real Hornady product page)
- Tests the full path: reduce → extract → validate → resolve
- Asserts extracted values are within expected ranges
- Asserts source_text is present for all fields
- Asserts entity resolution finds existing Hornady manufacturer and 6.5 CM caliber

---

## File Structure Summary

```
src/drift/pipeline/
├── __init__.py                    (exists, empty)
├── config.py                      (A1)
├── fetching/
│   ├── __init__.py
│   ├── base.py                    (A2)
│   ├── firecrawl.py               (A2)
│   ├── httpx.py                   (A2)
│   ├── registry.py                (A2)
│   └── schemas.py                 (A2)
├── reduction/
│   ├── __init__.py
│   └── reducer.py                 (A3)
├── extraction/
│   ├── __init__.py
│   ├── schemas.py                 (A4)
│   └── engine.py                  (D1)
└── resolution/
    ├── __init__.py
    └── resolver.py                (E1)

scripts/
├── spike_fetch.py                 (V1 - validation)
├── spike_reduce.py                (V2 - validation)
├── spike_extract.py               (V3 - validation)
├── generate_shopping_list.py      (B1)
├── validate_manifest.py           (B2)
├── pipeline_fetch.py              (C1)
├── pipeline_extract.py            (D2)
├── pipeline_store.py              (E2)
├── pipeline_review.py             (F1)
├── pipeline_status.py             (F2)
├── seed_db.py                     (exists)
├── dump_seed.py                   (exists)
└── describe_db.py                 (exists)

data/pipeline/
├── spike/                         (V1-V3 - validation outputs)
├── url_manifest.json              (B2 - seed URLs)
├── fetched/                       (C1 - raw HTML cache)
├── reduced/                       (C1 - reduced HTML cache)
├── extracted/                     (D2 - extraction results)
├── review/
│   └── flagged.json               (D2 - items needing review)
└── store_report.json              (E2 - store results)

tests/pipeline/
└── test_extraction_e2e.py         (G2)
```

---

## Existing Code to Reuse

| What | Where | How |
|------|-------|-----|
| Base model, UUID helpers, timestamps | `src/drift/models/base.py` | All new DB writes use existing `uuid_pk()`, `TimestampMixin` |
| Bullet model + BulletBCSource | `src/drift/models/bullet.py` | Store script creates Bullet rows and BulletBCSource rows |
| Cartridge model | `src/drift/models/cartridge.py` | Store script creates Cartridge rows with `bullet_match_confidence/method` |
| RifleModel model | `src/drift/models/rifle_model.py` | Store script creates RifleModel rows |
| Manufacturer model | `src/drift/models/manufacturer.py` | Entity resolver matches manufacturers by name/alt_names |
| DB session factory | `src/drift/database.py` | All scripts use `get_session_factory()` |
| Pydantic patterns | `docs/python-code-patterns.md` | Extraction schemas follow `Fields` class pattern, `BaseSchema` config |

---

## Linear Subtasks (under DR-39)

| # | Title | Workstream | Estimate |
|---|-------|-----------|----------|
| 1 | Spike: fetch + reduce + extract validation scripts | V1-V3 | M |
| 2 | Pipeline config, constants, and .env setup | A1 | S |
| 3 | Extraction schemas (ExtractedValue, entity schemas) | A4 | M |
| 4 | Fetching backends (Firecrawl + httpx) | A2 | M |
| 5 | HTML reducer (adapt Doro reducer_v4) | A3 | M |
| 6 | Shopping list generator script | B1 | S |
| 7 | URL manifest format + validation script | B2 | S |
| 8 | Fetch + reduce script with caching | C1 | M |
| 9 | LLM extraction engine (multi-model + validation) | D1 | L |
| 10 | Extraction script | D2 | M |
| 11 | Entity resolver (tiered matching) | E1 | L |
| 12 | Store script (dry-run + commit modes) | E2 | M |
| 13 | Review CLI for flagged items | F1 | M |
| 14 | Coverage dashboard script | F2 | S |
| 15 | Makefile targets | G1 | S |
| 16 | E2E smoke test | G2 | M |

**Suggested execution order:** V1-V3 → A1 → A4 → A2 → A3 → B1 → B2 → C1 → D1 → D2 → E1 → E2 → F1 → F2 → G1 → G2

The spike scripts (V1-V3) come first — they validate assumptions before we invest in the full infrastructure. Once the spikes pass, A1-A4 build the reusable components, then the pipeline scripts (B-F) wire them together.

---

## Verification

1. **Unit**: Run `make test` — new tests in `tests/pipeline/` pass
2. **Lint**: Run `make lint` — all new code passes black/isort/flake8
3. **Shopping list**: `make shopping-list` outputs JSON with caliber gaps matching `docs/db_summary.md` coverage gaps
4. **E2E smoke test**: `pytest tests/pipeline/test_extraction_e2e.py -v` — full reduce→extract→validate→resolve path works on fixture HTML
5. **Dry run**: `make pipeline-store` (dry-run) resolves entities without writing to DB, reports expected matches
6. **Coverage**: `make pipeline-status` shows current DB state and pipeline progress
