"""Dump the current drift.db data to data/seed.sql.

Usage:
    python scripts/dump_seed.py

Reads from data/drift.db, writes INSERT OR IGNORE statements in FK-safe
order to data/seed.sql. Run this after making verified changes to the
database to update the canonical seed file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "drift.db"
SEED_PATH = _ROOT / "data" / "seed.sql"

# FK-safe insertion order (parents before children).
TABLE_ORDER = [
    "platform",
    "manufacturer",
    "chamber",
    "caliber",
    "chamber_accepts_caliber",
    "caliber_platform",
    "entity_alias",
    "reticle",
    "bullet",
    "bullet_bc_source",
    "optic",
    "cartridge",
    "rifle_model",
]


def quote_val(v: object) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    lines: list[str] = []
    lines.append("-- Drift seed data")
    lines.append("-- Auto-generated from verified drift.db")
    lines.append("-- FK-safe insertion order; idempotent (INSERT OR IGNORE)")
    lines.append("")
    lines.append("PRAGMA foreign_keys = OFF;")
    lines.append("BEGIN TRANSACTION;")
    lines.append("")

    total_rows = 0

    for table in TABLE_ORDER:
        cursor = conn.execute(f"SELECT * FROM {table}")
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if not rows:
            lines.append(f"-- {table}: (empty)")
            lines.append("")
            continue

        lines.append(f"-- {table}: {len(rows)} rows")
        total_rows += len(rows)

        if table == "caliber":
            # Two-pass: insert with parent_caliber_id = NULL, then UPDATE.
            parent_idx = cols.index("parent_caliber_id")
            id_idx = cols.index("id")
            parent_updates: list[tuple[str, str]] = []

            for row in rows:
                vals = []
                for i, col in enumerate(cols):
                    if col == "parent_caliber_id":
                        vals.append("NULL")
                        if row[i] is not None:
                            parent_updates.append((row[id_idx], row[i]))
                    else:
                        vals.append(quote_val(row[i]))
                col_list = ", ".join(cols)
                val_list = ", ".join(vals)
                lines.append(f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({val_list});")

            if parent_updates:
                lines.append(f"-- caliber parent references: {len(parent_updates)} updates")
                for cal_id, parent_id in parent_updates:
                    lines.append(f"UPDATE caliber SET parent_caliber_id = '{parent_id}' WHERE id = '{cal_id}';")
        else:
            for row in rows:
                vals = [quote_val(row[i]) for i in range(len(cols))]
                col_list = ", ".join(cols)
                val_list = ", ".join(vals)
                lines.append(f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({val_list});")

        lines.append("")

    lines.append("COMMIT;")
    lines.append("PRAGMA foreign_keys = ON;")
    lines.append("")

    output = "\n".join(lines)
    SEED_PATH.write_text(output)

    conn.close()
    print(f"Wrote {SEED_PATH} ({total_rows} rows, {len(lines)} lines, {len(output):,} bytes)")


if __name__ == "__main__":
    main()
