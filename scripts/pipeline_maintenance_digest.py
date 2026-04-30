"""Weekly pipeline-maintenance digest.

Aggregates every maintenance-related artifact into a single markdown file so
the operator can answer "does this week need my attention?" at a glance.

Currently aggregates:
  - Sitemap discoveries (new + removed URLs) for the target week
  - Draft curation patches awaiting review (data/patches/drafts/)
  - Open review items (data/pipeline/review/flagged.json)

As future primitives land (refresh/drift reports, BC consensus outliers,
Firecrawl budget), they plug into the same digest file.

Output: data/pipeline/maintenance/YYYY-WW.md (ISO week).

Usage:
    python scripts/pipeline_maintenance_digest.py               # current week
    python scripts/pipeline_maintenance_digest.py --week 2026-W17
    python scripts/pipeline_maintenance_digest.py --stdout      # print, do not write
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from drift.pipeline.config import DATA_DIR

SITEMAPS_DIR = DATA_DIR / "sitemaps"
DISCOVERED_LOG = SITEMAPS_DIR / "discovered_urls.jsonl"
REMOVED_LOG = SITEMAPS_DIR / "removed_urls.jsonl"
MAINTENANCE_DIR = DATA_DIR / "maintenance"
REVIEW_FLAGGED = DATA_DIR / "review" / "flagged.json"
PATCHES_DRAFTS = Path(__file__).resolve().parent.parent / "data" / "patches" / "drafts"


# ── Week helpers ─────────────────────────────────────────────────────────────


def _parse_week(week_str: str) -> tuple[int, int]:
    """Parse 'YYYY-Www' (ISO week) → (year, week)."""
    try:
        year_str, week_part = week_str.split("-W")
        return int(year_str), int(week_part)
    except (ValueError, AttributeError) as e:
        raise SystemExit(f"Invalid --week format: {week_str!r} — expected 'YYYY-Www' (e.g. 2026-W17)") from e


def _week_bounds(year: int, week: int) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes (UTC) for the given ISO year/week."""
    start_date = date.fromisocalendar(year, week, 1)  # Monday
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    return start, end


def _current_iso_week() -> str:
    year, week, _ = datetime.now(tz=timezone.utc).isocalendar()
    return f"{year}-W{week:02d}"


# ── Log readers ──────────────────────────────────────────────────────────────


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _records_in_week(records: list[dict], key: str, start: datetime, end: datetime) -> list[dict]:
    out: list[dict] = []
    for rec in records:
        ts_raw = rec.get(key)
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if start <= ts < end:
            out.append(rec)
    return out


# ── Section builders ─────────────────────────────────────────────────────────


