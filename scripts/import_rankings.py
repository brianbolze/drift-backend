"""Import expert-reviewed ranking data and apply corrections to drift.db.

This script handles:
  1. Adding the .25x47 Lapua caliber (critical omission flagged by reviewer)
  2. Setting overall_popularity_rank from overall_rankings.json
  3. Setting lr_popularity_rank + is_common_lr from lr_rankings.json
  4. Updating caliber_platform.popularity_rank from platform_rankings.json
  5. Applying is_common_lr corrections (reviewer feedback)
  6. Applying description corrections (reviewer feedback)

Usage:
    python scripts/import_rankings.py                # dry-run (default)
    python scripts/import_rankings.py --apply        # write to DB
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from drift.database import get_engine, get_session_factory  # noqa: E402
from drift.models import (  # noqa: E402
    Caliber,
    CaliberPlatform,
    Chamber,
    ChamberAcceptsCaliber,
    Platform,
)

DATA_DIR = _ROOT / "data"


def load_json(filename: str) -> list[dict]:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 1: Add .25x47 Lapua (critical omission)
# ---------------------------------------------------------------------------

def add_missing_calibers(session: Session) -> None:
    """Add calibers flagged as missing by the domain expert."""
    print("[1/6] Adding missing calibers...")

    # .25x47 Lapua — 7% of top 200 PRS shooters in 2025
    existing = session.query(Caliber).filter_by(name=".25x47 Lapua").first()
    if existing:
        print("  SKIP (exists): .25x47 Lapua")
    else:
        cal = Caliber(
            name=".25x47 Lapua",
            bullet_diameter_inches=0.257,
            case_length_inches=1.850,
            coal_inches=2.800,
            max_pressure_psi=62000,
            rim_type="rimless",
            action_length="short",
            year_introduced=2018,
            alt_names=["25×47", ".25x47L", "25x47 Lapua", "25-47 Lapua", ".25-47L"],
            description=(
                "Top-5 PRS competition cartridge as of 2025. "
                "Necked-down .47 Lapua case with excellent barrel life "
                "and flat trajectory. The .25-cal revolution in precision shooting."
            ),
            is_common_lr=True,
        )
        session.add(cal)
        session.flush()
        print("  Added: .25x47 Lapua")

        # Add corresponding chamber
        chamber = Chamber(name=".25x47 Lapua", source="Industry standard")
        session.add(chamber)
        session.flush()
        session.add(
            ChamberAcceptsCaliber(
                chamber_id=chamber.id,
                caliber_id=cal.id,
                is_primary=True,
            )
        )
        session.flush()
        print("  Added: .25x47 Lapua chamber + mapping")

        # Add bolt-action platform link
        plat = session.query(Platform).filter_by(short_name="bolt").first()
        if plat:
            session.add(
                CaliberPlatform(
                    caliber_id=cal.id,
                    platform_id=plat.id,
                    popularity_rank=None,
                )
            )
            session.flush()
            print("  Added: .25x47 Lapua -> bolt platform link")


# ---------------------------------------------------------------------------
# Step 2: Overall popularity rankings
# ---------------------------------------------------------------------------

def import_overall_rankings(session: Session) -> None:
    """Set overall_popularity_rank for all calibers."""
    print("[2/6] Importing overall popularity rankings...")
    data = load_json("overall_rankings.json")
    cal_lookup = {c.name: c for c in session.query(Caliber).all()}

    updated = 0
    warnings = 0
    for entry in data:
        cal = cal_lookup.get(entry["name"])
        if not cal:
            print(f"  WARNING: {entry['name']!r} not found in DB")
            warnings += 1
            continue
        cal.overall_popularity_rank = entry["overall_popularity_rank"]
        updated += 1

    session.flush()
    print(f"  Updated {updated} calibers ({warnings} warnings)")


# ---------------------------------------------------------------------------
# Step 3: LR popularity rankings + is_common_lr
# ---------------------------------------------------------------------------

def import_lr_rankings(session: Session) -> None:
    """Set lr_popularity_rank and correct is_common_lr flags."""
    print("[3/6] Importing LR popularity rankings...")
    data = load_json("lr_rankings.json")
    cal_lookup = {c.name: c for c in session.query(Caliber).all()}

    # First, clear all existing lr_popularity_rank values
    # (expert re-ranked from scratch)
    for cal in cal_lookup.values():
        if cal.lr_popularity_rank is not None:
            cal.lr_popularity_rank = None

    # Set new LR ranks
    updated = 0
    warnings = 0
    for entry in data:
        cal = cal_lookup.get(entry["name"])
        if not cal:
            print(f"  WARNING: {entry['name']!r} not found in DB")
            warnings += 1
            continue
        cal.lr_popularity_rank = entry["lr_popularity_rank"]
        cal.is_common_lr = entry.get("is_common_lr", True)
        updated += 1

    session.flush()
    print(f"  Updated {updated} LR rankings ({warnings} warnings)")

    # Report calibers that lost LR rank
    removed = []
    for cal in cal_lookup.values():
        # Had a rank before but now doesn't
        if cal.lr_popularity_rank is None and cal.name in {
            ".223 Remington", "5.56x45mm NATO", ".270 Winchester",
            ".30-06 Springfield", "7.62x51mm NATO", ".243 Winchester",
            "7mm-08 Remington", "6.5x55mm Swedish", ".300 AAC Blackout",
            ".338 Winchester Magnum",
        }:
            removed.append(cal.name)
    if removed:
        print(f"  Removed from LR ranking (per expert): {', '.join(removed)}")


# ---------------------------------------------------------------------------
# Step 4: is_common_lr corrections
# ---------------------------------------------------------------------------

def apply_is_common_lr_corrections(session: Session) -> None:
    """Apply specific is_common_lr corrections from reviewer."""
    print("[4/6] Applying is_common_lr corrections...")
    corrections = {
        # Expert: should be true
        ".25 Creedmoor": True,
        "6.5 Grendel": True,
        # Expert: keep as true (confirming)
        ".224 Valkyrie": True,
        ".277 Fury": True,
    }
    for name, value in corrections.items():
        cal = session.query(Caliber).filter_by(name=name).first()
        if cal:
            old = cal.is_common_lr
            cal.is_common_lr = value
            if old != value:
                print(f"  {name}: is_common_lr {old} -> {value}")
            else:
                print(f"  {name}: already {value} (no change)")
        else:
            print(f"  WARNING: {name!r} not found")
    session.flush()


# ---------------------------------------------------------------------------
# Step 5: Per-platform rankings
# ---------------------------------------------------------------------------

def import_platform_rankings(session: Session) -> None:
    """Update caliber_platform.popularity_rank from expert data."""
    print("[5/6] Importing per-platform rankings...")
    data = load_json("platform_rankings.json")
    cal_lookup = {c.name: c.id for c in session.query(Caliber).all()}
    plat_lookup = {p.short_name: p.id for p in session.query(Platform).all()}

    # Clear existing platform ranks (expert re-ranked from scratch)
    session.query(CaliberPlatform).update({"popularity_rank": None})
    session.flush()

    updated = 0
    warnings = 0
    for entry in data:
        cal_id = cal_lookup.get(entry["caliber_name"])
        plat_id = plat_lookup.get(entry["platform"])

        if not cal_id:
            print(f"  WARNING: caliber {entry['caliber_name']!r} not found")
            warnings += 1
            continue
        if not plat_id:
            print(f"  WARNING: platform {entry['platform']!r} not found")
            warnings += 1
            continue

        link = (
            session.query(CaliberPlatform)
            .filter_by(caliber_id=cal_id, platform_id=plat_id)
            .first()
        )
        if link:
            link.popularity_rank = entry["rank"]
            updated += 1
        else:
            # Create the link if it doesn't exist
            session.add(
                CaliberPlatform(
                    caliber_id=cal_id,
                    platform_id=plat_id,
                    popularity_rank=entry["rank"],
                )
            )
            updated += 1
            print(f"  NEW LINK: {entry['caliber_name']} on {entry['platform']} (rank {entry['rank']})")

    session.flush()
    print(f"  Updated {updated} platform rankings ({warnings} warnings)")


# ---------------------------------------------------------------------------
# Step 6: Description corrections
# ---------------------------------------------------------------------------

def apply_description_corrections(session: Session) -> None:
    """Apply description corrections flagged by reviewer."""
    print("[6/6] Applying description corrections...")

    corrections = {
        ".25 Creedmoor": (
            "Hornady-standardized (SAAMI 2025) .25-cal precision cartridge based on the 6.5 CM case. "
            "16% of top 200 PRS shooters in 2025. The .25-cal revolution in competition shooting."
        ),
    }
    for name, desc in corrections.items():
        cal = session.query(Caliber).filter_by(name=name).first()
        if cal:
            cal.description = desc
            print(f"  Updated: {name}")
        else:
            print(f"  WARNING: {name!r} not found")
    session.flush()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import expert-reviewed rankings and corrections into drift.db."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the database. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    engine = get_engine()
    session_factory = get_session_factory()
    session = session_factory()

    try:
        print("Importing expert review data...\n")

        add_missing_calibers(session)
        print()
        import_overall_rankings(session)
        print()
        import_lr_rankings(session)
        print()
        apply_is_common_lr_corrections(session)
        print()
        import_platform_rankings(session)
        print()
        apply_description_corrections(session)
        print()

        if args.apply:
            session.commit()
            print("Committed to database.")
        else:
            session.rollback()
            print("DRY RUN — no changes written. Use --apply to commit.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
