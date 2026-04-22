# Data Pipeline

How ballistics data gets into Drift: from manufacturer URL to SQLite row bundled with the iOS app.

## Mental Model

The pipeline turns an unstructured web into a structured, bundled database. Each run moves items through seven stages:

```
MANIFEST  →  FETCH  →  REDUCE  →  EXTRACT  →  NORMALIZE  →  RESOLVE  →  STORE
   ↓          ↓         ↓          ↓           ↓             ↓          ↓
 URLs      raw HTML   clean HTML  raw JSON   unit-fixed   matched   drift.db
                                             entities     to DB     rows
```

Two properties hold throughout:

- **Everything is cached on disk, keyed by `url_hash`** (first 16 hex chars of SHA-256). Re-running any stage reuses cached outputs unless you explicitly invalidate them. This is what makes iterating on the reducer or the extractor tractable.
- **Stages are additive, not idempotent across pipeline runs.** STORE writes new rows on each successful match/create, and records with `is_locked = 1` are never modified. Dry-run (`make pipeline-store`) is the guardrail — always run it first.

After the pipeline, a separate workflow turns `drift.db` into what ships to users:

```
drift.db  →  curation patches  →  export_production_db  →  publish_db  →  R2 CDN  →  iOS app
```

Curation, export, and publish are documented briefly at the bottom; detailed notes live in [CLAUDE.md](../CLAUDE.md).

---

## Typical Workflow

A full end-to-end run, starting from "I want to add 50 more 6.5 Creedmoor cartridges":

```bash
# 1. Find gaps
make pipeline-shopping-list            # data/pipeline/shopping_list.json

# 2. Discover URLs (via Claude CoWork — manual step, see below)
make pipeline-cowork-prompts
#    → paste prompt into CoWork, save output as data/pipeline/hornady_cartridges.json
python scripts/merge_cowork_results.py data/pipeline/hornady_cartridges.json

# 3. Validate the manifest
make pipeline-validate

# 4. Fetch + reduce HTML (one step)
make pipeline-fetch

# 5. Extract structured data with an LLM
make pipeline-extract                  # batch mode (Anthropic, 50% cheaper)

# 6. Preview what will land in the DB
make pipeline-store                    # DRY-RUN — always do this first

# 7. Commit
make pipeline-store-commit

# 8. Check flagged items
make pipeline-review                   # lists flagged extractions + low-confidence matches
```

To ship changes to the iOS app afterwards:

```bash
make export-production-db              # strips pipeline metadata, filters bad rows
make publish-db CHANGELOG="..."        # dry-run
make publish-db-commit CHANGELOG="..." # upload to R2
```

---

## Stages

### 1. MANIFEST

The manifest is a JSON array of URLs to process, with expected entity metadata for sanity-checking during extraction.

**File**: [`data/pipeline/url_manifest.json`](../data/pipeline/url_manifest.json)

**Schema** (enforced by [`scripts/validate_manifest.py`](../scripts/validate_manifest.py)):

| Field | Required | Valid values |
|---|---|---|
| `url` | yes | http(s) URL |
| `entity_type` | yes | `bullet`, `cartridge`, `rifle` |
| `expected_manufacturer` | yes | manufacturer name (free text) |
| `expected_caliber` | no | caliber name (free text) |
| `priority` | no | integer |
| `source_type` | no | `manufacturer`, `retailer`, `review`, `reference` |
| `discovery_method` | no | `ai_research`, `manual`, `crawl`, `known`, `cowork_research` |
| `brief_description`, `confidence`, `notes` | no | free text (from CoWork output) |

The validator also deduplicates URLs and prints a tally by entity type and manufacturer.

**How URLs get into the manifest**:

