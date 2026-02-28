"""Seed the drift database from data/seed.sql.

Usage:
    python scripts/seed_db.py          # load seed data (skips existing rows)
    python scripts/seed_db.py --reset  # wipe all data tables and reload

Requires: alembic upgrade head to have been run first (schema must exist).
Seed file: data/seed.sql (auto-generated from verified drift.db)
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from drift.database import get_engine  # noqa: E402

SEED_SQL = _ROOT / "data" / "seed.sql"

# Tables in FK-safe deletion order (children before parents).
TABLES_DELETE_ORDER = [
    "rifle_model",
    "cartridge",
    "optic",
    "bullet_bc_source",
    "bullet",
    "reticle",
    "entity_alias",
    "caliber_platform",
    "chamber_accepts_caliber",
    "caliber",
    "chamber",
    "manufacturer",
    "platform",
]


def get_db_path() -> str:
    """Extract the SQLite file path from the engine URL."""
    engine = get_engine()
    url = str(engine.url)
    # sqlite:///data/drift.db -> data/drift.db
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    raise SystemExit(f"Expected SQLite URL, got: {url}")


def reset(db_path: str) -> None:
    """Delete all rows from data tables (preserves schema + alembic_version)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in TABLES_DELETE_ORDER:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count:
            conn.execute(f"DELETE FROM {table}")
            print(f"  deleted {count} rows from {table}")
    conn.commit()
    conn.close()


def seed(db_path: str) -> None:
    """Load seed data from SQL file. INSERT OR IGNORE makes this idempotent."""
    if not SEED_SQL.exists():
        raise SystemExit(f"Seed file not found: {SEED_SQL}")

    sql = SEED_SQL.read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.close()

    # Report what's in the DB now
    conn = sqlite3.connect(db_path)
    total = 0
    for table in reversed(TABLES_DELETE_ORDER):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count:
            print(f"  {table}: {count} rows")
            total += count
    conn.close()
    print(f"  total: {total} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed drift database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="wipe all data tables before seeding",
    )
    args = parser.parse_args()

    db_path = get_db_path()
    print(f"Database: {db_path}")

    if args.reset:
        print("Resetting data tables...")
        reset(db_path)

    print("Loading seed data...")
    seed(db_path)
    print("Done.")


if __name__ == "__main__":
    main()
