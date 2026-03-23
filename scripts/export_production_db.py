"""Export a production-ready SQLite database for the iOS app.

Copies drift.db → data/production/drift.db with the following transformations:
  - Flattens bullet_product_line aliases into bullet.alt_names JSON
  - Drops pipeline-only tables: alembic_version, bullet_bc_source, bullet_product_line
  - Drops pipeline-only columns: data_source, is_locked, extraction_confidence,
    last_verified_at, created_at, updated_at, bc_source_notes,
    bullet_match_confidence, bullet_match_method, product_line_id
  - Removes orphaned entity_alias rows (bullet_product_line references)
  - Computes display_name for bullets and cartridges
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

from drift.display_name import compute_bullet_display_name, compute_cartridge_display_name

SOURCE_DB = Path("data/drift.db")

# Tables to drop entirely
DROP_TABLES = [
    "alembic_version",
    "bullet_bc_source",
    "bullet_product_line",
]

# Columns to drop per table (pipeline/internal metadata)
DROP_COLUMNS: dict[str, list[str]] = {
    "bullet": [
        "data_source",
        "is_locked",
        "extraction_confidence",
        "last_verified_at",
        "bc_source_notes",
        "product_line_id",
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


def _populate_display_names(conn: sqlite3.Connection) -> None:
    """Compute and populate display_name for all bullets and cartridges."""
    # Ensure display_name column exists (idempotent)
    for table in ("bullet", "cartridge"):
        cols = get_table_columns(conn, table)
        if "display_name" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN display_name TEXT")

    # -- Bullets --
    rows = conn.execute("""
        SELECT b.id, b.name, b.product_line, m.name
        FROM bullet b
        JOIN manufacturer m ON b.manufacturer_id = m.id
    """).fetchall()

    bullet_count = 0
    bullet_warnings = []
    for bullet_id, name, product_line, mfr_name in rows:
        display_name = compute_bullet_display_name(name, product_line, mfr_name)
        if display_name:
            conn.execute("UPDATE bullet SET display_name = ? WHERE id = ?", (display_name, bullet_id))
            bullet_count += 1
            # Warn on suspicious results
            if len(display_name) < 2:
                bullet_warnings.append(f"  WARN: too short: {name!r} → {display_name!r}")
            elif display_name == name:
                bullet_warnings.append(f"  WARN: unchanged: {name!r}")
        else:
            bullet_warnings.append(f"  WARN: empty result: {name!r} (product_line={product_line!r})")

    print(f"  Computed display_name for {bullet_count}/{len(rows)} bullets")
    for w in bullet_warnings:
        print(w)

    # -- Cartridges --
    rows = conn.execute("""
        SELECT c.id, c.name, c.product_line, b.product_line, m.name
        FROM cartridge c
        JOIN manufacturer m ON c.manufacturer_id = m.id
        LEFT JOIN bullet b ON c.bullet_id = b.id
    """).fetchall()

    cart_count = 0
    cart_warnings = []
    for cart_id, name, cart_pl, bullet_pl, mfr_name in rows:
        display_name = compute_cartridge_display_name(name, cart_pl, bullet_pl, mfr_name)
        if display_name:
            conn.execute("UPDATE cartridge SET display_name = ? WHERE id = ?", (display_name, cart_id))
            cart_count += 1
            if len(display_name) < 2:
                cart_warnings.append(f"  WARN: too short: {name!r} → {display_name!r}")
            elif display_name == name:
                cart_warnings.append(f"  WARN: unchanged: {name!r}")
        else:
            cart_warnings.append(f"  WARN: empty result: {name!r} (product_line={cart_pl!r})")

    print(f"  Computed display_name for {cart_count}/{len(rows)} cartridges")
    for w in cart_warnings:
        print(w)


def _flatten_product_line_aliases(conn: sqlite3.Connection) -> None:  # noqa: C901
    """Merge bullet_product_line aliases into each bullet's alt_names JSON.

    For each bullet with a product_line_id, finds all entity_alias rows for that
    product line and appends them to the bullet's alt_names array (deduped).
    Must run BEFORE dropping bullet_product_line table and product_line_id column.
    """
    import json as _json

    # Build product_line_id → list of aliases
    alias_rows = conn.execute("""
        SELECT ea.entity_id, ea.alias
        FROM entity_alias ea
        WHERE ea.entity_type = 'bullet_product_line'
    """).fetchall()

    pl_aliases: dict[str, list[str]] = {}
    for entity_id, alias in alias_rows:
        pl_aliases.setdefault(entity_id, []).append(alias)

    if not pl_aliases:
        print("  No bullet_product_line aliases to flatten")
        return

    # Get all bullets with a product_line_id
    bullet_rows = conn.execute("""
        SELECT id, alt_names, product_line_id
        FROM bullet
        WHERE product_line_id IS NOT NULL
    """).fetchall()

    updated = 0
    for bullet_id, existing_alt_names_json, pl_id in bullet_rows:
        aliases = pl_aliases.get(pl_id, [])
        if not aliases:
            continue

        # Parse existing alt_names
        existing = []
        if existing_alt_names_json:
            try:
                parsed = _json.loads(existing_alt_names_json)
                if isinstance(parsed, list):
                    existing = parsed
                else:
                    print(f"  WARN: bullet {bullet_id} alt_names is {type(parsed).__name__}, not list — resetting")
            except (ValueError, TypeError) as e:
                print(f"  WARN: bullet {bullet_id} alt_names malformed: {e} — resetting")

        # Merge, deduped (case-insensitive)
        existing_lower = {s.lower() for s in existing if isinstance(s, str)}
        merged = list(existing)
        for alias in aliases:
            if alias.lower() not in existing_lower:
                merged.append(alias)
                existing_lower.add(alias.lower())

        if len(merged) > len(existing):
            conn.execute(
                "UPDATE bullet SET alt_names = ? WHERE id = ?",
                (_json.dumps(merged), bullet_id),
            )
            updated += 1

    # Clean up entity_alias rows that reference bullet_product_line (table will be dropped)
    cursor = conn.execute("DELETE FROM entity_alias WHERE entity_type = 'bullet_product_line'")
    print(f"  Flattened product line aliases into {updated} bullets' alt_names ({cursor.rowcount} alias rows removed)")


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

    # ── Flatten product line aliases into bullet alt_names ─────────────────
    # Must run BEFORE dropping bullet_product_line table and product_line_id column
    _flatten_product_line_aliases(conn)

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

    # BC-less cartridges (no usable BC at cartridge or bullet level — solver can't run)
    cursor = conn.execute("""
        DELETE FROM cartridge WHERE id IN (
            SELECT c.id FROM cartridge c
            JOIN bullet b ON c.bullet_id = b.id
            WHERE (c.bc_g1 IS NULL OR c.bc_g1 = 0)
              AND (c.bc_g7 IS NULL OR c.bc_g7 = 0)
              AND b.bc_g1_published IS NULL
              AND b.bc_g1_estimated IS NULL
              AND b.bc_g7_published IS NULL
              AND b.bc_g7_estimated IS NULL
        )
    """)
    print(f"  Removed {cursor.rowcount} BC-less cartridges")

    # Mislinked cartridges (linked to wrong bullet — cart-level BC is valid but
    # bullet data is wrong; filter until correct bullets exist in DB)
    cursor = conn.execute("""
        DELETE FROM cartridge WHERE id IN (
            SELECT c.id FROM cartridge c
            JOIN manufacturer m ON c.manufacturer_id = m.id
            WHERE m.name = 'Federal' AND c.name LIKE '%Power-Shok Copper%'
        )
    """)
    print(f"  Removed {cursor.rowcount} mislinked cartridges (Federal Power-Shok Copper)")

    # ── Compute display_name ────────────────────────────────────────────────
    _populate_display_names(conn)

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