1. **Shopping list → CoWork → merge** (the primary path)
   - [`scripts/generate_shopping_list.py`](../scripts/generate_shopping_list.py) analyzes current DB coverage vs. target counts per caliber tier (LR Top 5, LR Top 10, etc.). Output: [`data/pipeline/shopping_list.json`](../data/pipeline/shopping_list.json).
   - [`scripts/generate_cowork_prompts.py`](../scripts/generate_cowork_prompts.py) writes per-manufacturer research prompts to `data/pipeline/cowork_prompts/NN_entitytype_manufacturer.{txt,json}`.
   - A human runs each prompt inside Claude CoWork (which has a domain-mapping tool) and saves the JSON output to `data/pipeline/<manufacturer>_<entity>.json`.
   - [`scripts/merge_cowork_results.py`](../scripts/merge_cowork_results.py) enriches each entry with `priority`, `source_type=manufacturer`, `discovery_method=cowork_research`, then dedupes against the existing manifest and appends.

2. **Direct editing** — for one-off URLs, edit `url_manifest.json` by hand with `discovery_method: "manual"`.

**Commands**:
```bash
make pipeline-shopping-list
make pipeline-cowork-prompts
python scripts/merge_cowork_results.py <cowork_output.json> [--dry-run]
make pipeline-validate
```

---

### 2. FETCH

Downloads raw HTML for every URL in the manifest and immediately runs the reducer (stage 3). One command, two outputs per URL.

**Entry point**: [`scripts/pipeline_fetch.py`](../scripts/pipeline_fetch.py) → [`src/drift/pipeline/fetching/`](../src/drift/pipeline/fetching/)

**Fetcher strategy** (registry at [`fetching/registry.py`](../src/drift/pipeline/fetching/registry.py)):

1. Try `HttpxFetcher` — plain HTTP with browser-like headers. 30s timeout, 3 retries with exponential backoff.
2. If the response is ≥ HTTP 400 **or** the HTML is under 500 chars, fall back to `FirecrawlFetcher` (uses `FIRECRAWL_API_KEY`). Handles sites that require JS rendering.

**Rate limiting**: 1.0s delay between requests (`FIRECRAWL_RATE_LIMIT_SECONDS` in [`config.py`](../src/drift/pipeline/config.py), applied to all fetchers). Override with `--delay`.

**Outputs**:
- [`data/pipeline/fetched/<url_hash>.html`](../data/pipeline/fetched/) — raw HTML
- `data/pipeline/fetched/<url_hash>.json` — `{status_code, fetcher_backend, fetched_at, content_hash, html_size}`

**Resume behavior**: Skips URLs that already have `reduced/<url_hash>.json` on disk. To force a re-fetch, delete the files.

**Commands**:
```bash
make pipeline-fetch
python scripts/pipeline_fetch.py --delay 2.0            # slower rate
python scripts/pipeline_fetch.py --rereduce             # re-run reducer without re-fetching
python scripts/pipeline_fetch.py --rereduce --domain barnesbullets.com
```

---

### 3. REDUCE

LLMs have limited context and pay per token. Most manufacturer HTML is 10–100× larger than the useful product info. The reducer strips everything that isn't product content.

**Entry point**: [`src/drift/pipeline/reduction/reducer.py`](../src/drift/pipeline/reduction/reducer.py), invoked inline by `pipeline_fetch.py`.

**Three strategies**, selected per-domain in [`config.py:DOMAIN_REDUCER_STRATEGY`](../src/drift/pipeline/config.py):

| Strategy | When to use | Behavior |
|---|---|---|
| `generic` | Default for all domains | 14-step progressive stripping: removes `<script>` (except JSON-LD / framework bootstraps), `<style>`, `<svg>`, nav, footer, ads, comments. Keeps structural tags and a whitelist of attributes. |
| `main_content` | Sites with a clean `<main>` element (Barnes, Berger, Swift, Nosler, Cutting Edge, Lehigh) | Extracts `<main>` (or a custom CSS selector from `DOMAIN_CONTENT_SELECTORS`) plus JSON-LD blocks. |
| `jsonld_only` | SPAs whose rendered HTML is useless (Norma) | Keeps only JSON-LD `<script>` tags and `<meta>` tags. |

**Tuning**:
- Target size: 30,000 chars (`REDUCE_TARGET_SIZE`)
- Floor: 6,000 chars (`REDUCE_MIN_SIZE`) — below this we may have over-stripped; reduction metadata records `under_target: true` for follow-up.