def _section_discoveries(start: datetime, end: datetime) -> str:
    discovered = _records_in_week(_read_jsonl(DISCOVERED_LOG), "discovered_at", start, end)
    removed = _records_in_week(_read_jsonl(REMOVED_LOG), "removed_at", start, end)

    if not discovered and not removed:
        return "## Sitemap discoveries\n\n_No sitemap activity this week._\n"

    by_mfr: dict[str, Counter] = {}
    for rec in discovered:
        slug = rec.get("manufacturer_slug", "?")
        by_mfr.setdefault(slug, Counter())[rec.get("entity_type", "?")] += 1

    lines = ["## Sitemap discoveries\n"]
    lines.append(f"**New URLs discovered:** {len(discovered)}  ")
    lines.append(f"**URLs removed from sitemaps:** {len(removed)}\n")

    if by_mfr:
        lines.append("| Manufacturer | Bullets | Cartridges | Rifles | Unclassified | Total |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for slug in sorted(by_mfr):
            c = by_mfr[slug]
            total = sum(c.values())
            lines.append(
                f"| {slug} | {c.get('bullet', 0)} | {c.get('cartridge', 0)} | "
                f"{c.get('rifle', 0)} | {c.get('unclassified', 0)} | {total} |"
            )
        lines.append("")

    # Per-manufacturer discovery files available for merge
    discovery_dir = SITEMAPS_DIR / "discovered"
    if discovery_dir.exists():
        week_files = [
            p
            for p in sorted(discovery_dir.glob("*.json"))
            if start <= datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < end
        ]
        if week_files:
            lines.append("**Ready-to-merge JSON files** (cowork format):")
            for p in week_files:
                lines.append(f"- `{p.relative_to(DATA_DIR.parent.parent)}`")
            lines.append("")
            lines.append("Merge with: `python scripts/merge_cowork_results.py <file> --discovery-method sitemap`")
            lines.append("")

    return "\n".join(lines)


def _section_draft_patches() -> str:
    if not PATCHES_DRAFTS.exists():
        return "## Draft curation patches\n\n_No draft patches awaiting review._\n"

    drafts = sorted(PATCHES_DRAFTS.glob("*.yaml"))
    if not drafts:
        return "## Draft curation patches\n\n_No draft patches awaiting review._\n"

    lines = ["## Draft curation patches\n"]
    lines.append(f"**{len(drafts)} patch(es) awaiting operator review in `data/patches/drafts/`**\n")
    for p in drafts:
        lines.append(f"- `{p.name}`")
    lines.append("")
    lines.append("After review, move approved patches to `data/patches/` and run `make curate`.")
    lines.append("")
    return "\n".join(lines)


def _section_flagged() -> str:
    if not REVIEW_FLAGGED.exists():
        return "## Flagged extraction items\n\n_No flagged items file present._\n"

    try:
        flagged = json.loads(REVIEW_FLAGGED.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "## Flagged extraction items\n\n_Flagged file present but unreadable._\n"

    if not isinstance(flagged, list) or not flagged:
        return "## Flagged extraction items\n\n_No flagged items._\n"

    reason_counts: Counter = Counter(item.get("reason", "?") for item in flagged)
    lines = ["## Flagged extraction items\n"]
    lines.append(f"**{len(flagged)} item(s) flagged during extraction** (cumulative, not just this week):\n")
    for reason, n in reason_counts.most_common():
        lines.append(f"- `{reason}`: {n}")
    lines.append("")
    lines.append(f"Full list: `{REVIEW_FLAGGED.relative_to(DATA_DIR.parent.parent)}`")
    lines.append("")
    return "\n".join(lines)


def _section_placeholder(title: str, reason: str) -> str:
    return f"## {title}\n\n_{reason}_\n"


# ── Main ─────────────────────────────────────────────────────────────────────


def build_digest(year: int, week: int) -> str:
    start, end = _week_bounds(year, week)
    iso_week = f"{year}-W{week:02d}"

    parts = [
        f"# Pipeline Maintenance Digest — {iso_week}",
        "",
        f"Week range: {start.date()} → {(end - timedelta(days=1)).date()} (UTC)  ",
        f"Generated at: {datetime.now(tz=timezone.utc).isoformat()}",
        "",
        "---",
        "",
        _section_discoveries(start, end),
        _section_draft_patches(),
        _section_flagged(),
        _section_placeholder(
            "URL refreshes",
            "Not yet populated — `scripts/pipeline_refresh.py` lands in Primitive 2.",
        ),
        _section_placeholder(
            "BC consensus outliers",
            "Not yet populated — `scripts/bc_reconcile.py` lands in Primitive 3a.",
        ),
        _section_placeholder(
            "Fetch budget",
            "Not yet populated — wired in once refresh + Firecrawl fallback are live.",
        ),
        "---",
        "",
        "_Digest produced by `scripts/pipeline_maintenance_digest.py`._",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly pipeline-maintenance digest")
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        help="ISO week to generate (default: current). Example: 2026-W17",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default: data/pipeline/maintenance/YYYY-WW.md)",
    )
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing a file")
    args = parser.parse_args()

    week_str = args.week or _current_iso_week()
    year, week = _parse_week(week_str)

    content = build_digest(year, week)

    if args.stdout:
        print(content)
        return

    out_path = args.out or (MAINTENANCE_DIR / f"{year}-W{week:02d}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"✓ Wrote digest: {out_path}")


if __name__ == "__main__":
    main()
