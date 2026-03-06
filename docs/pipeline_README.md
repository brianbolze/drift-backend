# Data Pipeline

Automated pipeline for discovering, fetching, and extracting ballistics product data from manufacturer websites.

## Quick Start

```bash
# Install pipeline dependencies
make pipeline-install

# Run the complete pipeline
make pipeline-all                    # Dry-run mode (preview only)
make pipeline-store-commit           # Commit to database
```

## Pipeline Stages

### 1. Generate Shopping List

Analyze the database to identify gaps (missing bullets, cartridges, rifles):

```bash
make pipeline-shopping-list
# Output: data/pipeline/shopping_list.json
```

This snapshots current database coverage and calculates what data is missing. The shopping list drives prompt generation by identifying which calibers need more products.

### 2. Generate CoWork Prompts

Generate research prompts for Claude CoWork agents to discover product URLs:

```bash
# Generate prompts for all manufacturers
make pipeline-cowork-prompts
# Output: data/pipeline/cowork_prompts/*.txt
```

**Manual step**: Run CoWork research
1. Open CoWork (requires Chrome access for domain mapping)
2. Copy a prompt from `data/pipeline/cowork_prompts/`
3. Paste into CoWork and run research
4. Save JSON output to `data/pipeline/[manufacturer]_[entity_type].json`

Example: `data/pipeline/hornady_bullets.json`

### 3. Merge CoWork Results

Add CoWork-discovered URLs to the manifest:

```bash
# Interactive merge (prompts for file path)
make pipeline-merge-cowork

# Or merge directly
python scripts/merge_cowork_results.py data/pipeline/hornady_bullets.json

# Batch merge multiple files
python scripts/merge_cowork_results.py data/pipeline/*.json

# Dry-run to preview
python scripts/merge_cowork_results.py data/pipeline/hornady_bullets.json --dry-run
```

This adds required fields (`priority`, `source_type`, `discovery_method`) and deduplicates against the existing manifest.

### 4. Validate Manifest

```bash
make pipeline-validate
```

Checks `url_manifest.json` structure and required fields.

### 5. Fetch HTML

```bash
make pipeline-fetch
```

Downloads HTML from all URLs in the manifest. Uses plain HTTP (no browser automation needed for most manufacturers).

**Output**: `data/pipeline/fetched/*.html` and `data/pipeline/reduced/*.html`

### 6. Extract Structured Data

Extract product specs using LLM:

```bash
# Auto-detect provider/mode (batch for Anthropic, sync for OpenAI)
make pipeline-extract

# Use specific provider
make pipeline-extract-anthropic      # Batch mode (50% cheaper, no rate limits)
make pipeline-extract-openai         # Sync mode

# Use specific model
make pipeline-extract PIPELINE_MODEL=claude-opus-4-6
make pipeline-extract PIPELINE_MODEL=gpt-5-nano

# Limit URLs (for testing)
make pipeline-extract PIPELINE_LIMIT=10

# Resume a batch
python scripts/pipeline_extract.py --poll msgbatch_abc123
```

**Output**: `data/pipeline/extracted/*.json`

**Flagged items**: Items with validation warnings are written to `data/pipeline/review/flagged.json`

### 7. Review Results

```bash
# List extraction results
make pipeline-review

# Check pipeline status
make pipeline-status
```

Review flagged items for:
- Missing critical specs (e.g., BC values not on product page)
- Out-of-range values
- Parse errors

### 8. Store in Database

```bash
# Dry-run (preview what will be added)
make pipeline-store

# Commit to database
make pipeline-store-commit
```

Stores extracted entities in the database. Each new record gets a `data_source` tag ("pipeline", "cowork", or "manual") for provenance tracking. Records with `is_locked = 1` are skipped entirely — the store report shows these as "skipped (locked)".

**Locking manually curated records:**
```sql
UPDATE bullet SET is_locked = 1, data_source = 'manual', last_verified_at = datetime('now') WHERE id = '...';
```

This prevents pipeline re-runs from overwriting your corrections.

## File Structure

```
data/pipeline/
├── shopping_list.json          # Database gap analysis (drives prompt generation)
├── url_manifest.json           # Master list of URLs to process
├── cowork_prompts/             # Generated CoWork research prompts
│   ├── 01_bullet_berger_bullets.txt
│   ├── 02_bullet_hornady.txt
│   └── ...
├── fetched/                    # Raw HTML downloads
│   ├── abc123.html
│   └── abc123.json             # Metadata
├── reduced/                    # Cleaned HTML for extraction
│   ├── abc123.html
│   └── abc123.json
├── extracted/                  # Structured product data
│   └── abc123.json
├── batch/                      # Anthropic batch metadata
│   └── msgbatch_abc123.json
└── review/                     # Flagged items for manual review
    └── flagged.json
```

## URL Manifest Format

```json
[
  {
    "url": "https://example.com/bullets/6.5mm-140gr-eld-match",
    "entity_type": "bullet",
    "expected_manufacturer": "Hornady",
    "expected_caliber": "6.5mm",
    "brief_description": "140gr ELD Match",
    "confidence": "high",
    "priority": 1,
    "source_type": "manufacturer",
    "discovery_method": "cowork_research",
    "notes": "Complete specs visible on product page"
  }
]
```

## Key Concepts

### Entity Types
- `bullet` - Component bullets/projectiles
- `cartridge` - Factory-loaded ammunition
- `rifle` - Rifle models

### CoWork Research
- Uses manufacturer-centric approach: one prompt per manufacturer covering all calibers
- CoWork agent has domain mapping tool for exploring site structure
- Multi-variant pages (one URL, multiple weights) are handled by extraction engine

### Extraction Modes
- **Batch** (Anthropic only): Submit all items as batch, poll for results. 50% cheaper, no rate limits.
- **Sync**: Sequential extraction with retry logic. Required for OpenAI.

### Missing Data
- Extraction handles missing fields gracefully (sets to null)
- Items with warnings are flagged for review
- Example: Nosler BCs are in load data section, not product pages → flagged with null BC values

### Data Provenance & Curation
- `data_source` on bullet/cartridge/rifle_model tracks where data came from: "pipeline" (API extraction), "cowork" (CoWork agent), or "manual" (human edit)
- `is_locked` prevents the pipeline store from modifying a record — use this after manual corrections
- Extraction JSON can include `"data_source": "cowork"` in the top-level envelope to tag CoWork-sourced entities

## Troubleshooting

**No URLs extracted**:
```bash
# Check manifest has entries
cat data/pipeline/url_manifest.json | jq '. | length'

# Validate manifest structure
make pipeline-validate
```

**Extraction failing**:
```bash
# Check API keys
make pipeline-env-check

# List available models
make pipeline-models

# Try with limit
make pipeline-extract PIPELINE_LIMIT=1
```

**Batch timeout**:
```bash
# Resume polling with batch ID
python scripts/pipeline_extract.py --poll msgbatch_abc123
```

## Next Steps

After completing the pipeline:
1. Review flagged items: `data/pipeline/review/flagged.json`
2. For items with missing BCs, cross-reference manufacturer load data
3. Run pipeline again for remaining manufacturers
4. Generate shopping list to see coverage: `make pipeline-shopping-list`
