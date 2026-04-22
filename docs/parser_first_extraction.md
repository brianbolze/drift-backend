# Parser-First Extraction Tier — Implementation Plan

**Status:** approved for implementation.
**Scope:** introduces deterministic per-manufacturer parsers as a pre-LLM tier, with the LLM as a guaranteed fallback. No changes to the existing LLM path's behavior on domains without a parser.

## Implementation status

**Landed 2026-04-22.** Both PRs implemented. Viability gate cleared and promoted.

- **Agreement vs cached LLM output** ([parser_agreement_hornady.md](parser_agreement_hornady.md)): 761/776 Hornady pages parsed; 100% agreement on every deterministic numeric field (bc_g1, bc_g7, weight, diameter, sectional_density, sku, muzzle_velocity_fps) and on bullet + cartridge `name`. Remaining noise is naming-convention ("Hornady" vs "Hornady Manufacturing, Inc", "380 Auto" vs "380 Automatic") resolved downstream via EntityAlias.
- **Parser vs current DB** ([parser_vs_db_hornady.md](parser_vs_db_hornady.md)): joined by `source_url`; 339/339 DB rows match parser output bit-for-bit. Zero new BCs. 422 URLs not in DB are all handgun/pistol loads correctly filtered by `rejected_calibers.json`.
- **Telemetry**: new cache records carry `extraction_method: "parser" | "parser_fellthrough_to_llm" | "llm"` + `parser_name`.

Parsers now active on: `www.hornady.com`. Next target per rollout plan: Sierra (248 cached extractions).

## Why

Cached extractions show several manufacturer pages already embed machine-readable structured data — the LLM is effectively re-transcribing JSON. Examples from `data/pipeline/extracted/`:

- **Hornady** (776 extractions): `"cartridgename":"300 Savage"`, `"weight":150`, `"ball_coef":0.37,"ball_coef_type":1`, `"muzzlevelocity":2740`
- **Sierra** (248 extractions): `"Bullet Diameter","value":"0.277"`, `"G1 BC","value":"0.505"`, `"G7 BC","value":"0.245"`

A deterministic parser on the happy path skips the LLM entirely on those domains. LLM remains the fallback when a parser returns `None`, raises, or produces values that fail validation.

## Architecture

### File layout

```
src/drift/pipeline/extraction/
  parsers/
    __init__.py          # exports BaseParser, ParserResult, lookup helper
    base.py              # BaseParser ABC + ParserResult + ParserError
    registry.py          # name → class mapping, lazy-imported
    hornady.py           # first parser (PR #2)
tests/fixtures/parsers/
  hornady/
    <case>.html                 # raw HTML snapshot
    <case>.expected.json        # expected Pydantic output
tests/pipeline/test_parsers.py  # golden-set + agreement-report tests
```

Parsers live under `extraction/`, not as a peer package — they are an extraction strategy, not a separate pipeline stage.

### Base class + result type

```python
# src/drift/pipeline/extraction/parsers/base.py
class ParserError(Exception):
    """Parser tried to handle the page but hit an unexpected condition."""

@dataclasses.dataclass(frozen=True, slots=True)
class ParserResult:
    entities: list[ExtractedBullet | ExtractedCartridge | ExtractedRifleModel]
    bc_sources: list[ExtractedBCSource]
    warnings: list[str]

class BaseParser(ABC):
    supported_entity_types: frozenset[str]  # e.g. frozenset({"bullet", "cartridge"})

    @abstractmethod
    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:
        """Return None to signal 'I can't handle this page' — engine falls through to LLM.
        Raise ParserError for unexpected failures (also falls through, also logged)."""
```

Parsers return the same Pydantic models (`ExtractedBullet` / `ExtractedCartridge` / `ExtractedRifleModel`) the LLM path produces. Keeps the downstream contract identical.

### Registry (mirrors `DOMAIN_REDUCER_STRATEGY`)

```python
# src/drift/pipeline/config.py
DOMAIN_PARSER: dict[str, str] = {
    # populated in PR #2; empty in PR #1
}
```

```python
# src/drift/pipeline/extraction/parsers/registry.py
def get_parser_for_domain(domain: str) -> BaseParser | None: ...
```

