# HTML Reducer Strategy Brief

**Date:** 2026-03-19
**Status:** Ready for implementation
**Owner:** TBD

## Problem

The pipeline's HTML reducer uses a single generic strategy for all manufacturer websites. It works well for some (Federal, Winchester) but fails for others, leaving pages 2-7x over the 30KB target. Oversized pages either waste LLM tokens or exceed context limits entirely, blocking extraction.

## Current Reducer

`src/drift/pipeline/reduction/reducer.py` — 14-step progressive reduction that strips tags, attributes, and non-content elements until under 30KB. Key design choice: it preserves inline data scripts (JSON-LD, `__NEXT_DATA__`, etc.) as `<!-- DATA: ... -->` comments.

Target: 30KB (`REDUCE_TARGET_SIZE` in `config.py`). Minimum: 6KB (`REDUCE_MIN_SIZE`).

## Size Analysis (reduced HTML, by domain)

| Domain | Pages | Avg | Max | Over 30KB | Root Cause |
|---|---|---|---|---|---|
| norma-ammunition.com | 49 | **2,192 KB** | 2,197 KB | 100% | SPA — entire app in JS bundles |
| cuttingedgebullets.com | 374 | **194 KB** | 206 KB | 100% | Massive HTML templates in body |
| lehighdefense.com | 122 | **143 KB** | 145 KB | 100% | Same as CE — heavy templates |
| barnesbullets.com | 139 | **68 KB** | 77 KB | 100% | `<!-- DATA: -->` blocks after `<main>` — mostly JS bundles and consent manager, not product data |
| nosler.com | 455 | **67 KB** | 85 KB | 100% | Same pattern as Barnes — bloated DATA comments |
| bergerbullets.com | 145 | **35 KB** | 39 KB | 97% | Borderline — similar DATA comment bloat |
| swiftbullets.com | 56 | **31 KB** | 31 KB | 100% | Barely over |
| hornady.com | 775 | **26-36 KB** | 525 KB | 5-17% | Mostly fine, a few outlier pages |
| winchester.com | 230 | **12 KB** | 26 KB | 0% | Works great |
| federalpremium.com | 420 | **11 KB** | 11 KB | 0% | Works great |
| speer.com | 170 | **26 KB** | 28 KB | 0% | Fine |
| lapua.com | 55 | **26 KB** | 27 KB | 0% | Fine |

**~700+ pages** are over target. The 5 worst manufacturers account for the vast majority.

## Proposed Solution: Multi-Strategy Reducer

Add 2 new strategies alongside the existing generic reducer, selected by domain lookup.

### Strategy 1: `generic` (current, default)

No changes. Works for Federal, Winchester, Hornady, Speer, Lapua.

### Strategy 2: `main_content`

For sites where `<main>` contains all useful product data but the rest of the page is bloated with JS bundles, consent managers, and template code preserved as DATA comments.

**Algorithm:**
1. Extract `<main>` (or configured CSS selector) content
2. Extract only JSON-LD `<script type="application/ld+json">` blocks (ignore other DATA scripts)
3. Combine and apply existing generic reduction steps to the extracted content
4. Falls back to generic if `<main>` not found or result is below `REDUCE_MIN_SIZE`

**Target domains:**
- `barnesbullets.com` — `<main>` is 6KB vs 70KB total
- `nosler.com` — `<main>` is 14KB vs 69KB total
- `bergerbullets.com` — should bring from 35KB to under 30KB
- `swiftbullets.com` — should bring from 31KB to under 30KB

**Investigation needed for:**
- `cuttingedgebullets.com` (194KB) — check if `<main>` or another container isolates product content
- `lehighdefense.com` (143KB) — same check

### Strategy 3: `jsonld_only`

For SPAs where the HTML body is useless (JS app shell) but structured data exists in JSON-LD or similar.

