"""One-time cleanup: delete bullets whose diameter matches no caliber.

Removes pipeline-sourced, unlocked bullets that can never be associated
with any caliber in the database. Their extraction data is preserved in
data/pipeline/extracted/ for future re-runs if needed.

Usage:
    python scripts/cleanup_orphan_bullets.py            # dry-run
    python scripts/cleanup_orphan_bullets.py --commit   # write to DB
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import delete, select

from drift.database import get_session_factory
from drift.models.bullet import Bullet, BulletBCSource
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete orphan bullets with no matching caliber")
    parser.add_argument("--commit", action="store_true", help="Actually write to DB (default is dry-run)")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        # Get valid diameters from caliber table
        valid_diameters = set(session.scalars(select(Caliber.bullet_diameter_inches).distinct()))
        logger.info("Valid bullet diameters: %d", len(valid_diameters))

        # Find orphan bullets (no matching caliber, not locked)
        orphan_bullets = list(
            session.scalars(
                select(Bullet)
                .where(Bullet.bullet_diameter_inches.notin_(valid_diameters))
                .where(Bullet.is_locked == False)  # noqa: E712
            )
        )

        if not orphan_bullets:
            print("No orphan bullets found.")
            return

        # Exclude bullets referenced by cartridges (FK safety)
        orphan_ids = [b.id for b in orphan_bullets]
        referenced_ids = set(
            session.scalars(select(Cartridge.bullet_id).where(Cartridge.bullet_id.in_(orphan_ids)).distinct())
        )
        if referenced_ids:
            logger.warning("Skipping %d bullets referenced by cartridges", len(referenced_ids))
            orphan_bullets = [b for b in orphan_bullets if b.id not in referenced_ids]
            orphan_ids = [b.id for b in orphan_bullets]

        # Group by diameter for reporting
        by_diameter: dict[float, list[Bullet]] = {}
        for b in orphan_bullets:
            by_diameter.setdefault(b.bullet_diameter_inches, []).append(b)

        print(f"\nOrphan bullets to delete ({mode}): {len(orphan_bullets)}")
        print(f"Across {len(by_diameter)} diameters:\n")
        for d in sorted(by_diameter):
            bullets = by_diameter[d]
            print(f'  {d:.4f}" ({len(bullets)} bullets)')
            for b in bullets[:3]:
                print(f"    - {b.name}")
            if len(bullets) > 3:
                print(f"    ... and {len(bullets) - 3} more")

        if args.commit:
            bc_deleted = session.execute(
                delete(BulletBCSource).where(BulletBCSource.bullet_id.in_(orphan_ids))
            ).rowcount
            bullet_deleted = session.execute(delete(Bullet).where(Bullet.id.in_(orphan_ids))).rowcount
            session.commit()
            print(f"\nDeleted {bullet_deleted} bullets and {bc_deleted} BC sources.")
        else:
            print("\nDry-run — no changes. Use --commit to delete.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
