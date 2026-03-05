"""Import new calibers, chambers, chamber_accepts_caliber, and caliber_platform
records from the JSON files produced by the domain-expert curation task.

Usage:
    python scripts/import_calibers.py                # dry-run (default)
    python scripts/import_calibers.py --apply        # actually write to DB

Reads from:
    data/calibers.json
    data/chambers.json
    data/chamber_accepts_caliber.json
    data/caliber_platforms.json

Inserts into the existing drift.db without touching existing rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path when running as a script
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


def build_caliber_lookup(session: Session) -> dict[str, str]:
    """Return {caliber.name: caliber.id} for all calibers in the DB."""
    return {c.name: c.id for c in session.query(Caliber).all()}


def build_chamber_lookup(session: Session) -> dict[str, str]:
    """Return {chamber.name: chamber.id} for all chambers in the DB."""
    return {c.name: c.id for c in session.query(Chamber).all()}


def build_platform_lookup(session: Session) -> dict[str, str]:
    """Return {platform.short_name: platform.id} for all platforms in the DB."""
    return {p.short_name: p.id for p in session.query(Platform).all()}


def import_calibers(session: Session) -> int:
    """Insert new calibers from calibers.json. Returns count inserted."""
    data = load_json("calibers.json")
    existing = {c.name for c in session.query(Caliber.name).all()}

    count = 0
    for entry in data:
        if entry["name"] in existing:
            print(f"  SKIP (exists): {entry['name']}")
            continue

        # parent_caliber_name -> parent_caliber_id (resolve after all inserts)
        # popularity_rank is handled by import_rankings.py, not the Caliber model
        skip_keys = {"parent_caliber_name", "popularity_rank"}
        row = {k: v for k, v in entry.items() if k not in skip_keys}
        session.add(Caliber(**row))
        count += 1

    session.flush()

    # Second pass: resolve parent_caliber_name -> parent_caliber_id
    cal_lookup = build_caliber_lookup(session)
    parent_count = 0
    for entry in data:
        parent_name = entry.get("parent_caliber_name")
        if not parent_name:
            continue
        cal_id = cal_lookup.get(entry["name"])
        parent_id = cal_lookup.get(parent_name)
        if not cal_id:
            continue
        if not parent_id:
            print(f"  WARNING: parent {parent_name!r} not found for {entry['name']!r}")
            continue
        session.query(Caliber).filter(Caliber.id == cal_id).update({"parent_caliber_id": parent_id})
        parent_count += 1

    session.flush()
    print(f"  Inserted {count} calibers ({parent_count} parent links resolved)")
    return count


def import_chambers(session: Session) -> int:
    """Insert new chambers from chambers.json. Returns count inserted."""
    data = load_json("chambers.json")
    existing = {c.name for c in session.query(Chamber.name).all()}

    count = 0
    for entry in data:
        if entry["name"] in existing:
            print(f"  SKIP (exists): {entry['name']}")
            continue
        session.add(Chamber(**entry))
        count += 1

    session.flush()
    print(f"  Inserted {count} chambers")
    return count


def import_chamber_accepts_caliber(session: Session) -> int:
    """Insert new chamber-caliber mappings. Returns count inserted."""
    data = load_json("chamber_accepts_caliber.json")
    cal_lookup = build_caliber_lookup(session)
    ch_lookup = build_chamber_lookup(session)

    count = 0
    warnings = 0
    for entry in data:
        cal_id = cal_lookup.get(entry["caliber_name"])
        ch_id = ch_lookup.get(entry["chamber_name"])

        if not cal_id:
            print(f"  WARNING: caliber {entry['caliber_name']!r} not found — skipping")
            warnings += 1
            continue
        if not ch_id:
            print(f"  WARNING: chamber {entry['chamber_name']!r} not found — skipping")
            warnings += 1
            continue

        # Check for existing mapping
        existing = session.query(ChamberAcceptsCaliber).filter_by(chamber_id=ch_id, caliber_id=cal_id).first()
        if existing:
            print(f"  SKIP (exists): {entry['chamber_name']} -> {entry['caliber_name']}")
            continue

        session.add(
            ChamberAcceptsCaliber(
                chamber_id=ch_id,
                caliber_id=cal_id,
                is_primary=entry["is_primary"],
            )
        )
        count += 1

    session.flush()
    print(f"  Inserted {count} chamber-caliber mappings ({warnings} warnings)")
    return count


def import_caliber_platforms(session: Session) -> int:
    """Insert new caliber-platform mappings. Returns count inserted."""
    data = load_json("caliber_platforms.json")
    cal_lookup = build_caliber_lookup(session)
    plat_lookup = build_platform_lookup(session)

    count = 0
    warnings = 0
    for entry in data:
        cal_id = cal_lookup.get(entry["caliber_name"])
        plat_id = plat_lookup.get(entry["platform"])

        if not cal_id:
            print(f"  WARNING: caliber {entry['caliber_name']!r} not found — skipping")
            warnings += 1
            continue
        if not plat_id:
            print(f"  WARNING: platform {entry['platform']!r} not found — skipping")
            warnings += 1
            continue

        # Check for existing mapping
        existing = session.query(CaliberPlatform).filter_by(caliber_id=cal_id, platform_id=plat_id).first()
        if existing:
            print(f"  SKIP (exists): {entry['caliber_name']} on {entry['platform']}")
            continue

        session.add(
            CaliberPlatform(
                caliber_id=cal_id,
                platform_id=plat_id,
                popularity_rank=entry.get("rank"),
                notes=entry.get("notes"),
            )
        )
        count += 1

    session.flush()
    print(f"  Inserted {count} caliber-platform mappings ({warnings} warnings)")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import curated caliber/chamber data from JSON files into drift.db.")
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
        print("Importing caliber/chamber data...")
        print()

        print("[1/4] Calibers:")
        import_calibers(session)
        print()

        print("[2/4] Chambers:")
        import_chambers(session)
        print()

        print("[3/4] Chamber-Caliber Mappings:")
        import_chamber_accepts_caliber(session)
        print()

        print("[4/4] Caliber-Platform Mappings:")
        import_caliber_platforms(session)
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