Lazy import inside `get_parser_for_domain` to avoid circular deps. Single-line config flag per domain means parser adoption is trivial to enable/disable without code changes.

## Engine fallthrough flow

`ExtractionEngine.extract()` grows a pre-LLM branch:

```
1. Resolve parser for url's domain via registry. None → step 5.
2. entity_type not in parser.supported_entity_types → step 5.
3. Load raw HTML from data/pipeline/fetched/<hash>.html.
   Raw missing (disk wipe, never-fetched, etc.) → step 5.
4. Try parser.parse(raw_html, url, entity_type):
     - returns None                         → step 5 (log reason)
     - raises ParserError / any exception   → step 5 (log + counter)
     - returns ParserResult:
         - run entities through validate_ranges()
         - any entity outside ranges        → step 5 (log)
         - clean                            → pass through the existing
                                              Pydantic parse_response() gate
                                              for symmetry, then return.
5. LLM path (unchanged from today).
```

Notes on the cascade:
- **Raw-missing fallback is two lines** — don't over-engineer. Use the reduced HTML path on the LLM side exactly as today.
- **Pydantic gate stays on parser output.** No-op in the happy case, catches a future parser that accidentally returns a dict or an old schema shape. Symmetry is cheap.
- **`BulletBCSource.source` does NOT get a new enum value for parser-extracted BCs.** The `source` field is semantic ("where in the world did this number come from": `manufacturer`, `cartridge_page`, `doppler_radar`) — not how we lifted it. Parser BCs from a manufacturer page stay tagged `manufacturer`.

## Telemetry

Each record in `data/pipeline/extracted/*.json` gains:

```json
{
  "extraction_method": "parser" | "parser_fellthrough_to_llm" | "llm",
  "parser_name": "hornady" | null,
  ...
}
```

`usage` on the parser path records zero LLM tokens. Rollup with `jq` over the cache directory gives cost/coverage by method and manufacturer.

**Do not bump `schema_version`.** The extracted-entity payload is identical to the LLM output; only the audit fields change.

## Per-field confidence in parsers

Do **not** blanket-assign `confidence: 1.0` on parser output. Confidence should track the actual certainty of the extraction method per field:

- Fields lifted verbatim from JSON-LD or inline JSON keys (e.g. `ball_coef`, `muzzlevelocity`, `weight`) → `1.0`. Machine-readable, no interpretation.
- Fields regex-extracted from prose or messy product names (e.g. `product_line` parsed out of `"30 Cal .308 178 gr ELD-X®"`) → `~0.8`. Rules can be wrong.
- Fields requiring heuristic inference (e.g. deriving `base_type: "boat_tail"` from the presence of "BT" in the name) → `0.7` or lower.

Downstream resolver behavior is confidence-sensitive. Parsers that lie about confidence corrupt the resolver.

## Testing

### Golden-set fixtures (per parser)

`tests/fixtures/parsers/<manufacturer>/` — one `(input.html, expected.json)` pair per case. Expected JSON is the Pydantic-dumped model list. Test driver is shared:

```python
# tests/pipeline/test_parsers.py
@pytest.mark.parametrize("case", _discover_cases("hornady"))
def test_hornady_parser_matches_golden(case): ...
```

Keep each parser's fixture set to 5–10 cases covering:
- Happy path per supported entity type
- Each optional field absent
- Each validation boundary (low/high BC, weight mismatch)
- One deliberately adversarial page where the parser must return `None` cleanly

Golden refresh is explicit — provide a tiny CLI (`python -m drift.pipeline.extraction.parsers.update_golden hornady`) that re-runs the parser and overwrites `.expected.json`. Committers review the diff.

### Cache-wide agreement report (not a pass/fail regression test)

Run the parser over every matching extraction already cached in `data/pipeline/extracted/` and compare parser output to LLM output.

**This is not a regression test in the traditional sense — the LLM is not ground truth.** You will get disagreements where the parser is correct and the LLM was noisy. The test asserts structural correctness only; agreement is reported as a metric.