**Outputs**:
- [`data/pipeline/reduced/<url_hash>.html`](../data/pipeline/reduced/) — reduced HTML
- `data/pipeline/reduced/<url_hash>.json` — entity metadata + `reduction_meta` (strategy used, size, ratio)

**Iterating on a reducer**: edit `DOMAIN_REDUCER_STRATEGY` or the reducer code, then `make pipeline-fetch` with `--rereduce --domain <domain>` to regenerate reductions without touching the network.

---

### 4. EXTRACT

LLM-driven structured extraction. Sends reduced HTML + a per-entity-type prompt to Claude or GPT, parses the JSON response into typed Pydantic models.

**Entry point**: [`scripts/pipeline_extract.py`](../scripts/pipeline_extract.py)
**Engine**: [`src/drift/pipeline/extraction/engine.py`](../src/drift/pipeline/extraction/engine.py)
**Batch orchestration**: [`src/drift/pipeline/extraction/batch.py`](../src/drift/pipeline/extraction/batch.py)
**Schemas**: [`src/drift/pipeline/extraction/schemas.py`](../src/drift/pipeline/extraction/schemas.py)
**Providers**: [`extraction/providers/`](../src/drift/pipeline/extraction/providers/) (`anthropic_provider.py`, `openai_provider.py`, `factory.py`)

**Two modes**:

| Mode | Provider | Use when |
|---|---|---|
| **Batch** (default for Anthropic) | Anthropic Message Batches API | Production runs. 50% cheaper, no rate-limit exposure. Submits all items, polls every 30s, up to 1 hour total. Resumable via `--poll <batch_id>`. |
| **Sync** (required for OpenAI) | Either | Small test runs, OpenAI models. Sequential with up to 5 retries and exponential backoff (2s → 32s). Breaks after 3 consecutive failures. |

**Models** (defaults in [`config.py`](../src/drift/pipeline/config.py)):
- Default: `claude-haiku-4-5-20251001`
- Fallback: `claude-sonnet-4-20250514`
- Max output tokens: 8192 (needed for multi-variant pages like Bergara HMR with 7 caliber variants)

**Extracted schema** per entity type. Every field is wrapped in `ExtractedValue[T]` carrying `{value, source_text, confidence}` so we can trace each field back to a specific HTML snippet.

- **Bullet**: name, manufacturer, diameter, weight, BC G1/G7, length (bullet, not cartridge OAL), sectional density, base_type, tip_type, type_tags, used_for, product_line, sku
- **Cartridge**: name, manufacturer, caliber, bullet_name, bullet weight/length, BC G1/G7, muzzle velocity, test barrel length, round count, product_line, sku
- **Rifle**: model, manufacturer, caliber, barrel length/material/finish, twist rate, weight, model_family

**Schema versioning**: each entity has a `schema_version` ([`extraction/schemas.py`](../src/drift/pipeline/extraction/schemas.py)). Bump it to force re-extraction of cached items. Cartridge is currently v2 (added BC fields in v2).

**Outputs**:
- [`data/pipeline/extracted/<url_hash>.json`](../data/pipeline/extracted/) — `{url, url_hash, entity_type, schema_version, model, usage, entity_count, entities, bc_sources, warnings}`
- `data/pipeline/batches/<batch_id>.json` — batch metadata for resumability
- [`data/pipeline/review/flagged.json`](../data/pipeline/review/flagged.json) — cumulative list of items with validation warnings

**Re-extraction triggers** (automatic):
- Cached result has `entity_count: 0`
- Cached `schema_version` is older than current
- `--reextract` flag forces ignore cache

**Commands**:
```bash
make pipeline-extract                                   # batch, Anthropic default
make pipeline-extract PIPELINE_LIMIT=5                  # cap pending items
make pipeline-extract PIPELINE_MODEL=claude-opus-4-6
make pipeline-extract-openai                            # sync, OpenAI
make pipeline-extract-parallel                          # both providers, compare outputs
python scripts/pipeline_extract.py --poll msgbatch_abc  # resume a batch
python scripts/pipeline_extract.py --reextract          # ignore cache
```

---

### 5. NORMALIZE

