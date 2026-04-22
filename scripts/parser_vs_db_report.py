"""Run a parser over its domain's fetched HTML and diff against current DB state.

For each URL the parser handles, joins to the corresponding DB row via
``source_url`` (each Hornady page is a 1:1 bullet or cartridge). Reports:

  - how many URLs made it into the DB (vs. filtered by rejected-caliber list,
    or flagged at store time)
  - per-field discrepancies between parser output and DB values
  - BC coverage: parser-found BCs that are/aren't recorded in bullet_bc_source

The DB is **read only** — this script inserts nothing. Use it as a sanity
check before pointing the live pipeline at a parser.

Usage:
    python scripts/parser_vs_db_report.py hornady
    python scripts/parser_vs_db_report.py hornady --out docs/parser_vs_db_hornady.md
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from drift.models.bullet import Bullet, BulletBCSource
from drift.models.cartridge import Cartridge
from drift.models.manufacturer import Manufacturer
from drift.pipeline.config import DOMAIN_PARSER, FETCHED_DIR
from drift.pipeline.extraction.parsers.registry import _instantiate

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "drift.db"

NUMERIC_REL_TOL = 0.01  # 1% — DB values may have been rounded during earlier ingests
NUMERIC_ABS_TOL = 0.01

# The manufacturer name in the DB for each parser's domain. Add an entry
# when a new parser lands; otherwise the report has no way to scope the
# DB query to the right rows.
PARSER_TO_MANUFACTURER = {
    "hornady": "Hornady",
    "sierra": "Sierra Bullets",
    "nosler": "Nosler",
}


# How each parser's URLs split into entity types.
def _entity_type_for_url(parser_name: str, url: str) -> str | None:
    if parser_name == "hornady":
        if "/bullets/" in url:
            return "bullet"
        if "/ammunition/" in url:
            return "cartridge"
        return None
    if parser_name == "sierra":
        return "bullet"  # Sierra is bullet-only
    if parser_name == "nosler":
        # Nosler URL slugs: ammunition pages end with "-ammunition.html", bullets
        # are product pages with grain weight + bullet line (no "-ammunition").
        if "-ammunition.html" in url:
            return "cartridge"
        return "bullet"
    return None


@dataclasses.dataclass
class Outcome:
    total_urls: int = 0
    parser_declined: int = 0
    in_db_match: int = 0
    in_db_diff: int = 0
    not_in_db: int = 0
    locked_rows: int = 0
    bc_present_in_db: int = 0
    bc_missing_from_db: int = 0


def _domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def _numbers_agree(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    return abs(a - b) <= max(NUMERIC_ABS_TOL, NUMERIC_REL_TOL * max(abs(a), abs(b)))


def _build_url_to_hash_map(domain: str) -> dict[str, str]:
    """Walk fetched/*.json to map URL → url_hash for a given domain."""
    import json

    mapping: dict[str, str] = {}
    for meta_path in FETCHED_DIR.glob("*.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        url = data.get("url", "")
        if _domain_of(url) != domain:
            continue
        mapping[url] = meta_path.stem
    return mapping


def _compare_bullet(parser_entity, db_row: Bullet, bc_sources: list[BulletBCSource]) -> list[str]:
    diffs: list[str] = []

    if not _numbers_agree(parser_entity.weight_grains.value, db_row.weight_grains):
        diffs.append(f"weight: parser={parser_entity.weight_grains.value} db={db_row.weight_grains}")

    if not _numbers_agree(parser_entity.bullet_diameter_inches.value, db_row.bullet_diameter_inches):
        diffs.append(
            f"diameter: parser={parser_entity.bullet_diameter_inches.value} db={db_row.bullet_diameter_inches}"
        )

    # BC comparison: the parser's BC should either match bc_g1_published/estimated
    # or appear in bullet_bc_source. Report as "missing" if neither matches.
    bc_g1 = parser_entity.bc_g1.value
    if bc_g1 is not None:
        canon = db_row.bc_g1_published if db_row.bc_g1_published is not None else db_row.bc_g1_estimated
        bc_source_values = [s.bc_value for s in bc_sources if s.bc_type == "g1"]
        if not _numbers_agree(bc_g1, canon) and not any(_numbers_agree(bc_g1, v) for v in bc_source_values):
            diffs.append(f"bc_g1: parser={bc_g1} db_canonical={canon} db_sources={bc_source_values}")

    bc_g7 = parser_entity.bc_g7.value
    if bc_g7 is not None:
        canon = db_row.bc_g7_published if db_row.bc_g7_published is not None else db_row.bc_g7_estimated
        bc_source_values = [s.bc_value for s in bc_sources if s.bc_type == "g7"]
        if not _numbers_agree(bc_g7, canon) and not any(_numbers_agree(bc_g7, v) for v in bc_source_values):
            diffs.append(f"bc_g7: parser={bc_g7} db_canonical={canon} db_sources={bc_source_values}")

    if parser_entity.sku.value and db_row.sku and parser_entity.sku.value != db_row.sku:
        diffs.append(f"sku: parser={parser_entity.sku.value!r} db={db_row.sku!r}")

    return diffs


def _compare_cartridge(parser_entity, db_row: Cartridge) -> list[str]:
    diffs: list[str] = []

    if not _numbers_agree(parser_entity.bullet_weight_grains.value, db_row.bullet_weight_grains):
        diffs.append(f"weight: parser={parser_entity.bullet_weight_grains.value} db={db_row.bullet_weight_grains}")

    pmv = parser_entity.muzzle_velocity_fps.value
    if pmv is not None and db_row.muzzle_velocity_fps is not None:
        if not _numbers_agree(pmv, db_row.muzzle_velocity_fps):
            diffs.append(f"mv_fps: parser={pmv} db={db_row.muzzle_velocity_fps}")

    # BC on cartridge — stored directly (not via bc_source for cartridges).
    if parser_entity.bc_g1.value is not None and db_row.bc_g1 is not None:
        if not _numbers_agree(parser_entity.bc_g1.value, db_row.bc_g1):
            diffs.append(f"bc_g1: parser={parser_entity.bc_g1.value} db={db_row.bc_g1}")
    if parser_entity.bc_g7.value is not None and db_row.bc_g7 is not None:
        if not _numbers_agree(parser_entity.bc_g7.value, db_row.bc_g7):
            diffs.append(f"bc_g7: parser={parser_entity.bc_g7.value} db={db_row.bc_g7}")

    if parser_entity.sku.value and db_row.sku and parser_entity.sku.value != db_row.sku:
        diffs.append(f"sku: parser={parser_entity.sku.value!r} db={db_row.sku!r}")

    return diffs


def run_report(parser_name: str, out_path: Path) -> int:  # noqa: C901
    domain = next((d for d, n in DOMAIN_PARSER.items() if n == parser_name), None)
    if domain is None:
        print(f"Parser {parser_name!r} not registered in DOMAIN_PARSER", file=sys.stderr)
        return 2
    parser = _instantiate(parser_name)
    if parser is None:
        print(f"Unknown parser: {parser_name}", file=sys.stderr)
        return 2

    engine = create_engine(f"sqlite:///{DB_PATH}")

    url_to_hash = _build_url_to_hash_map(domain)
    if not url_to_hash:
        print(f"No fetched HTML found for domain {domain}", file=sys.stderr)
        return 2

    outcome = Outcome()
    outcome.total_urls = len(url_to_hash)

    diff_rows: list[tuple[str, str, list[str]]] = []  # (url, entity_type, diffs)
    not_in_db_samples: dict[str, list[str]] = defaultdict(list)  # entity_type → [urls]
    field_diff_counter: Counter = Counter()

    mfr_name = PARSER_TO_MANUFACTURER.get(parser_name)
    if mfr_name is None:
        print(
            f"No PARSER_TO_MANUFACTURER entry for {parser_name!r} — add one before running this report.",
            file=sys.stderr,
        )
        return 2

    with Session(engine) as session:
        mfr = session.scalar(select(Manufacturer).where(Manufacturer.name == mfr_name))
        if mfr is None:
            print(f"No {mfr_name!r} manufacturer row in DB — nothing to compare.", file=sys.stderr)
            return 1

        # Prefetch DB rows keyed by source_url.
        bullet_by_url: dict[str, Bullet] = {
            b.source_url: b
            for b in session.scalars(select(Bullet).where(Bullet.manufacturer_id == mfr.id))
            if b.source_url
        }
        cartridge_by_url: dict[str, Cartridge] = {
            c.source_url: c
            for c in session.scalars(select(Cartridge).where(Cartridge.manufacturer_id == mfr.id))
            if c.source_url
        }

        for url, uhash in sorted(url_to_hash.items()):
            raw_path = FETCHED_DIR / f"{uhash}.html"
            if not raw_path.exists():
                continue
            html = raw_path.read_text(encoding="utf-8")

            entity_type = _entity_type_for_url(parser_name, url)
            if entity_type is None:
                continue

            try:
                result = parser.parse(html, url, entity_type)
            except Exception:
                outcome.parser_declined += 1
                continue
            if result is None or not result.entities:
                outcome.parser_declined += 1
                continue

            pentity = result.entities[0]

            if entity_type == "bullet":
                db_row = bullet_by_url.get(url)
                if db_row is None:
                    outcome.not_in_db += 1
                    not_in_db_samples["bullet"].append(url)
                    continue
                if db_row.is_locked:
                    outcome.locked_rows += 1
                bc_sources = list(session.scalars(select(BulletBCSource).where(BulletBCSource.bullet_id == db_row.id)))
                # Track BC source coverage
                for bc_field, bc_type in [("bc_g1", "g1"), ("bc_g7", "g7")]:
                    parser_bc = getattr(pentity, bc_field).value
                    if parser_bc is None:
                        continue
                    matches = [s for s in bc_sources if s.bc_type == bc_type and _numbers_agree(s.bc_value, parser_bc)]
                    canonical_match = False
                    canonical = (
                        db_row.bc_g1_published or db_row.bc_g1_estimated
                        if bc_type == "g1"
                        else db_row.bc_g7_published or db_row.bc_g7_estimated
                    )
                    if canonical is not None and _numbers_agree(canonical, parser_bc):
                        canonical_match = True
                    if matches or canonical_match:
                        outcome.bc_present_in_db += 1
                    else:
                        outcome.bc_missing_from_db += 1

                diffs = _compare_bullet(pentity, db_row, bc_sources)

            else:  # cartridge
                db_row = cartridge_by_url.get(url)
                if db_row is None:
                    outcome.not_in_db += 1
                    not_in_db_samples["cartridge"].append(url)
                    continue
                if db_row.is_locked:
                    outcome.locked_rows += 1
                diffs = _compare_cartridge(pentity, db_row)

            if diffs:
                outcome.in_db_diff += 1
                diff_rows.append((url, entity_type, diffs))
                for d in diffs:
                    field_diff_counter[d.split(":", 1)[0]] += 1
            else:
                outcome.in_db_match += 1

    # ── Render ──────────────────────────────────────────────────────────
    lines = []
    lines.append(f"# Parser vs DB comparison — {parser_name}")
    lines.append("")
    lines.append(
        f"Ran `{parser_name}` parser over every cached page on `{domain}` and joined by "
        f"`source_url` to the current DB. DB is read-only — no inserts."
    )
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Manufacturer (DB): `{mfr_name}`")
    lines.append(f"- URLs in fetched cache: **{outcome.total_urls}**")
    lines.append(f"- Parser extracted a result: **{outcome.total_urls - outcome.parser_declined}**")
    lines.append(f"- Parser declined: {outcome.parser_declined}")
    lines.append(f"- Matched DB row, all fields agree: **{outcome.in_db_match}**")
    lines.append(f"- Matched DB row, at least one field differs: **{outcome.in_db_diff}**")
    lines.append(
        f"- URL not in DB (filtered by rejected-caliber list, failed to resolve, or not ingested): "
        f"**{outcome.not_in_db}**"
    )
    lines.append(f"- Matched rows that are `is_locked=True` (curation-protected): {outcome.locked_rows}")
    lines.append("")
    lines.append(
        f"- Parser BC values already represented in DB (canonical or bullet_bc_source): "
        f"**{outcome.bc_present_in_db}**"
    )
    lines.append(
        f"- Parser BC values **not** in DB (new data the parser would add): " f"**{outcome.bc_missing_from_db}**"
    )
    lines.append("")

    if field_diff_counter:
        lines.append("## Discrepancies by field")
        lines.append("")
        lines.append("| Field | Count |")
        lines.append("|---|---:|")
        for field, n in field_diff_counter.most_common():
            lines.append(f"| `{field}` | {n} |")
        lines.append("")

    if diff_rows:
        lines.append("## Diffs (first 30)")
        lines.append("")
        for url, entity_type, diffs in diff_rows[:30]:
            lines.append(f"### `{url}` _{entity_type}_")
            for d in diffs:
                lines.append(f"- {d}")
            lines.append("")

    if not_in_db_samples:
        lines.append("## URLs not present in DB")
        lines.append("")
        for entity_type, urls in not_in_db_samples.items():
            lines.append(f"### {entity_type} ({len(urls)})")
            for url in urls[:20]:
                lines.append(f"- `{url}`")
            if len(urls) > 20:
                lines.append(f"- … {len(urls) - 20} more")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Parser vs DB comparison report.")
    parser.add_argument("parser_name", help="Parser short name (e.g. 'hornady')")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output markdown path (defaults to docs/parser_vs_db_<name>.md)",
    )
    args = parser.parse_args()
    out = args.out or Path(__file__).resolve().parent.parent / "docs" / f"parser_vs_db_{args.parser_name}.md"
    return run_report(args.parser_name, out)


if __name__ == "__main__":
    sys.exit(main())
