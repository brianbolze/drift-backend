"""Fetch and reduce URLs from the manifest.

Reads url_manifest.json, fetches each URL via httpx (with optional Firecrawl
fallback), reduces the HTML, and caches both raw and reduced results.

Resume-safe: skips already-fetched URLs based on cache files.

Usage:
    python scripts/pipeline_fetch.py
    python scripts/pipeline_fetch.py --no-firecrawl
    python scripts/pipeline_fetch.py --manifest data/pipeline/url_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import httpx

from drift.pipeline.config import (
    EXTRACTED_DIR,
    FETCHED_DIR,
    FIRECRAWL_RATE_LIMIT_SECONDS,
    MANIFEST_PATH,
    REDUCED_DIR,
)
from drift.pipeline.fetching.registry import FetcherRegistry
from drift.pipeline.reduction.reducer import HtmlReducer
from drift.pipeline.utils import url_hash

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Fetch and reduce URLs from manifest")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="URL manifest JSON path")
    parser.add_argument("--no-firecrawl", action="store_true", help="Disable Firecrawl fallback")
    parser.add_argument(
        "--delay", type=float, default=FIRECRAWL_RATE_LIMIT_SECONDS, help="Delay between requests (seconds)"
    )
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to process (0 = all)")
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(
            f"Manifest not found: {args.manifest}\nRun generate_shopping_list.py first, then create the manifest."
        )

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    logger.info("Loaded manifest: %d URLs", len(manifest))

    # Ensure cache directories exist
    for d in [FETCHED_DIR, REDUCED_DIR, EXTRACTED_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    registry = FetcherRegistry(enable_firecrawl=not args.no_firecrawl)
    reducer = HtmlReducer()

    stats = {"fetched": 0, "skipped": 0, "failed": 0, "total": 0}

    # Separate cached from pending, then apply limit to pending items only
    pending = []
    for entry in manifest:
        uhash = url_hash(entry["url"])
        reduced_cache = REDUCED_DIR / f"{uhash}.json"
        if reduced_cache.exists():
            stats["skipped"] += 1
        else:
            pending.append(entry)

    if args.limit > 0:
        pending = pending[: args.limit]

    stats["total"] = stats["skipped"] + len(pending)

    for i, entry in enumerate(pending):
        url = entry["url"]
        uhash = url_hash(url)

        logger.info("[%d/%d] FETCH: %s", i + 1, len(pending), url)

        try:
            result = await registry.fetch(url)

            if result.status_code >= 400:
                logger.warning("  HTTP %d — skipping", result.status_code)
                stats["failed"] += 1
                continue

            # Save raw fetch result
            fetch_data = {
                "url": result.url,
                "status_code": result.status_code,
                "fetcher_backend": result.fetcher_backend,
                "fetched_at": result.fetched_at.isoformat(),
                "content_hash": result.content_hash,
                "html_size": len(result.html),
            }
            (FETCHED_DIR / f"{uhash}.json").write_text(json.dumps(fetch_data, indent=2), encoding="utf-8")
            (FETCHED_DIR / f"{uhash}.html").write_text(result.html, encoding="utf-8")

            # Reduce
            reduced_html, meta = reducer.reduce(result.html)

            # Save reduced result
            reduced_data = {
                "url": url,
                "url_hash": uhash,
                "entity_type": entry.get("entity_type"),
                "expected_manufacturer": entry.get("expected_manufacturer"),
                "expected_caliber": entry.get("expected_caliber"),
                "reduction_meta": meta,
            }
            reduced_cache.write_text(json.dumps(reduced_data, indent=2), encoding="utf-8")
            (REDUCED_DIR / f"{uhash}.html").write_text(reduced_html, encoding="utf-8")

            logger.info(
                "  %s → %d → %d chars (%.0f%%), %s",
                result.fetcher_backend,
                len(result.html),
                meta["reduced_size"],
                meta["reduction_ratio"] * 100,
                "under target" if meta["under_target"] else "OVER TARGET",
            )

            stats["fetched"] += 1

        except (httpx.HTTPError, OSError) as e:
            logger.exception("  FAILED: %s — %s", url, e)
            stats["failed"] += 1
        except Exception:
            logger.exception("  UNEXPECTED FAILURE: %s", url)
            stats["failed"] += 1

        # Rate limiting (non-blocking in async context)
        if i < len(pending) - 1:
            await asyncio.sleep(args.delay)

    print()
    print(
        f"Done: {stats['fetched']} fetched, {stats['skipped']} skipped, {stats['failed']} failed "
        f"(of {stats['total']} total)"
    )


if __name__ == "__main__":
    asyncio.run(main())