Catches unit-confusion errors before resolution. Runs inline inside `pipeline_store.py` (line [521](../scripts/pipeline_store.py#L521)) — not a separate CLI step.

**Module**: [`src/drift/pipeline/normalization.py`](../src/drift/pipeline/normalization.py)

**Heuristics** (applied when the LLM put a valid number in the wrong unit):

| Field | Out-of-range triggers | Conversion |
|---|---|---|
| `weight_grains`, `bullet_weight_grains` | < 15 | × 15.4324 (grams → grains) |
| `bullet_diameter_inches`, `length_inches`, `bullet_length_inches` | > 0.510" / > 3.0" | ÷ 25.4 (mm → inches) |
| `muzzle_velocity_fps` | < 400 | × 3.28084 (m/s → fps) |

Valid ranges are in [`config.py:VALIDATION_RANGES`](../src/drift/pipeline/config.py). For each field: if the raw value is in range, pass through; if out of range but conversion recovers it, convert and emit a normalization event; if still out of range, null the field and warn.

**Entity rejection**: if a bullet has an unrecoverable `bullet_diameter_inches` or `weight_grains`, the whole entity is rejected before resolution. This is what prevented the known "Lapua 6,5 g" → 6.5" diameter bug from reoccurring (see [`TODO.md`](../TODO.md) and [`docs/entity_resolution_review.md`](entity_resolution_review.md)).

---

### 6. RESOLVE

Matches each extracted entity against the canonical DB record (if one exists). Produces a `MatchResult` with confidence, method, and runner-up alternatives — the pipeline store uses these to decide whether to match, update, create, or flag.

**Entry point**: [`src/drift/pipeline/resolution/resolver.py`](../src/drift/pipeline/resolution/resolver.py)
**Config**: [`src/drift/pipeline/resolution/config.py`](../src/drift/pipeline/resolution/config.py) (every threshold and confidence scalar, documented inline)
**Alias lookup**: [`src/drift/resolution/aliases.py`](../src/drift/resolution/aliases.py) (shared with curation)

**Tier ladder** — the resolver walks tiers in order and collects all scored candidates before picking the best:

| Tier | Signal | Confidence output |
|---|---|---|
| **1. SKU** | Exact `manufacturer_sku` match | `1.0` (deterministic) |
| **1. EntityAlias** | Exact alias lookup (name normalized) | `1.0` (deterministic) |
| **2. Product line + weight + diameter** (bullets) | Three-way agreement | `0.93` with weight, `0.80` without |
| **2. Composite key** | Manufacturer + diameter/caliber + weight + name similarity ≥ 0.55 | `0.85 + (name_score × 0.1)` → max 0.95 |
| **3. Fuzzy name** | `rapidfuzz.token_set_ratio` ≥ 0.5 | `score × 0.8` if weight agrees (±1gr), `score × 0.4` if not |

Why this order matters: higher tiers have stronger evidence, so a perfect fuzzy-name hit (0.8 confidence max) never beats an alias hit (1.0).

**MatchResult** ([`resolver.py:50-66`](../src/drift/pipeline/resolution/resolver.py#L50)) carries:
- `matched`, `entity_id`, `confidence`, `method`, `details`
- `alternatives` — top 3 runner-ups across all tiers, for ambiguity detection
- `methods_tried` — audit trail of every tier attempted
- `is_ambiguous` (property) — True when confidence gap to runner-up < 0.2 and confidence < 0.97

**ResolutionResult** adds resolved FKs (`manufacturer_id`, `caliber_id`, `chamber_id`, `bullet_id`), `unresolved_refs` (e.g., `"caliber:6.5 Creedmoor"` if not found), and for cartridges, `bullet_match_confidence` + `bullet_match_method` (the bullet-side sub-match is persisted on the Cartridge row).

**Tuning knobs** in [`ResolutionConfig`](../src/drift/pipeline/resolution/config.py):
- `match_confidence_threshold: 0.7` — store action gate. Below this → flagged for review.
- `bullet_fk_min_confidence: 0.5` — cartridge→bullet linkage. Below this, cartridge ships with `bullet_id=None`.
- `bullet_weight_gate_grains: 5.0` — hard reject for cartridge→bullet FK if weights differ by >5gr.
- `auto_create_confidence_ceiling: 0.5` — below this with weight mismatch, auto-create instead of flag.
- `ambiguity_gap_threshold: 0.2` — confidence gap for `is_ambiguous`.
- `alias_auto_promote_threshold: 0.85` — fuzzy-tier alias suggestions above this (and not ambiguous) are written directly on commit instead of deferred to a curation patch.

**Do not retune without running the golden-set regression test** ([`tests/test_resolution_golden_set.py`](../tests/test_resolution_golden_set.py)) before and after. It captures current match accuracy as a baseline.

**Cartridge→bullet BC boost**: when a cartridge's published BC G1/G7 and weight agree with its resolved bullet's values (within `bc_tolerance` / `composite_weight_tolerance_grains`), each matching signal adds `+0.05` confidence, max `+0.15`.

---

### 7. STORE

The policy layer. Walks every extraction JSON, applies normalize → resolve, then decides what to do with each entity.

**Entry point**: [`scripts/pipeline_store.py`](../scripts/pipeline_store.py)

**Action outcomes** (counted per entity type):

| Action | Trigger |
|---|---|
| `matched_existing` | Match confidence ≥ 0.7, existing record not locked |
| `updated` | Matched cartridge, DB row missing `bullet_id`, resolver found one |
| `created` | No match, or weight-mismatched low-confidence fuzzy match → auto-create new variant |
| `skipped_locked` | Matched record has `is_locked = 1`; never overwritten |
| `rejected` | Normalization rejected entity (critical field unrecoverable), or `unresolved_refs` include a caliber in `rejected_calibers.json` (pistol, shotgun, exotic) |
| `flagged_low_confidence` | Matched but confidence < 0.7 |
| `flagged_unresolved` | No match and missing required FK (e.g., cartridge with no bullet_id) |

**Rejected-calibers guard** ([`data/pipeline/rejected_calibers.json`](../data/pipeline/rejected_calibers.json)): ~70 pistol/shotgun/exotic calibers that should never enter the DB. The store auto-rejects any entity whose unresolved refs include one. Edit the JSON to add more.

**Curation protection**:
- `is_locked = 1` → the store skips the record entirely. Use for manually corrected rows.
- `data_source` (`pipeline` / `cowork` / `manual`) → provenance tag written on every new row.

**BC sources**: when creating or updating a bullet, the store also writes [`BulletBCSource`](../src/drift/models/) rows for each BC observation. Deduped by `(bullet_id, bc_type, bc_value ± 1e-9, source)` via `_bc_source_exists()`. For cartridges, the store emits BC sources tagged `source="cartridge_page"`.

**EntityAlias suggestions**: on fuzzy-tier wins, the store proposes adding the extracted name as an alias so the next run hits the deterministic path. Two outcomes:

- **Auto-promoted** (commit mode only) — when the fuzzy match's confidence is strictly above [`alias_auto_promote_threshold`](../src/drift/pipeline/resolution/config.py) (default `0.85`) *and* not ambiguous (runner-up gap ≥ `ambiguity_gap_threshold`), the store inserts the `EntityAlias` row directly with `alias_type="extracted_fuzzy"`. The suggestion entry carries `status: "alias_auto_promoted"` and `alias_id`. Dry-run never auto-promotes.
- **Suggested** — below the gate or ambiguous (or in dry-run mode), the store emits a suggestion with `status: "suggested"` for a curator to apply via an [`add_entity_alias`](../data/patches/014_bullet_product_line_aliases.yaml) patch.

Pre-existing aliases are a no-op either way — `_build_alias_suggestion` filters them out before the gate runs.

**Output**: [`data/pipeline/store_report.json`](../data/pipeline/store_report.json)
```json
{
  "mode": "DRY-RUN" | "COMMIT",
  "stats": { "bullet": {...}, "cartridge": {...}, "rifle": {...} },
  "alias_suggestions": [...],        // status == "suggested" — needs a curator
  "alias_auto_promoted": [...],      // status == "alias_auto_promoted" — already written
  "entries": [{ url, entity_name, matched, match_method, match_confidence,
                action, alias_suggestion, created_id, warnings, ... }]
}
```

**Commands**:
```bash
make pipeline-store                      # DRY-RUN (safe preview)
make pipeline-store-commit               # write to drift.db
python scripts/pipeline_store.py --limit 10 --commit   # bounded commit
```

---

## Post-Pipeline

These aren't part of the pipeline proper but complete the path from `drift.db` to the iOS app. See [CLAUDE.md](../CLAUDE.md) for details.

### Curation
Manual data fixes via YAML patches in [`data/patches/`](../data/patches/) (applied in numbered order, idempotent, locked on write). Operations: `create_bullet`, `create_cartridge`, `create_rifle`, `update_bullet`, `update_cartridge`, `add_bc_source`, `add_entity_alias`. Engine: [`src/drift/curation.py`](../src/drift/curation.py).

```bash
make curate             # dry-run
make curate-commit      # apply
```

### Production export
[`scripts/export_production_db.py`](../scripts/export_production_db.py) creates [`data/production/drift.db`](../data/production/) — strips pipeline-only tables and columns, filters bad rows (zero-MV cartridges, weight-mismatched cartridges, bogus-diameter bullets), flattens aliases, computes display names, VACUUMs.

### OTA publish
[`scripts/publish_db.py`](../scripts/publish_db.py) uploads to Cloudflare R2 at `data.driftballistics.com` with a manifest + PK-stability check (fails if any published primary key changed — would break installed apps). Requires `R2_*` env vars.

---

## Data Directory Layout

```
data/pipeline/
├── url_manifest.json              # stage 1 input/output
├── shopping_list.json             # DB gap analysis
├── rejected_calibers.json         # ~70 excluded calibers (pistol/shotgun/exotic)
├── cowork_prompts/                # generated per-manufacturer research prompts
├── fetched/<url_hash>.{html,json} # raw HTML + metadata (stage 2)
├── reduced/<url_hash>.{html,json} # reduced HTML + reduction metadata (stage 3)
├── extracted/<url_hash>.json      # LLM structured output (stage 4)
├── batches/<batch_id>.json        # Anthropic batch metadata (resumable)
├── review/flagged.json            # cumulative flagged items
├── store_report.json              # latest store run (dry-run or commit)
└── spike/                         # throwaway experiments (not part of main flow)
```

**Cache semantics**: stages read their own outputs if present. To force a re-run of a stage, delete the relevant files (or use `--rereduce` / `--reextract` flags where available). The cache is keyed on `url_hash`, not entity identity, so updating the manifest entry for a URL does **not** invalidate its cached fetch/extract.

---

## Configuration

All pipeline constants live in [`src/drift/pipeline/config.py`](../src/drift/pipeline/config.py). Resolution constants live in [`src/drift/pipeline/resolution/config.py`](../src/drift/pipeline/resolution/config.py).

### Environment variables

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API (extraction) |
| `OPENAI_API_KEY` | GPT API (extraction) |
| `FIRECRAWL_API_KEY` | JS-rendered page fallback (fetch) |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL` | Publish to CDN |
| `PIPELINE_PROVIDER` | `anthropic` (default) or `openai` |
| `PIPELINE_MODEL` | Specific model (see `make pipeline-models`) |
| `PIPELINE_LIMIT` | Max items to process (0 = all) |

Env check: `make pipeline-env-check`.

### Controlled vocabulary

Extraction prompts enforce these enums (source: [`config.py`](../src/drift/pipeline/config.py)):

- `BULLET_TYPE_TAGS`: match, hunting, target, varmint, long_range, tactical, plinking
- `BULLET_USED_FOR`: competition, hunting_{deer,elk,varmint}, long_range, precision, self_defense, plinking
- `BULLET_BASE_TYPES`: boat_tail, flat_base, rebated_boat_tail, hybrid
- `BULLET_TIP_TYPES`: polymer_tip, hollow_point, open_tip_match, fmj, soft_point, ballistic_tip, meplat
- `BC_TYPES`: g1, g7
- `BC_SOURCE_TYPES`: manufacturer, cartridge_page, applied_ballistics, doppler_radar, independent_test, estimated

Add to an enum? Update `config.py` and any prompt strings that embed the list.

---

## Troubleshooting

**No URLs extracted after `make pipeline-extract`**
- `cat data/pipeline/url_manifest.json | jq length` — sanity-check manifest size.
- `make pipeline-validate` — schema errors.
- `make pipeline-env-check` — API keys present.

**Batch polling timed out (1 hour)**
- The batch is still running on Anthropic's side. Resume: `python scripts/pipeline_extract.py --poll <batch_id>`. Batch ID is in the last log line and in `data/pipeline/batches/<batch_id>.json`.

**One domain keeps producing empty or wrong extractions**
- Inspect the reduced HTML: `data/pipeline/reduced/<url_hash>.html`. If it's < 6k chars, reduction over-stripped; tweak the domain's strategy in `DOMAIN_REDUCER_STRATEGY` and re-run reduction only: `python scripts/pipeline_fetch.py --rereduce --domain <domain>`.
- If it's > 80k chars, reduction is leaving noise; consider adding a `main_content` override.

**Store reports many `flagged_unresolved` for cartridges**
- These are usually missing bullet links. Check `entries[].unresolved_refs` for the missing entity. Either (a) add an `EntityAlias` curation patch, (b) add the missing bullet to the manifest and re-run, or (c) curate the cartridge directly.

**Store reports `rejected` entries**
- Legitimate when the caliber is in `rejected_calibers.json` (pistol/shotgun). Unlegitimate when normalization nulled a critical field — check the extraction JSON's `warnings`.

**Extraction cached with 0 entities but HTML looks fine**
- Auto-re-extracts on next run. Or force with `--reextract`.

**Schema change invalidated cached extractions**
- Bump the schema version in [`extraction/schemas.py`](../src/drift/pipeline/extraction/schemas.py). Next run re-extracts stale cache automatically.

---

## Makefile Reference

```
Pipeline discovery & setup
  pipeline-install            Install extraction dependencies
  pipeline-env-check          Verify API keys + installed deps
  pipeline-models             List available LLM models per provider
  pipeline-shopping-list      Analyze DB gaps → shopping_list.json
  pipeline-cowork-prompts     Generate CoWork research prompts
  pipeline-merge-cowork       Interactively merge a CoWork JSON into manifest
  pipeline-validate           Schema-check url_manifest.json

Fetch & extract
  pipeline-fetch              Fetch HTML + run reducer
  pipeline-extract            Extract (Anthropic batch by default)
  pipeline-extract-batch      Force Anthropic batch mode
  pipeline-extract-sync       Force sync mode (required for OpenAI)
  pipeline-extract-poll       Resume a batch by ID
  pipeline-extract-openai     Sync, OpenAI, default model
  pipeline-extract-anthropic  Batch, Anthropic, default model
  pipeline-extract-gpt-5      Sync, GPT-5
  pipeline-extract-gpt-5-nano Sync, GPT-5 nano (fastest/cheapest OpenAI)
  pipeline-extract-claude-4   Batch, Claude Opus 4.6
  pipeline-extract-parallel   Run OpenAI + Anthropic side-by-side

Store & review
  pipeline-store              DRY-RUN store (preview)
  pipeline-store-commit       Commit to drift.db
  pipeline-review             List extractions + flagged items
  pipeline-status             Detailed per-stage status

Full-run + housekeeping
  pipeline-all                Shopping-list → validate → fetch → extract → store (dry-run)
  pipeline-clean              Wipe fetched/reduced/extracted/review/batches caches

Post-pipeline
  curate / curate-commit      Apply YAML curation patches
  export-production-db        Build data/production/drift.db
  publish-db / publish-db-commit  Upload to R2 (OTA)
```

Environment variables (for `make pipeline-extract*`):
```
PIPELINE_PROVIDER=anthropic|openai
PIPELINE_MODEL=<model_id>
PIPELINE_LIMIT=<N>    # 0 = all
```
