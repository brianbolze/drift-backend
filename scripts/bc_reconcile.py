"""Reconcile canonical BC values on Bullet from BulletBCSource observations.

For each bullet with ≥1 BC source, pick a canonical bc_g1 / bc_g7 value using
the priority ladder defined in `BC_SOURCE_PRIORITY` (tie-break: newest
source_date). Route to bc_*_published or bc_*_estimated based on source type.

Bullets whose multi-source BC disagreement exceeds BC_DISAGREEMENT_THRESHOLDS
are skipped — the existing column values stay untouched — and an entry is
written to a YAML draft under `data/patches/drafts/` for operator review.

Bullets with is_locked=True are always skipped.

Usage:
    python scripts/bc_reconcile.py                 # dry-run preview
    python scripts/bc_reconcile.py --commit        # write to DB
    python scripts/bc_reconcile.py --bullet-id X   # single bullet
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from drift.database import get_session_factory
from drift.models import Bullet, BulletBCSource, Manufacturer
from drift.pipeline.config import BC_DISAGREEMENT_THRESHOLDS, BC_SOURCE_PRIORITY

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFTS_DIR = PROJECT_ROOT / "data" / "patches" / "drafts"


# ── Decision model ──────────────────────────────────────────────────────────


@dataclass
class ReconcileReview:
    """A bullet whose sources disagree beyond threshold — operator adjudicates."""

    bullet_id: str
    bullet_name: str
    manufacturer_name: str
    bc_type: str
    spread_pct: float
    threshold: float
    sources: list[BulletBCSource]
    recommended: BulletBCSource  # highest-priority source (for comment)


@dataclass
class ReconcileUpdate:
    """A bullet whose canonical value can be (re)written."""

    bullet_id: str
    bullet_name: str
    manufacturer_name: str
    bc_type: str
    column: str  # e.g. "bc_g1_published"
    new_value: float
    current_value: float | None
    chosen: BulletBCSource


@dataclass
class ReconcileStats:
    """Summary of a reconcile run."""

    inspected: int = 0
    locked_skipped: int = 0
    no_change: int = 0
    updated: int = 0
    review_required: int = 0
    updates: list[ReconcileUpdate] = field(default_factory=list)
    reviews: list[ReconcileReview] = field(default_factory=list)


# ── Decision logic ──────────────────────────────────────────────────────────


def _spread_pct(values: list[float]) -> float:
    """Return (max - min) / mean — zero when only one value."""
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return (max(values) - min(values)) / mean if mean > 0 else 0.0


def _source_sort_key(s: BulletBCSource) -> tuple[int, float]:
    """Priority ascending, then source_date descending (newer wins)."""
    priority = BC_SOURCE_PRIORITY.get(s.source, 99)
    date_ord = -s.source_date.timestamp() if s.source_date else 0.0
    return (priority, date_ord)


def _target_column(bc_type: str, source_name: str) -> str:
    """Return 'bc_<type>_published' or 'bc_<type>_estimated' for the chosen source."""
    suffix = "estimated" if source_name == "estimated" else "published"
    return f"bc_{bc_type}_{suffix}"


def reconcile_one(bullet: Bullet, bc_type: str) -> ReconcileUpdate | ReconcileReview | None:
    """Decide canonical BC for one (bullet, bc_type). None if no sources of that type."""
    sources = [s for s in bullet.bc_sources if s.bc_type == bc_type]
    if not sources:
        return None

    threshold = BC_DISAGREEMENT_THRESHOLDS.get(bc_type, 0.08)
    values = [s.bc_value for s in sources]
    spread = _spread_pct(values)

    sources_sorted = sorted(sources, key=_source_sort_key)
    top = sources_sorted[0]

    if spread > threshold and len(sources) > 1:
        return ReconcileReview(
            bullet_id=bullet.id,
            bullet_name=bullet.name,
            manufacturer_name=bullet.manufacturer.name if bullet.manufacturer else "?",
            bc_type=bc_type,
            spread_pct=spread,
            threshold=threshold,
            sources=sources_sorted,
            recommended=top,
        )

    column = _target_column(bc_type, top.source)
    current = getattr(bullet, column)
    return ReconcileUpdate(
        bullet_id=bullet.id,
        bullet_name=bullet.name,
        manufacturer_name=bullet.manufacturer.name if bullet.manufacturer else "?",
        bc_type=bc_type,
        column=column,
        new_value=top.bc_value,
        current_value=current,
        chosen=top,
    )


# ── Session-level orchestration ──────────────────────────────────────────────


def _fetch_bullets(session: Session, bullet_id: str | None) -> list[Bullet]:
    stmt = select(Bullet).options(
        selectinload(Bullet.bc_sources),
        selectinload(Bullet.manufacturer),
    )
    if bullet_id:
        stmt = stmt.where(Bullet.id == bullet_id)
    return list(session.scalars(stmt))


def _values_equal(a: float | None, b: float) -> bool:
    if a is None:
        return False
    return abs(a - b) < 1e-9


def run_reconcile(session: Session, bullet_id: str | None = None) -> ReconcileStats:
    stats = ReconcileStats()
    bullets = _fetch_bullets(session, bullet_id)
    for bullet in bullets:
        stats.inspected += 1
        if bullet.is_locked:
            stats.locked_skipped += 1
            continue
        for bc_type in ("g1", "g7"):
            decision = reconcile_one(bullet, bc_type)
            if decision is None:
                continue
            if isinstance(decision, ReconcileReview):
                stats.review_required += 1
                stats.reviews.append(decision)
                continue
            # ReconcileUpdate
            if _values_equal(decision.current_value, decision.new_value):
                stats.no_change += 1
                continue
            setattr(bullet, decision.column, decision.new_value)
            stats.updated += 1
            stats.updates.append(decision)
    return stats


# ── Draft YAML emission ─────────────────────────────────────────────────────


def _draft_filename() -> Path:
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    # Numbered prefix to stay consistent with data/patches/ convention.
    # Scan for existing drafts to pick the next number; if none, start at 001.
    existing = sorted(DRAFTS_DIR.glob("*_bc_reconcile_review_*.yaml"))
    next_num = 1
    if existing:
        last = existing[-1].stem
        try:
            next_num = int(last.split("_", 1)[0]) + 1
        except ValueError:
            pass
    return DRAFTS_DIR / f"{next_num:03d}_bc_reconcile_review_{date_str}.yaml"


def _yaml_quote(s: str) -> str:
    """Minimal YAML-safe quoting — double-quote + escape backslashes/quotes."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'  # noqa: B907


