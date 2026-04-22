"""Run a parser over every cached LLM extraction for its domain and report
field-level agreement — the viability-gate evidence for a parser PR.

Structural failures fail hard; field-level agreement is a metric, not a
pass/fail. The LLM is NOT ground truth — disagreements where the parser is
correct and the LLM was noisy are expected and called out by URL so reviewers
can investigate.

Usage:
    python scripts/parser_agreement_report.py hornady
    python scripts/parser_agreement_report.py hornady --limit 100
    python scripts/parser_agreement_report.py hornady --out docs/parser_agreement_hornady.md
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from drift.pipeline.config import DOMAIN_PARSER, EXTRACTED_DIR, FETCHED_DIR
from drift.pipeline.extraction.parsers.registry import _instantiate

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Deterministic fields where parser and LLM are expected to agree — free of
# the known LLM-variable fields (product_line, used_for, type_tags, base_type,
# tip_type). Per-entity-type field sets per docs/parser_first_extraction.md.
DETERMINISTIC_FIELDS: dict[str, list[str]] = {
    "bullet": [
        "name",
        "manufacturer",
        "bullet_diameter_inches",
        "weight_grains",
        "bc_g1",
        "bc_g7",
        "sectional_density",
        "sku",
    ],
    "cartridge": [
        "name",
        "manufacturer",
        "caliber",
        "bullet_weight_grains",
        "bc_g1",
        "bc_g7",
        "muzzle_velocity_fps",
        "sku",
    ],
}

# Numeric tolerance when comparing floats. 0.5% relative OR an absolute
# minimum — so BCs (tight absolute diffs) and MV (big magnitudes) both work.
# Example: 2598 vs 2600 counts as agreement (within 0.1%); 0.485 vs 0.49 too.
NUMERIC_REL_TOL = 0.005
NUMERIC_ABS_TOL = 0.01


@dataclasses.dataclass
class FieldStats:
    agree: int = 0
    disagree: int = 0
    parser_null_llm_value: int = 0
    parser_value_llm_null: int = 0
    both_null: int = 0

    @property
    def total(self) -> int:
        return self.agree + self.disagree + self.parser_null_llm_value + self.parser_value_llm_null + self.both_null

    @property
    def non_null_total(self) -> int:
        """Count of cases where at least one side had a non-null value."""
        return self.agree + self.disagree + self.parser_null_llm_value + self.parser_value_llm_null

    @property
    def agreement_pct(self) -> float:
        if self.non_null_total == 0:
            return 100.0
        return 100.0 * self.agree / self.non_null_total


@dataclasses.dataclass
class RunOutcome:
    total: int = 0
    parser_null: int = 0
    parser_error: int = 0
    parser_invalid: int = 0
    parser_entity_count_mismatch: int = 0
    parsed_ok: int = 0
    structural_failures: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    disagreement_samples: list[dict] = dataclasses.field(default_factory=list)


def _get(value, *path):
    """Dig into a nested ExtractedValue-style dict. Returns None if missing."""
    cur = value
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def _normalize_scalar(val):
    if isinstance(val, str):
        stripped = val.strip()
        return stripped if stripped else None
    return val


def _values_agree(parser_val, llm_val) -> bool:
    """Compare a parser value to an LLM value with float tolerance + string normalization."""
    if parser_val is None and llm_val is None:
        return True
    if parser_val is None or llm_val is None:
        return False
    if isinstance(parser_val, (int, float)) and isinstance(llm_val, (int, float)):
        a, b = float(parser_val), float(llm_val)
        return abs(a - b) <= max(NUMERIC_ABS_TOL, NUMERIC_REL_TOL * max(abs(a), abs(b)))
    if isinstance(parser_val, str) and isinstance(llm_val, str):
        return _normalize_str(parser_val) == _normalize_str(llm_val)
    return parser_val == llm_val


# Characters that are formatting noise, not content. Unicode non-breaking
# hyphen (U+2011) often appears in Hornady's HTML where the LLM emits a
# regular hyphen; neither is "wrong."
_NORMALIZATION_NOISE = {
    "\u00ae": "",  # ®
    "\u2122": "",  # ™
    "\u2011": "-",  # non-breaking hyphen → hyphen
}


def _normalize_str(s: str) -> str:
    for src, dst in _NORMALIZATION_NOISE.items():
        s = s.replace(src, dst)
    return " ".join(s.lower().split())


def _compare_one(parser_entity: dict, llm_entity: dict, fields: list[str]):
    """Yield (field, parser_val, llm_val, classification) per deterministic field."""
    for f in fields:
        parser_val = _normalize_scalar(_get(parser_entity, f, "value"))
        llm_val = _normalize_scalar(_get(llm_entity, f, "value"))
        if parser_val is None and llm_val is None:
            yield f, parser_val, llm_val, "both_null"
        elif parser_val is None:
            yield f, parser_val, llm_val, "parser_null_llm_value"
        elif llm_val is None:
            yield f, parser_val, llm_val, "parser_value_llm_null"
        elif _values_agree(parser_val, llm_val):
            yield f, parser_val, llm_val, "agree"
        else:
            yield f, parser_val, llm_val, "disagree"


def _iter_domain_extractions(domain: str):
    for cache_file in sorted(EXTRACTED_DIR.glob("*.json")):
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if urlparse(data.get("url", "")).netloc.lower() != domain:
            continue
        yield cache_file, data


def run_report(  # noqa: C901
    parser_name: str,
    limit: int | None,
    out_path: Path,
) -> int:
    # Find the domain this parser serves.
    domain = None
    for d, n in DOMAIN_PARSER.items():
        if n == parser_name:
            domain = d
            break
    if domain is None:
        print(f"Parser {parser_name!r} not registered in DOMAIN_PARSER", file=sys.stderr)
        return 2
    parser = _instantiate(parser_name)
    if parser is None:
        print(f"Unknown parser: {parser_name}", file=sys.stderr)
        return 2

    per_type_stats: dict[str, dict[str, FieldStats]] = {
        "bullet": {f: FieldStats() for f in DETERMINISTIC_FIELDS["bullet"]},
        "cartridge": {f: FieldStats() for f in DETERMINISTIC_FIELDS["cartridge"]},
    }
    outcome = RunOutcome()
    disagreement_buckets: dict[str, list[dict]] = defaultdict(list)

    for _cache_file, data in _iter_domain_extractions(domain):
        if limit is not None and outcome.total >= limit:
            break
        outcome.total += 1

        url = data["url"]
        uhash = data["url_hash"]
        entity_type = data.get("entity_type")
        if entity_type not in DETERMINISTIC_FIELDS:
            continue

        raw_path = FETCHED_DIR / f"{uhash}.html"
        if not raw_path.exists():
            outcome.structural_failures.append((url, "raw HTML missing"))
            continue
        html = raw_path.read_text(encoding="utf-8")

        try:
            result = parser.parse(html, url, entity_type)
        except Exception as e:
            outcome.parser_error += 1
            outcome.structural_failures.append((url, f"parser raised {type(e).__name__}: {e}"))
            continue

        if result is None:
            outcome.parser_null += 1
            continue

        parser_entities = [e.model_dump() for e in result.entities]
        llm_entities = data.get("entities", [])

        if len(parser_entities) != len(llm_entities):
            outcome.parser_entity_count_mismatch += 1
            outcome.structural_failures.append(
                (url, f"entity count: parser={len(parser_entities)}, llm={len(llm_entities)}")
            )
            continue

        outcome.parsed_ok += 1
        if not parser_entities:
            continue

        parser_entity = parser_entities[0]
        llm_entity = llm_entities[0]
        fields = DETERMINISTIC_FIELDS[entity_type]
        field_stats = per_type_stats[entity_type]

        for f, parser_val, llm_val, cls in _compare_one(parser_entity, llm_entity, fields):
            stats = field_stats[f]
            if cls == "agree":
                stats.agree += 1
            elif cls == "disagree":
                stats.disagree += 1
                if len(disagreement_buckets[f]) < 5:
                    disagreement_buckets[f].append(
                        {"url": url, "parser": parser_val, "llm": llm_val, "entity_type": entity_type}
                    )
            elif cls == "parser_null_llm_value":
                stats.parser_null_llm_value += 1
            elif cls == "parser_value_llm_null":
                stats.parser_value_llm_null += 1
                if len(disagreement_buckets[f]) < 5:
                    disagreement_buckets[f].append(
                        {"url": url, "parser": parser_val, "llm": None, "entity_type": entity_type}
                    )
            else:
                stats.both_null += 1

    # ── Render ───────────────────────────────────────────────────────────
    lines = []
    lines.append(f"# Parser agreement report — {parser_name}")
    lines.append("")
    lines.append(
        f"Generated by `scripts/parser_agreement_report.py {parser_name}`. "
        f"Compares parser output to cached LLM output on deterministic fields. "
        f"**The LLM is not ground truth** — field-level disagreements are reported as a metric, not asserted."
    )
    lines.append("")
    lines.append(
        f"Numeric comparison allows ±{NUMERIC_REL_TOL * 100:.1f}% relative "
        f"(to absorb unit-conversion rounding). String comparison is "
        f"case-insensitive and ignores trademark glyphs + non-breaking hyphens."
    )
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- **Domain:** `{domain}`")
    lines.append(f"- **Cached LLM extractions examined:** {outcome.total}")
    lines.append(f"- **Parser returned usable result:** {outcome.parsed_ok}")
    lines.append(f"- **Parser declined (returned None):** {outcome.parser_null}")
    lines.append(f"- **Parser raised:** {outcome.parser_error}")
    lines.append(f"- **Parser entity-count mismatch vs LLM:** {outcome.parser_entity_count_mismatch}")
    lines.append("")
    if outcome.structural_failures:
        lines.append(f"### Structural issues ({len(outcome.structural_failures)})")
        lines.append("")
        counter = Counter(reason for _, reason in outcome.structural_failures)
        for reason, n in counter.most_common():
            lines.append(f"- **{n}×** {reason}")
        lines.append("")
        # First 10 raw URLs for drilldown
        lines.append("<details><summary>First 10 failing URLs</summary>\n")
        for url, reason in outcome.structural_failures[:10]:
            lines.append(f"- `{url}` — {reason}")
        lines.append("\n</details>")
        lines.append("")
    lines.append("## Field-level agreement")
    lines.append("")
    for entity_type, field_stats in per_type_stats.items():
        lines.append(f"### {entity_type}")
        lines.append("")
        header = (
            "| Field | Agree | Disagree | Parser-null, LLM-value | "
            "Parser-value, LLM-null | Both-null | Agreement % (non-null pairs) |"
        )
        lines.append(header)
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for f, s in field_stats.items():
            lines.append(
                f"| `{f}` | {s.agree} | {s.disagree} | {s.parser_null_llm_value} | "
                f"{s.parser_value_llm_null} | {s.both_null} | {s.agreement_pct:.1f}% |"
            )
        lines.append("")

    if disagreement_buckets:
        lines.append("## Disagreement samples")
        lines.append("")
        lines.append(
            "Up to 5 examples per field where parser and LLM diverge. "
            "Most are LLM noise (trademark handling, variant product-line extraction, regex-vs-prose bullet names). "
            "Treat as an investigation list, not a bug list."
        )
        lines.append("")
        for field in sorted(disagreement_buckets.keys()):
            samples = disagreement_buckets[field]
            lines.append(f"### `{field}`")
            lines.append("")
            lines.append("| URL | Parser | LLM |")
            lines.append("|---|---|---|")
            for s in samples:
                url = s["url"]
                parser_val = repr(s["parser"]) if s["parser"] is not None else "_null_"
                llm_val = repr(s["llm"]) if s["llm"] is not None else "_null_"
                lines.append(f"| `{url}` | {parser_val} | {llm_val} |")
            lines.append("")

    report = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Parser-vs-LLM agreement report.")
    parser.add_argument("parser_name", help="Parser short name (e.g. 'hornady')")
    parser.add_argument("--limit", type=int, default=None, help="Max cached extractions to process")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output markdown path (defaults to docs/parser_agreement_<name>.md)",
    )
    args = parser.parse_args()
    out = args.out or Path(__file__).resolve().parent.parent / "docs" / f"parser_agreement_{args.parser_name}.md"
    return run_report(args.parser_name, args.limit, out)


if __name__ == "__main__":
    sys.exit(main())
