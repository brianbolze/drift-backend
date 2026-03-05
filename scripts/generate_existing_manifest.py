"""Generate a URL manifest from existing DB entities for pipeline validation.

Queries the database for all bullets, cartridges, and rifle models that have
source_url set, and generates a manifest suitable for the fetch → extract
pipeline. This lets us validate the pipeline against known-good data.

URLs are deduplicated — if multiple entities share the same source URL,
only one manifest entry is created with all entity types noted.

Usage:
    python scripts/generate_existing_manifest.py
    python scripts/generate_existing_manifest.py --output data/pipeline/url_manifest.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Generate manifest from existing DB entities")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/pipeline/url_manifest.json"),
        help="Output manifest path",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Database URL (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    # Set DATABASE_URL if provided
    if args.db:
        os.environ["DATABASE_URL"] = args.db

    from drift.database import get_session_factory
    from drift.models.bullet import Bullet
    from drift.models.cartridge import Cartridge
    from drift.models.rifle_model import RifleModel

    session = get_session_factory()()

    # Collect all entities with source URLs
    url_entries: dict[str, dict] = {}  # url → manifest entry

    try:
        # Bullets
        bullets = session.query(Bullet).filter(Bullet.source_url.isnot(None), Bullet.source_url != "").all()
        logger.info("Found %d bullets with source URLs", len(bullets))
        for b in bullets:
            url = b.source_url.strip()
            if url not in url_entries:
                url_entries[url] = {
                    "url": url,
                    "entity_type": "bullet",
                    "expected_manufacturer": b.manufacturer.name if b.manufacturer else "",
                    "expected_caliber": b.caliber.name if b.caliber else "",
                    "source": "existing_db",
                    "existing_entities": [],
                }
            url_entries[url]["existing_entities"].append(
                {
                    "type": "bullet",
                    "name": b.name,
                    "weight_grains": b.weight_grains,
                    "id": b.id,
                }
            )

        # Cartridges
        carts = session.query(Cartridge).filter(Cartridge.source_url.isnot(None), Cartridge.source_url != "").all()
        logger.info("Found %d cartridges with source URLs", len(carts))
        for c in carts:
            url = c.source_url.strip()
            if url not in url_entries:
                url_entries[url] = {
                    "url": url,
                    "entity_type": "cartridge",
                    "expected_manufacturer": c.manufacturer.name if c.manufacturer else "",
                    "expected_caliber": c.caliber.name if c.caliber else "",
                    "source": "existing_db",
                    "existing_entities": [],
                }
            url_entries[url]["existing_entities"].append(
                {
                    "type": "cartridge",
                    "name": c.name,
                    "bullet_weight_grains": c.bullet_weight_grains,
                    "id": c.id,
                }
            )

        # Rifle models
        rifles = session.query(RifleModel).all()
        logger.info("Found %d rifle models total", len(rifles))
        for r in rifles:
            url = (r.source_url or r.manufacturer_url or "").strip()
            if not url:
                continue
            if url not in url_entries:
                url_entries[url] = {
                    "url": url,
                    "entity_type": "rifle",
                    "expected_manufacturer": r.manufacturer.name if r.manufacturer else "",
                    "source": "existing_db",
                    "existing_entities": [],
                }
            url_entries[url]["existing_entities"].append(
                {
                    "type": "rifle",
                    "model": r.model,
                    "id": r.id,
                }
            )

    finally:
        session.close()

    # Build manifest list
    manifest = list(url_entries.values())

    # Stats
    entity_counts = {"bullet": 0, "cartridge": 0, "rifle": 0}
    for entry in manifest:
        for entity in entry.get("existing_entities", []):
            entity_counts[entity["type"]] = entity_counts.get(entity["type"], 0) + 1

    logger.info("Manifest: %d unique URLs covering %d entities", len(manifest), sum(entity_counts.values()))
    for etype, count in entity_counts.items():
        logger.info("  %s: %d", etype, count)

    # Note shared URLs
    shared = [e for e in manifest if len(e["existing_entities"]) > 1]
    if shared:
        logger.info("%d URLs are shared across multiple entities:", len(shared))
        for entry in shared:
            names = [e.get("name") or e.get("model") for e in entry["existing_entities"]]
            logger.info("  %s → %s", entry["url"], names)

    # Write manifest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest written to {args.output} ({len(manifest)} URLs)")


if __name__ == "__main__":
    main()
