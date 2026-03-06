"""Apply YAML curation patches to the database.

Usage:
    python scripts/curate.py              # dry-run (preview changes)
    python scripts/curate.py --commit     # write to DB
    python scripts/curate.py --patch 001_sierra_matchking_30cal  # single patch
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from drift.curation import ApplyStats, apply_patch, discover_patches, load_and_validate
from drift.database import get_session_factory

PATCHES_DIR = Path(__file__).resolve().parent.parent / "data" / "patches"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _resolve_patch_paths(args: argparse.Namespace) -> list[Path]:
    """Discover and return patch paths based on CLI args."""
    if args.patch:
        patch_path = PATCHES_DIR / f"{args.patch}.yaml"
        if not patch_path.exists():
            logger.error("Patch not found: %s", patch_path)
            sys.exit(1)
        return [patch_path]
    return discover_patches(PATCHES_DIR)


def _validate_patches(patch_paths: list[Path]) -> list:
    """Load and validate all patches. Exits on first validation error."""
    patches = []
    for path in patch_paths:
        try:
            patches.append(load_and_validate(path))
        except Exception as e:
            logger.error("Validation failed for %s: %s", path.name, e)
            sys.exit(1)
    return patches


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply YAML curation patches")
    parser.add_argument("--commit", action="store_true", help="Write changes to DB (default: dry-run)")
    parser.add_argument("--patch", type=str, help="Apply a single patch by ID (e.g. 001_sierra_matchking_30cal)")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    logger.info("Running in %s mode", mode)

    patch_paths = _resolve_patch_paths(args)
    if not patch_paths:
        logger.info("No patches found in %s", PATCHES_DIR)
        return

    logger.info("Found %d patch(es)", len(patch_paths))
    patches = _validate_patches(patch_paths)

    SessionFactory = get_session_factory()
    session = SessionFactory()
    totals = ApplyStats()

    try:
        for patch in patches:
            logger.info("Applying patch %s: %s", patch.patch.id, patch.patch.description)
            stats = apply_patch(session, patch)
            totals.created += stats.created
            totals.updated += stats.updated
            totals.skipped += stats.skipped
            totals.errors += stats.errors
            for detail in stats.details:
                logger.info(detail)

        if args.commit:
            session.commit()
            logger.info("Changes committed to database")
        else:
            session.rollback()
            logger.info("Dry-run complete — no changes written")
    except Exception as e:
        session.rollback()
        logger.error("Fatal error: %s", e)
        sys.exit(1)
    finally:
        session.close()

    logger.info(
        "Summary (%s): %d created, %d updated, %d skipped, %d errors",
        mode,
        totals.created,
        totals.updated,
        totals.skipped,
        totals.errors,
    )


if __name__ == "__main__":
    main()
