"""Export a production-ready SQLite database for the iOS app.

Copies drift.db → data/production/drift.db with the following transformations:
  - Drops pipeline-only tables: alembic_version, bullet_bc_source
  - Drops pipeline-only columns: data_source, is_locked, extraction_confidence,
    last_verified_at, created_at, updated_at, bc_source_notes,
    bullet_match_confidence, bullet_match_method
  - Removes zero-MV cartridges (no trajectory data)
  - Removes weight-mismatched cartridges (incorrect bullet linkage)
  - Removes bogus-diameter bullets (0.223" Sierra Hornet)
  - VACUUMs for minimal file size

Usage:
    python scripts/export_production_db.py              # default output: data/production/drift.db
    python scripts/export_production_db.py -o path.db   # custom output path
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

SOURCE_DB = Path("data/drift.db")

# Tables to drop entirely
DROP_TABLES = [
    "alembic_version",
    "bullet_bc_source",
]

# Columns to drop per table (pipeline/internal metadata)
DROP_COLUMNS: dict[str, list[str]] = {
    "bullet": [
        "data_source",
        "is_locked",
        "extraction_confidence",
        "last_verified_at",
        "bc_source_notes",
        "created_at",
        "updated_at",
    ],
    "cartridge": [
        "data_source",
        "is_locked",
        "extraction_confidence",
        "last_verified_at",
        "bullet_match_confidence",
        "bullet_match_method",
        "created_at",
        "updated_at",
    ],
    "rifle_model": [
        "data_source",
        "is_locked",
        "created_at",
        "updated_at",
    ],
    "manufacturer": ["created_at", "updated_at"],
    "caliber": ["created_at", "updated_at"],
    "chamber": ["created_at", "updated_at"],
    "optic": ["created_at", "updated_at"],
    "reticle": ["created_at", "updated_at"],
    "entity_alias": ["created_at", "updated_at"],
    "platform": ["created_at", "updated_at"],
    "caliber_platform": ["created_at", "updated_at"],
    "chamber_accepts_caliber": ["created_at", "updated_at"],
}


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return ordered column names for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def rebuild_table_without_columns(conn: sqlite3.Connection, table: str, drop_cols: list[str]) -> int:
    """Rebuild a table excluding specified columns. Returns columns kept."""
    all_cols = get_table_columns(conn, table)
    keep_cols = [c for c in all_cols if c not in drop_cols]

    if len(keep_cols) == len(all_cols):
        return 0  # nothing to drop

    cols_csv = ", ".join(keep_cols)
    conn.execute(f"CREATE TABLE _tmp_{table} AS SELECT {cols_csv} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE _tmp_{table} RENAME TO {table}")
    return len(all_cols) - len(keep_cols)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export production SQLite DB for iOS app")
    parser.add_argument("-o", "--output", default="data/production/drift.db", help="Output path")
    args = parser.parse_args()

    output = Path(args.output)

    if not SOURCE_DB.exists():
        print(f"ERROR: Source database not found: {SOURCE_DB}", file=sys.stderr)
        sys.exit(1)

    # Copy source to output
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_DB, output)
    print(f"Copied {SOURCE_DB} → {output}")

    conn = sqlite3.connect(output)
    conn.execute("PRAGMA foreign_keys = OFF")

    # ── Drop tables ────────────────────────────────────────────────────────
    for table in DROP_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"  Dropped table: {table}")

    # ── Remove bad records ─────────────────────────────────────────────────

    # Zero-MV cartridges (useless for trajectory computation)
    cursor = conn.execute("DELETE FROM cartridge WHERE muzzle_velocity_fps <= 0")
    print(f"  Removed {cursor.rowcount} zero-MV cartridges")

    # Weight-mismatched cartridges (incorrect bullet linkage)
    cursor = conn.execute("""
        DELETE FROM cartridge WHERE id IN (
            SELECT c.id FROM cartridge c
            JOIN bullet b ON c.bullet_id = b.id
            WHERE ABS(c.bullet_weight_grains - b.weight_grains) > 1.0
        )
    """)
    print(f"  Removed {cursor.rowcount} weight-mismatched cartridges")

    # Bogus-diameter bullet (Sierra .223 Hornet — should be .224)
    cursor = conn.execute("DELETE FROM bullet WHERE bullet_diameter_inches = 0.223")
    print(f"  Removed {cursor.rowcount} bogus-diameter bullets")

    # ── Drop columns ───────────────────────────────────────────────────────
    total_cols_dropped = 0
    for table, cols in DROP_COLUMNS.items():
        existing = get_table_columns(conn, table)
        cols_to_drop = [c for c in cols if c in existing]
        if cols_to_drop:
            n = rebuild_table_without_columns(conn, table, cols_to_drop)
            if n:
                total_cols_dropped += n
                print(f"  Dropped {n} columns from {table}")

    # ── Rebuild indexes ────────────────────────────────────────────────────
    # Table rebuilds drop indexes; recreate the important ones
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bullet_name ON bullet (name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bullet_sku ON bullet (sku)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bullet_product_line ON bullet (product_line)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bullet_manufacturer ON bullet (manufacturer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bullet_diameter ON bullet (bullet_diameter_inches)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cartridge_name ON cartridge (name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cartridge_sku ON cartridge (sku)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cartridge_caliber ON cartridge (caliber_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cartridge_bullet ON cartridge (bullet_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cartridge_manufacturer ON cartridge (manufacturer_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_manufacturer_name ON manufacturer (name)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_caliber_name ON caliber (name)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_chamber_name ON chamber (name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_optic_name ON optic (name)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_reticle_name ON reticle (name)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_entity_alias_entity_id ON entity_alias (entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_entity_alias_entity_type ON entity_alias (entity_type)")
    print(f"  Rebuilt indexes")

    # ── Compact ────────────────────────────────────────────────────────────
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    size_kb = output.stat().st_size / 1024
    print(f"\nDone: {output} ({size_kb:.0f} KB)")

    # ── Summary ────────────────────────────────────────────────────────────
    conn = sqlite3.connect(output)
    for table in ["manufacturer", "caliber", "bullet", "cartridge", "optic", "reticle", "entity_alias"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")
    conn.close()


if __name__ == "__main__":
    main()
