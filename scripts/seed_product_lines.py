"""Seed bullet_product_line table and backfill bullet.product_line_id.

Reads existing DISTINCT (manufacturer_id, product_line) from the bullet table,
creates BulletProductLine rows, and links bullets to their product line.

Usage:
    python scripts/seed_product_lines.py                 # dry-run
    python scripts/seed_product_lines.py --commit        # write to DB
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from sqlalchemy import func, select  # noqa: E402

from drift.database import get_session_factory  # noqa: E402
from drift.models import Bullet, BulletProductLine, Manufacturer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert product line name to a URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[®™©]", "", s)  # strip trademark symbols
    s = re.sub(r"[^a-z0-9]+", "-", s)  # non-alphanum → hyphens
    return s.strip("-")


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Seed bullet_product_line and backfill bullet.product_line_id")
    parser.add_argument("--commit", action="store_true", help="Write to DB (default is dry-run)")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    logger.info("Running in %s mode", mode)

    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        # Get all distinct (manufacturer_id, product_line) combos from bullets
        pairs = list(
            session.execute(
                select(Bullet.manufacturer_id, Bullet.product_line)
                .where(Bullet.product_line.isnot(None))
                .group_by(Bullet.manufacturer_id, Bullet.product_line)
                .order_by(Bullet.manufacturer_id, Bullet.product_line)
            )
        )
        logger.info("Found %d distinct (manufacturer, product_line) pairs", len(pairs))

        # Index existing BPL rows to avoid dupes
        existing = {(row.manufacturer_id, row.slug) for row in session.scalars(select(BulletProductLine))}

        created = skipped = 0
        bpl_lookup: dict[tuple[str, str], str] = {}  # (manufacturer_id, product_line) → bpl.id

        # Load any existing BPL rows into lookup
        for bpl in session.scalars(select(BulletProductLine)):
            # Match by manufacturer_id + name (case-insensitive)
            bpl_lookup[(bpl.manufacturer_id, bpl.name.lower())] = bpl.id

        for mfr_id, product_line in pairs:
            slug = _slugify(product_line)
            key = (mfr_id, product_line.lower())

            if key in bpl_lookup:
                skipped += 1
                continue

            if (mfr_id, slug) in existing:
                # Slug exists but name differs — lookup by slug
                bpl = session.scalars(
                    select(BulletProductLine).where(
                        BulletProductLine.manufacturer_id == mfr_id,
                        BulletProductLine.slug == slug,
                    )
                ).first()
                if bpl:
                    bpl_lookup[key] = bpl.id
                    skipped += 1
                    continue

            # Get manufacturer name for logging
            mfr_name = session.scalars(select(Manufacturer.name).where(Manufacturer.id == mfr_id)).first()

            bpl = BulletProductLine(
                manufacturer_id=mfr_id,
                name=product_line,
                slug=slug,
            )
            session.add(bpl)
            session.flush()  # get the id
            bpl_lookup[key] = bpl.id
            existing.add((mfr_id, slug))
            created += 1
            logger.info("  CREATE: %s / %s (slug=%s)", mfr_name, product_line, slug)

        print(f"\nProduct lines ({mode}):")
        print(f"  Created: {created}")
        print(f"  Skipped (existing): {skipped}")

        # Backfill bullet.product_line_id
        bullets_updated = 0
        bullets_already = 0
        bullets_no_match = 0

        bullets = list(
            session.scalars(
                select(Bullet).where(
                    Bullet.product_line.isnot(None),
                    Bullet.product_line_id.is_(None),
                )
            )
        )
        logger.info("Found %d bullets needing product_line_id backfill", len(bullets))

        for bullet in bullets:
            key = (bullet.manufacturer_id, bullet.product_line.lower())
            bpl_id = bpl_lookup.get(key)
            if bpl_id:
                bullet.product_line_id = bpl_id
                bullets_updated += 1
            else:
                bullets_no_match += 1
                logger.warning("  NO MATCH: bullet %s product_line=%r", bullet.name, bullet.product_line)

        # Count already-linked bullets
        bullets_already = session.scalar(
            select(func.count()).select_from(Bullet).where(Bullet.product_line_id.isnot(None))
        )

        print(f"\nBullet backfill ({mode}):")
        print(f"  Updated: {bullets_updated}")
        print(f"  Already linked: {bullets_already}")
        print(f"  No match: {bullets_no_match}")

        if args.commit:
            session.commit()
            logger.info("Committed to database")
        else:
            session.rollback()
            logger.info("Dry-run complete — no changes written")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
