"""Re-parse cached HTML against current parsers and report drift vs. cached extractions.

This is the cache-only refresh path (per plan primitive 2). It does not make
HTTP requests. For each extracted cache entry whose domain has a registered
parser, it re-runs the parser against the already-fetched raw HTML and diffs
the result field-by-field against the cached extraction.

Primary use case: post-parser-release backfill. When Sierra's parser fills
product_line that the LLM left null, or Hornady's parser fixes a m/s→fps bug,
this script surfaces the delta without any API cost or network traffic.

Four classification tiers per field:
  - identical         : no change
  - gap_fill          : cached=null, parser has a value  (safe-update candidate)
  - regression        : cached had value, parser=null    (review-required)
  - value_change      : both had values, different        (review-required)

Usage:
    python scripts/pipeline_refresh.py                # report, no outputs written
    python scripts/pipeline_refresh.py --domain hornady.com
    python scripts/pipeline_refresh.py --limit 50
    python scripts/pipeline_refresh.py --out path.md  # save markdown report
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from drift.pipeline.config import EXTRACTED_DIR, FETCHED_DIR, REDUCED_DIR
from drift.pipeline.extraction.engine import ExtractionEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Fields whose value_change is considered material (flip to review-required).
# Everything else falls into "safe_value_change" (mostly cosmetic or derived).
MATERIAL_FIELDS = frozenset(
    {
        "name",
        "manufacturer",
        "caliber",
        "bullet_diameter_inches",
        "weight_grains",
        "bullet_weight_grains",
        "bc_g1",
        "bc_g7",
        "length_inches",
        "bullet_length_inches",
        "muzzle_velocity_fps",
    }
)

BC_DRIFT_SAFE_PCT = 0.05  # BC delta under 5% is a safe update


@dataclass
class FieldDiff:
    field: str
    old: object
    new: object
    classification: str  # identical | gap_fill | regression | value_change


@dataclass
class EntityDiff:
    entity_index: int
    entity_name: str
    field_diffs: list[FieldDiff] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(d.classification != "identical" for d in self.field_diffs)

    def classification(self) -> str:
        """Entity-level tier: worst-case over fields."""
        tiers = {d.classification for d in self.field_diffs}
        if "regression" in tiers or "value_change_material" in tiers:
            return "review_required"
        if "gap_fill" in tiers or "value_change_safe" in tiers:
            return "safe_update"
        return "noise"


@dataclass
class FileDiff:
    url_hash: str
    url: str
    entity_type: str
    parser_name: str
    entity_diffs: list[EntityDiff] = field(default_factory=list)
    missing_from_parser: int = 0  # entities in cache but not in new parser output
    extra_from_parser: int = 0  # entities in new parser output but not in cache

    def tier(self) -> str:
        if self.missing_from_parser:
            return "review_required"
        if self.extra_from_parser or any(ed.classification() == "safe_update" for ed in self.entity_diffs):
            return "safe_update"
        if any(ed.classification() == "review_required" for ed in self.entity_diffs):
            return "review_required"
        return "noise"


# ── Value extraction / comparison ────────────────────────────────────────────


def _unwrap(obj):
    """Strip ExtractedValue wrapper to bare value. Tolerates legacy dict shapes."""
    if isinstance(obj, dict) and set(obj.keys()) >= {"value", "source_text", "confidence"}:
        return obj.get("value")
    return obj


def _classify_field(field_name: str, old_val, new_val) -> str:
    if _values_equal(old_val, new_val):
        return "identical"
    if old_val in (None, "") and new_val not in (None, ""):
        return "gap_fill"
    if new_val in (None, "") and old_val not in (None, ""):
        return "regression"
    # Both have values; distinguish material vs safe.
    if field_name in ("bc_g1", "bc_g7") and _numeric_close(old_val, new_val, BC_DRIFT_SAFE_PCT):
        return "value_change_safe"
    if field_name in MATERIAL_FIELDS:
        return "value_change_material"
    return "value_change_safe"


def _values_equal(a, b) -> bool:
    if a == b:
        return True
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-9
    # Lists with same items regardless of order.
    if isinstance(a, list) and isinstance(b, list):
        try:
            return sorted(a) == sorted(b)
        except TypeError:
            return a == b
    return False


def _numeric_close(a, b, pct: float) -> bool:
    try:
        av, bv = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if av == 0 and bv == 0:
        return True
    mean = (abs(av) + abs(bv)) / 2
    return mean > 0 and abs(av - bv) / mean <= pct


# ── Entity-level diff ────────────────────────────────────────────────────────


def diff_entity(old_raw: dict, new_raw: dict, field_list: list[str]) -> EntityDiff:
    name = _unwrap(old_raw.get("name") or new_raw.get("name")) or "(unnamed)"
    diffs = []
    for fld in field_list:
        old = _unwrap(old_raw.get(fld))
        new = _unwrap(new_raw.get(fld))
        diffs.append(FieldDiff(field=fld, old=old, new=new, classification=_classify_field(fld, old, new)))
    return EntityDiff(entity_index=0, entity_name=str(name), field_diffs=diffs)


def _align_entities(old: list[dict], new: list[dict]) -> tuple[list[tuple[dict, dict]], int, int]:
    """Pair entities by index (parser + cache output are ordered; best-effort).

    Returns (pairs, missing_from_parser, extra_from_parser).
    """
    pairs = list(zip(old, new, strict=False))
    missing = max(0, len(old) - len(new))  # cache had more than parser does now
    extra = max(0, len(new) - len(old))  # parser found more than cache had
    return pairs, missing, extra


# ── File-level refresh ───────────────────────────────────────────────────────


def _load_extracted(url_hash: str) -> dict | None:
    path = EXTRACTED_DIR / f"{url_hash}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_raw_html(url_hash: str) -> str | None:
    path = FETCHED_DIR / f"{url_hash}.html"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def refresh_file(cached: dict, engine: ExtractionEngine) -> FileDiff | None:
    url = cached.get("url") or ""
    url_hash = cached.get("url_hash") or ""
    entity_type = cached.get("entity_type") or ""
    if not (url and url_hash and entity_type):
        return None

    parser = engine._resolve_parser(url, entity_type)  # noqa: SLF001 — internal accessor by design
    if parser is None:
        return None

    raw_html = _load_raw_html(url_hash)
    if raw_html is None:
        logger.warning("No raw HTML for %s — skipping", url)
        return None

    result = engine.try_parse(url, entity_type, raw_html)
    if result is None:
        # Parser declined; nothing to diff.
        return FileDiff(url_hash=url_hash, url=url, entity_type=entity_type, parser_name=parser.name)

    new_entities = result.raw_entities or []
    old_entities = cached.get("entities") or []
    if not old_entities and not new_entities:
        return FileDiff(url_hash=url_hash, url=url, entity_type=entity_type, parser_name=parser.name)

    # Derive the field list from whichever side has one.
    sample = (new_entities[0] if new_entities else old_entities[0]) or {}
    field_names = sorted(sample.keys())

    pairs, missing, extra = _align_entities(old_entities, new_entities)
    entity_diffs = []
    for i, (old_e, new_e) in enumerate(pairs):
        ed = diff_entity(old_e, new_e, field_names)
        ed.entity_index = i
        entity_diffs.append(ed)

    return FileDiff(
        url_hash=url_hash,
        url=url,
        entity_type=entity_type,
        parser_name=parser.name,
        entity_diffs=entity_diffs,
        missing_from_parser=missing,
        extra_from_parser=extra,
    )


def refresh_all(domain_filter: str | None = None, limit: int = 0) -> list[FileDiff]:
    engine = ExtractionEngine(provider=_NullProvider(), model="refresh-cache-only")
    results: list[FileDiff] = []
    files = sorted(EXTRACTED_DIR.glob("*.json"))
    for path in files:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        url = cached.get("url", "")
        if domain_filter and domain_filter not in urlparse(url).netloc.lower():
            continue
        diff = refresh_file(cached, engine)
        if diff is not None and (diff.entity_diffs or diff.missing_from_parser or diff.extra_from_parser):
            results.append(diff)
        if limit and len(results) >= limit:
            break
    return results


# ── Reporting ────────────────────────────────────────────────────────────────


def _collect_field_stats(diffs: list[FileDiff]) -> tuple[Counter, Counter]:
    gap_fills: Counter = Counter()
    regressions: Counter = Counter()
    for d in diffs:
        for ed in d.entity_diffs:
            for fd in ed.field_diffs:
                if fd.classification == "gap_fill":
                    gap_fills[fd.field] += 1
                elif fd.classification == "regression":
                    regressions[fd.field] += 1
    return gap_fills, regressions


def _review_sample_lines(diffs: list[FileDiff], limit: int = 10) -> list[str]:
    review_items = [d for d in diffs if d.tier() == "review_required"][:limit]
    if not review_items:
        return []
    lines = [f"## Review-required samples (first {limit})", ""]
    for d in review_items:
        lines.append(f"- [{d.parser_name}] {d.url}")
        if d.missing_from_parser:
            lines.append(f"  - missing_from_parser: {d.missing_from_parser}")
        for ed in d.entity_diffs:
            for fd in ed.field_diffs:
                if fd.classification in ("regression", "value_change_material"):
                    lines.append(f"  - `{fd.field}` ({fd.classification}): `{fd.old}` → `{fd.new}`")
    lines.append("")
    return lines


def _counter_section(title: str, counter: Counter, head: int = 15) -> list[str]:
    if not counter:
        return []
    lines = [f"## {title}", ""]
    lines.extend(f"- `{key}`: {n}" for key, n in counter.most_common(head))
    lines.append("")
    return lines


def render_markdown(diffs: list[FileDiff]) -> str:
    tier_counts: Counter = Counter(d.tier() for d in diffs)
    parser_counts: Counter = Counter(d.parser_name for d in diffs)
    gap_fills, regressions = _collect_field_stats(diffs)

    lines = [
        "# Pipeline refresh (cache-only) — drift report",
        "",
        f"**Total files with changes:** {len(diffs)}",
        "",
    ]
    lines.extend(_counter_section("Tier counts", tier_counts, head=99))
    lines.extend(_counter_section("By parser", parser_counts, head=99))
    lines.extend(_counter_section("Gap-fills (cached=null → parser has value)", gap_fills))
    lines.extend(_counter_section("Regressions (cached had value → parser=null)", regressions))
    lines.extend(_review_sample_lines(diffs))
    return "\n".join(lines)


# ── Provider shim for cache-only runs ────────────────────────────────────────


class _NullProvider:
    """Minimal stand-in so ExtractionEngine constructs without API keys.

    We only use engine.try_parse() in cache-only mode — the LLM path is never
    invoked, so the provider methods never get called.
    """

    def extract(self, *_a, **_kw):  # pragma: no cover — defensive
        raise RuntimeError("cache-only refresh must not invoke the LLM provider")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-parse cached HTML and report drift vs cached extractions")
    parser.add_argument("--domain", type=str, default=None, help="Limit to URLs matching this domain substring")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N files with changes (0 = all)")
    parser.add_argument("--out", type=Path, default=None, help="Write markdown report to path")
    parser.add_argument("--print", action="store_true", help="Print markdown report to stdout")
    args = parser.parse_args()

    # REDUCED_DIR is imported for symmetry with other pipeline scripts but
    # isn't read in cache-only mode — assert presence so the import isn't
    # flagged as unused.
    assert REDUCED_DIR.parent is not None

    logger.info("Scanning %s for extracted cache entries...", EXTRACTED_DIR)
    diffs = refresh_all(domain_filter=args.domain, limit=args.limit)

    tier_counts = Counter(d.tier() for d in diffs)
    print()
    print("─" * 70)
    print("Cache-only refresh summary")
    print(f"  files with changes:  {len(diffs)}")
    for tier in ("noise", "safe_update", "review_required"):
        print(f"    {tier}:".ljust(22), tier_counts.get(tier, 0))
    print()

    report = render_markdown(diffs)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"✓ Wrote report: {args.out}")
    if args.print or not args.out:
        print()
        print(report if args.print else "(use --print to show report, or --out PATH to save)")


if __name__ == "__main__":
    main()