def _render_draft(reviews: list[ReconcileReview]) -> str:
    date_str = datetime.now(tz=timezone.utc).date().isoformat()
    patch_id = _yaml_quote(f"bc_reconcile_review_{date_str}")
    quoted_date = _yaml_quote(date_str)
    header = f"""# BC reconciliation — review-required cases generated {date_str}
# Each block below has its `set:` block COMMENTED OUT so `make curate` will
# reject this file until the operator picks a value. Workflow:
#   1. For each bullet below, inspect the source list and pick the correct value.
#   2. Uncomment the `set:` block and fill in ONE of the recommended values.
#   3. Move this file to data/patches/ and run `make curate-commit`.

patch:
  id: {patch_id}
  author: "bc_reconcile.py (automated draft)"
  date: {quoted_date}
  description: "BC reconciliation — bullets with multi-source disagreement above threshold."

operations:
"""

    blocks: list[str] = []
    for r in reviews:
        src_lines = "\n".join(
            (
                f"  #   priority={BC_SOURCE_PRIORITY.get(s.source, 99)} "
                f"{s.source:<18} "
                f"{(s.source_date.date().isoformat() if s.source_date else 'unknown'):<10} "
                f"value={s.bc_value:.4f}" + (f"  {s.source_url}" if s.source_url else "")
            )
            for s in r.sources
        )
        column = _target_column(r.bc_type, r.recommended.source)
        blocks.append(f"""
  # ============================================================
  # {r.manufacturer_name} — {r.bullet_name}
  # bullet_id: {r.bullet_id}
  # bc_type:   {r.bc_type.upper()}
  # spread:    {r.spread_pct * 100:.1f}% (threshold: {r.threshold * 100:.1f}%)
  # sources:
{src_lines}
  # recommended by priority ladder: {r.recommended.source} ({r.recommended.bc_value:.4f})
  # ============================================================
  - action: update_bullet
    manufacturer: {_yaml_quote(r.manufacturer_name)}
    name: {_yaml_quote(r.bullet_name)}
    # set:  # UNCOMMENT AND PICK ONE
    #   {column}: {r.recommended.bc_value:.4f}
""")
    return header + "".join(blocks)


def write_draft_if_any(reviews: list[ReconcileReview]) -> Path | None:
    if not reviews:
        return None
    path = _draft_filename()
    path.write_text(_render_draft(reviews), encoding="utf-8")
    return path


# ── Reporting ────────────────────────────────────────────────────────────────


def print_report(stats: ReconcileStats, commit: bool, draft_path: Path | None) -> None:
    print()
    print("─" * 70)
    mode = "COMMIT" if commit else "DRY-RUN"
    print(f"BC reconciliation summary ({mode})")
    print(f"  bullets inspected:    {stats.inspected}")
    print(f"  is_locked skipped:    {stats.locked_skipped}")
    print(f"  unchanged (same val): {stats.no_change}")
    print(f"  updated:              {stats.updated}")
    print(f"  review-required:      {stats.review_required}")

    if stats.updates:
        print()
        print(f"Updates ({min(10, len(stats.updates))} of {len(stats.updates)} shown):")
        for u in stats.updates[:10]:
            cur = f"{u.current_value:.4f}" if u.current_value is not None else "NULL"
            print(
                f"  {u.manufacturer_name[:20]:<20} {u.bullet_name[:40]:<40} "
                f"{u.column:<20} {cur} → {u.new_value:.4f}  (src: {u.chosen.source})"
            )

    if draft_path:
        print()
        print(f"✎ Review-required draft written: {draft_path.relative_to(PROJECT_ROOT)}")
        print("  Edit, move to data/patches/, then run `make curate-commit`.")


# ── Main ─────────────────────────────────────────────────────────────────────


def _iter_all_manufacturers(session: Session) -> Iterable[Manufacturer]:  # pragma: no cover
    # Helper left here for future diagnostic hooks.
    return session.scalars(select(Manufacturer))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile canonical BC values from BulletBCSource rows")
    parser.add_argument("--commit", action="store_true", help="Write changes to DB (default: dry-run)")
    parser.add_argument("--bullet-id", type=str, default=None, help="Reconcile a single bullet by id")
    parser.add_argument(
        "--no-draft",
        action="store_true",
        help="Skip writing the review-required draft YAML (summary only)",
    )
    args = parser.parse_args()

    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        stats = run_reconcile(session, bullet_id=args.bullet_id)
        draft_path = None if args.no_draft else write_draft_if_any(stats.reviews)

        if args.commit:
            session.commit()
            logger.info("Reconciliation committed.")
        else:
            session.rollback()
            logger.info("Dry-run complete — no changes written.")

        print_report(stats, args.commit, draft_path)
    except Exception:
        session.rollback()
        logger.exception("Reconciliation failed — rolled back.")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