- **Pass/fail (hard):** parser crashed, returned wrong type, violated validation ranges, raised an unhandled exception.
- **Reported, not asserted:** field-level agreement percentage. Printed as a table at the end of the test run. Scoped to deterministic fields only: `name`, `manufacturer`, `caliber`, `bullet_diameter_inches`, `weight_grains`, `bc_g1`, `bc_g7`, `muzzle_velocity_fps`, `sku`. **Excluded:** `product_line`, `used_for`, `type_tags`, `base_type`, `tip_type` — known LLM-variable.

The agreement report is where the 90% viability discussion happens.

## First target: Hornady

| | Hornady | Sierra |
|---|---|---|
| Extractions in cache | **776** | 248 |
| Entity coverage | bullet + cartridge | bullet only |
| Structured signal | Embedded JSON (`ball_coef`, `muzzlevelocity`, `cartridgename`, `weight`) | Label/value HTML table |
| Rough LLM cost share | ~25% of all extractions | ~8% |

Hornady has the biggest volume, both entity types (exercises cartridge parsing too), and the cleanest machine-readable signal. Sierra is the most likely second target once the pattern is proven.

### Viability gate — framing

Target: ≥90% agreement on deterministic fields against cached LLM output over the 776 Hornady pages.

**This is a prior-to-generalizing gate, not a kill switch.** If Hornady hits 88% on the first pass, do not scrap parsers wholesale. Investigate the 12%:
- Is the parser wrong? Fix it.
- Is the LLM wrong? The parser is doing its job and the gap is noise in the "ground truth."
- Is the page structurally different (e.g. a product family page vs. a single-SKU page)? Narrow the parser's scope.

Whichever answer applies, the investigation is where the highest-value learning lives about what parsers can and can't do on that manufacturer's HTML. That answer also informs which manufacturer to target second.

## Rollout

### PR #1 — Dark infrastructure

- Everything under `parsers/` except `hornady.py`.
- `DOMAIN_PARSER = {}` in config (registry empty, parser branch in engine unreachable in production).
- Engine fallthrough cascade, telemetry fields, `ParserResult` type, registry lookup, Pydantic gate, golden-set driver.
- Unit tests for the engine's fallthrough logic using a fake parser (mock returning `None`, raising, returning valid, returning invalid).

Low-risk, lands the abstraction, exercises all code paths in tests without touching production runs.

### PR #2 — Hornady parser lights up

- `hornady.py` with typed parsing of Hornady's inline JSON.
- Golden-set fixtures under `tests/fixtures/parsers/hornady/`.
- `DOMAIN_PARSER = {"www.hornady.com": "hornady"}` in config.
- **Agreement report committed as a markdown artifact** (e.g. `docs/parser_agreement_hornady.md`) so the diff is reviewable — field-by-field percentages + a sample of disagreements with URLs. This is the viability-gate evidence.
- Cached LLM extractions stay as-is (no re-extraction, no `schema_version` bump). New runs route through the parser for Hornady URLs.

## Out of scope for this work

- Touching the OpenAI provider or any non-Anthropic extraction path.
- Refactoring prompt management, moving prompts to files, or altering LLM prompts.
- Retroactively re-extracting Hornady URLs. The cache is left alone; parser adoption happens on the next pipeline run.
- Adding a row-level parser audit column on `bullet` / `cartridge` models. The extracted-JSON audit is sufficient; if row-level audit is ever needed, add it as a separate column later — do not overload `BulletBCSource.source`.
- Sierra and other manufacturers. Treat as PR #3+, gated on Hornady's agreement report.

## Summary of decisions baked in

| Decision | Resolution |
|---|---|
| Parser input format | Raw HTML from `fetched/`, with raw-missing → LLM fallback on reduced HTML |
| `BulletBCSource.source` tagging | Keep semantic (`manufacturer`, etc.); parser-ness lives in `extraction_method` on the audit JSON |
| Pydantic gate on parser output | Kept — no-op in happy case, catches type drift |
| Agreement-vs-LLM test semantics | Structural issues fail; field-level agreement reported as a metric |
| Per-field confidence | Tiered by extraction certainty, not blanket 1.0 |
| Rollout | PR #1 dark infra + PR #2 Hornady + agreement report |
| First manufacturer | Hornady — largest volume, both entity types, cleanest JSON |
| 90% viability gate | Prior-to-generalizing gate, not a kill switch |
