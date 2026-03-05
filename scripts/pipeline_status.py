"""Coverage dashboard — shows pipeline progress and DB entity coverage.

Queries the database for current entity counts and compares against
the shopping list targets to show coverage gaps.

Usage:
    python scripts/pipeline_status.py
    python scripts/pipeline_status.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from sqlalchemy import func

from drift.database import get_session_factory
from drift.models.bullet import Bullet
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge
from drift.models.chamber import Chamber
from drift.models.manufacturer import Manufacturer
from drift.models.rifle_model import RifleModel
from drift.pipeline.config import (
    DATA_DIR,
    EXTRACTED_DIR,
    FETCHED_DIR,
    MANIFEST_PATH,
    REDUCED_DIR,
    REVIEW_DIR,
    STORE_REPORT_PATH,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _count_files(directory: Path, pattern: str = "*.json") -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def _print_section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Pipeline coverage dashboard")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-caliber breakdown")
    args = parser.parse_args()

    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        # ── Database entity counts ───────────────────────────────────────
        _print_section("Database Entity Counts")

        counts = {
            "Manufacturers": session.query(func.count(Manufacturer.id)).scalar(),
            "Calibers": session.query(func.count(Caliber.id)).scalar(),
            "Chambers": session.query(func.count(Chamber.id)).scalar(),
            "Bullets": session.query(func.count(Bullet.id)).scalar(),
            "Cartridges": session.query(func.count(Cartridge.id)).scalar(),
            "Rifle Models": session.query(func.count(RifleModel.id)).scalar(),
        }

        for label, count in counts.items():
            print(f"  {label:20s}: {count:>5d}")

        # ── Pipeline file counts ─────────────────────────────────────────
        _print_section("Pipeline File Counts")

        manifest_count = 0
        if MANIFEST_PATH.exists():
            try:
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                manifest_count = len(manifest)
            except (json.JSONDecodeError, TypeError):
                pass

        pipeline_counts = {
            "Manifest entries": manifest_count,
            "Fetched (raw)": _count_files(FETCHED_DIR, "*.json"),
            "Reduced": _count_files(REDUCED_DIR, "*.json"),
            "Extracted": _count_files(EXTRACTED_DIR, "*.json"),
            "Flagged": 0,
        }

        flagged_path = REVIEW_DIR / "flagged.json"
        if flagged_path.exists():
            try:
                flagged = json.loads(flagged_path.read_text(encoding="utf-8"))
                pipeline_counts["Flagged"] = len(flagged)
            except (json.JSONDecodeError, TypeError):
                pass

        for label, count in pipeline_counts.items():
            print(f"  {label:20s}: {count:>5d}")

        # ── Coverage by caliber ──────────────────────────────────────────
        if args.verbose:
            _print_section("Coverage by Caliber (LR Priority)")

            # Get calibers ordered by LR rank
            calibers = (
                session.query(Caliber)
                .filter(Caliber.lr_popularity_rank.isnot(None))
                .order_by(Caliber.lr_popularity_rank)
                .all()
            )

            if calibers:
                print(f"  {'Rank':>4s}  {'Caliber':<30s}  {'Bullets':>7s}  {'Carts':>5s}  {'Rifles':>6s}")
                print(f"  {'─'*4}  {'─'*30}  {'─'*7}  {'─'*5}  {'─'*6}")

                for cal in calibers:
                    n_bullets = session.query(func.count(Bullet.id)).filter(Bullet.caliber_id == cal.id).scalar()
                    n_carts = session.query(func.count(Cartridge.id)).filter(Cartridge.caliber_id == cal.id).scalar()
                    # Rifles go through chamber → caliber
                    n_rifles = (
                        session.query(func.count(RifleModel.id))
                        .join(Chamber, RifleModel.chamber_id == Chamber.id)
                        .join(
                            Caliber,
                            Chamber.id.in_(
                                session.query(func.distinct(Caliber.id)).filter(Caliber.id == cal.id)  # noqa: E501
                            ),
                        )
                        .scalar()
                    ) or 0

                    # Simpler rifle count via ChamberAcceptsCaliber
                    from drift.models.chamber import ChamberAcceptsCaliber

                    chamber_ids = [
                        link.chamber_id
                        for link in session.query(ChamberAcceptsCaliber)
                        .filter(ChamberAcceptsCaliber.caliber_id == cal.id)
                        .all()
                    ]
                    n_rifles = (
                        session.query(func.count(RifleModel.id)).filter(RifleModel.chamber_id.in_(chamber_ids)).scalar()
                        if chamber_ids
                        else 0
                    )

                    rank = cal.lr_popularity_rank or 0
                    print(f"  {rank:>4d}  {cal.name:<30s}  {n_bullets:>7d}  {n_carts:>5d}  {n_rifles:>6d}")
            else:
                print("  No calibers with LR popularity rank found.")

        # ── Store report summary ─────────────────────────────────────────
        if STORE_REPORT_PATH.exists():
            _print_section("Latest Store Report")
            try:
                report = json.loads(STORE_REPORT_PATH.read_text(encoding="utf-8"))
                mode = report.get("mode", "?")
                print(f"  Mode: {mode}")
                for etype, s in report.get("stats", {}).items():
                    print(
                        f"  {etype:12s}: {s.get('created', 0)} created, "
                        f"{s.get('matched', 0)} matched, "
                        f"{s.get('flagged', 0)} flagged"
                    )
            except (json.JSONDecodeError, TypeError):
                print("  (Could not parse store report)")

        # ── Shopping list comparison ─────────────────────────────────────
        shopping_list_path = DATA_DIR / "shopping_list.json"
        if shopping_list_path.exists():
            _print_section("Shopping List Coverage")
            try:
                shopping = json.loads(shopping_list_path.read_text(encoding="utf-8"))
                summary = shopping.get("summary", {})
                print(f"  Priority calibers: {summary.get('priority_calibers', '?')}")
                for etype in ["bullets", "cartridges", "rifles"]:
                    have = summary.get(f"total_{etype}_have", 0)
                    target = summary.get(f"total_{etype}_target", 0)
                    gap = summary.get(f"total_{etype}_gap", 0)
                    pct = (have / target * 100) if target > 0 else 0
                    bar_len = int(pct / 5)
                    bar = "█" * bar_len + "░" * (20 - bar_len)
                    print(f"  {etype:12s}: {have:>4d}/{target:<4d} ({pct:>5.1f}%) [{bar}] gap={gap}")
            except (json.JSONDecodeError, TypeError):
                print("  (Could not parse shopping list)")

        print()

    finally:
        session.close()


if __name__ == "__main__":
    main()