**Algorithm:**
1. Extract all `<script type="application/ld+json">` blocks
2. Extract `<title>` and any `<meta>` description/og tags
3. Format as a clean pseudo-HTML document with the structured data
4. If no JSON-LD found, fall back to generic (and log a warning)

**Target domains:**
- `norma-ammunition.com` (2.2MB SPAs) — already proven via manual JSON-LD extraction in gap-fill session (see `data/patches/` Norma entries)

### Strategy Dispatch

```python
# In config.py or a new reduction/strategies.py
DOMAIN_REDUCER_STRATEGY: dict[str, str] = {
    # Strategy: main_content
    "barnesbullets.com": "main_content",
    "www.nosler.com": "main_content",
    "bergerbullets.com": "main_content",
    "www.swiftbullets.com": "main_content",
    # Strategy: jsonld_only
    "www.norma-ammunition.com": "jsonld_only",
    # Everything else: generic (default)
}
```

The `HtmlReducer.reduce()` method would accept an optional `url` parameter, extract the domain, and dispatch to the appropriate strategy. Signature change:

```python
def reduce(self, html: str, url: str | None = None) -> tuple[str, dict]:
```

The fetch script already has the URL in scope at the call site (`scripts/pipeline_fetch.py` line 108).

### Cutting Edge / Lehigh (TBD)

These two are the worst offenders (194KB, 143KB) but need investigation before choosing a strategy. The engineer should:

1. Open a fetched HTML file from each in a browser and identify the product content container
2. Check if `<main>`, `#content`, `.product-detail`, or similar isolates the specs
3. If yes → add to `main_content` with a custom CSS selector override
4. If no (e.g., content is deeply interleaved with template markup) → may need a more aggressive approach like extracting only `<table>` and `<dl>` elements

### Configuration for `main_content` CSS selectors

For most sites `<main>` works. For sites that don't use `<main>`, support a per-domain selector override:

```python
DOMAIN_CONTENT_SELECTORS: dict[str, str] = {
    # Only needed for sites where <main> doesn't work
    "cuttingedgebullets.com": ".product-detail",  # TBD — needs investigation
    "lehighdefense.com": "#product-content",      # TBD — needs investigation
}
```

## Implementation Notes

- The `main_content` strategy should still run the generic steps on extracted content (whitespace collapse, empty container removal, etc.) — just on a much smaller input.
- Preserve the existing `reduction_meta` return structure so store reports remain comparable.
- Add `strategy_used` to the metadata dict for debugging.
- Consider a `--rereduce` flag on the fetch script to re-run reduction on already-fetched pages without re-fetching (useful for testing new strategies).
- All existing reduced files would need to be regenerated for affected domains after implementation. Could be selective: delete `reduced/{hash}.json` + `reduced/{hash}.html` for affected URLs, then re-run fetch (it skips based on reduced cache existence).

## Expected Impact

| Domain | Current Avg | Expected After | Strategy |
|---|---|---|---|
| norma-ammunition.com | 2,192 KB | ~5-15 KB | jsonld_only |
| cuttingedgebullets.com | 194 KB | ~10-30 KB (TBD) | main_content |
| lehighdefense.com | 143 KB | ~10-30 KB (TBD) | main_content |
| barnesbullets.com | 68 KB | ~6-10 KB | main_content |
| nosler.com | 67 KB | ~14-20 KB | main_content |
| bergerbullets.com | 35 KB | ~15-25 KB | main_content |
| swiftbullets.com | 31 KB | ~10-20 KB | main_content |

This would bring **all manufacturers under the 30KB target**, unblocking extraction for ~700 pages currently over limit.

## Files to Modify

- `src/drift/pipeline/reduction/reducer.py` — add strategy dispatch and new strategy methods
- `src/drift/pipeline/config.py` — add `DOMAIN_REDUCER_STRATEGY` and `DOMAIN_CONTENT_SELECTORS`
- `scripts/pipeline_fetch.py` — pass `url` to `reducer.reduce()`
- Tests for each strategy
