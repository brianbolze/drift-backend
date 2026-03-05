"""Extract structured product data from reduced HTML via Claude.

Reads reduced HTML from data/pipeline/reduced/, sends each to the
ExtractionEngine (Claude Haiku), and saves results to data/pipeline/extracted/.

Resume-safe: skips already-extracted URLs based on cache files.

Usage:
    python scripts/pipeline_extract.py
    python scripts/pipeline_extract.py --model claude-sonnet-4-20250514
    python scripts/pipeline_extract.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from drift.pipeline.config import (
    DEFAULT_MODEL,
    EXTRACTED_DIR,
    MANIFEST_PATH,
    REDUCED_DIR,
    REVIEW_DIR,
)
from drift.pipeline.extraction.engine import ExtractionEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _url_hash_from_manifest(manifest: list[dict]) -> dict[str, dict]:
    """Build a lookup from url_hash → manifest entry.

    The url_hash is computed the same way as in pipeline_fetch.py,
    but we read it from the reduced JSON metadata instead.
    """
    import hashlib

    lookup: dict[str, dict] = {}
    for entry in manifest:
        url = entry["url"]
        uhash = hashlib.sha256(url.encode()).hexdigest()[:16]
        lookup[uhash] = entry
    return lookup


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Extract product data from reduced HTML")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="URL manifest JSON path")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Claude model to use")
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to process (0 = all)")
    parser.add_argument("--reextract", action="store_true", help="Re-extract even if cached result exists")
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}\nRun pipeline_fetch.py first.")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    hash_lookup = _url_hash_from_manifest(manifest)

    # Find all reduced files ready for extraction
    reduced_files = sorted(REDUCED_DIR.glob("*.json"))
    if not reduced_files:
        raise SystemExit(f"No reduced files found in {REDUCED_DIR}\nRun pipeline_fetch.py first.")

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    engine = ExtractionEngine(model=args.model)

    stats = {"extracted": 0, "skipped": 0, "failed": 0, "flagged": 0, "total": 0}
    flagged_items: list[dict] = []

    entries = reduced_files[: args.limit] if args.limit > 0 else reduced_files

    for i, reduced_json_path in enumerate(entries):
        uhash = reduced_json_path.stem
        stats["total"] += 1

        # Check cache
        extracted_cache = EXTRACTED_DIR / f"{uhash}.json"
        if extracted_cache.exists() and not args.reextract:
            logger.info("[%d/%d] SKIP (cached): %s", i + 1, len(entries), uhash)
            stats["skipped"] += 1
            continue

        # Load reduced metadata
        reduced_meta = json.loads(reduced_json_path.read_text(encoding="utf-8"))
        url = reduced_meta.get("url", uhash)
        entity_type = reduced_meta.get("entity_type")

        if not entity_type:
            # Try manifest lookup
            manifest_entry = hash_lookup.get(uhash, {})
            entity_type = manifest_entry.get("entity_type")

        if not entity_type:
            logger.warning("[%d/%d] SKIP (no entity_type): %s", i + 1, len(entries), url)
            stats["failed"] += 1
            continue

        # Load reduced HTML
        reduced_html_path = REDUCED_DIR / f"{uhash}.html"
        if not reduced_html_path.exists():
            logger.warning("[%d/%d] SKIP (no reduced HTML): %s", i + 1, len(entries), url)
            stats["failed"] += 1
            continue

        reduced_html = reduced_html_path.read_text(encoding="utf-8")
        logger.info("[%d/%d] EXTRACT (%s): %s", i + 1, len(entries), entity_type, url)

        try:
            result = engine.extract(reduced_html, entity_type)

            # Build extraction output
            extraction_data = {
                "url": url,
                "url_hash": uhash,
                "entity_type": entity_type,
                "model": result.model,
                "usage": result.usage,
                "entity_count": len(result.entities),
                "entities": result.raw_entities,
                "bc_sources": [bc.model_dump() for bc in result.bc_sources],
                "warnings": result.warnings,
            }

            extracted_cache.write_text(json.dumps(extraction_data, indent=2), encoding="utf-8")

            logger.info(
                "  %d entities, %d BC sources, %d warnings, %d input / %d output tokens",
                len(result.entities),
                len(result.bc_sources),
                len(result.warnings),
                result.usage["input_tokens"],
                result.usage["output_tokens"],
            )

            # Flag items with warnings or low confidence
            if result.warnings:
                flag_entry = {
                    "url": url,
                    "url_hash": uhash,
                    "entity_type": entity_type,
                    "reason": "validation_warnings",
                    "warnings": result.warnings,
                }
                flagged_items.append(flag_entry)
                stats["flagged"] += 1
                logger.warning("  FLAGGED: %s", result.warnings)

            stats["extracted"] += 1

        except Exception:
            logger.exception("  FAILED: %s", url)
            stats["failed"] += 1

    # Write flagged items
    flagged_path = REVIEW_DIR / "flagged.json"
    if flagged_items:
        # Merge with existing flagged items if any
        existing_flagged: list[dict] = []
        if flagged_path.exists():
            try:
                existing_flagged = json.loads(flagged_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, TypeError):
                pass

        # Deduplicate by url_hash
        existing_hashes = {f["url_hash"] for f in existing_flagged}
        for item in flagged_items:
            if item["url_hash"] not in existing_hashes:
                existing_flagged.append(item)

        flagged_path.write_text(json.dumps(existing_flagged, indent=2), encoding="utf-8")

    print()
    print(
        f"Done: {stats['extracted']} extracted, {stats['skipped']} skipped, "
        f"{stats['failed']} failed, {stats['flagged']} flagged "
        f"(of {stats['total']} total)"
    )
    if flagged_items:
        print(f"Flagged items written to: {flagged_path}")


if __name__ == "__main__":
    main()
