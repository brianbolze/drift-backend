"""Fetch and reduce URLs from the manifest.

Reads url_manifest.json, fetches each URL via httpx (with optional Firecrawl
fallback), reduces the HTML, and caches both raw and reduced results.

Resume-safe: skips already-fetched URLs based on cache files.

Usage:
    python scripts/pipeline_fetch.py
    python scripts/pipeline_fetch.py --no-firecrawl
    python scripts/pipeline_fetch.py --manifest data/pipeline/url_manifest.json
    python scripts/pipeline_fetch.py --rereduce                   # Re-reduce all fetched HTML
    python scripts/pipeline_fetch.py --rereduce --domain barnes   # Re-reduce only matching domains
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

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

# Sentinel used when a manifest entry lacks an explicit priority.
# Chosen large enough to never collide with a real (human-assigned) priority value.
_PRIORITY_MISSING = 10**9


def _collect_rereduce_items(domain_filter: str | None) -> tuple[list[tuple], int]:
    """Scan reduced cache for items eligible for re-reduction. Returns (items, skipped_count)."""
    reduced_jsons = sorted(REDUCED_DIR.glob("*.json"))
    pending = []
    skipped = 0
    for rj in reduced_jsons:
        try:
            meta = json.loads(rj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.warning("Skipping corrupt reduced cache file %s: %s", rj.name, e)
            skipped += 1
            continue
        url = meta.get("url", "")
        if not url:
            continue
        if domain_filter and domain_filter.lower() not in urlparse(url).netloc.lower():
            skipped += 1
            continue
        uhash = meta.get("url_hash", rj.stem)
        fetched_html_path = FETCHED_DIR / f"{uhash}.html"
        if not fetched_html_path.exists():
            skipped += 1
            continue
        pending.append((url, uhash, meta, fetched_html_path))
    return pending, skipped


def _rereduce(domain_filter: str | None, limit: int) -> None:
    """Re-run reduction on already-fetched HTML without re-fetching."""
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST_PATH}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    url_to_entry = {entry["url"]: entry for entry in manifest}

    reducer = HtmlReducer()
    pending, skipped = _collect_rereduce_items(domain_filter)
    if limit > 0:
        pending = pending[:limit]

    improved = 0
    fallbacks = 0
    for i, (url, uhash, old_meta, fetched_html_path) in enumerate(pending):
        html = fetched_html_path.read_text(encoding="utf-8")
        old_size = old_meta.get("reduction_meta", {}).get("reduced_size", 0)

        reduced_html, meta = reducer.reduce(html, url=url)

        # Preserve manifest metadata in reduced JSON
        entry = url_to_entry.get(url, {})
        reduced_data = {
            "url": url,
            "url_hash": uhash,
            "entity_type": entry.get("entity_type") or old_meta.get("entity_type"),
            "expected_manufacturer": entry.get("expected_manufacturer") or old_meta.get("expected_manufacturer"),
            "expected_caliber": entry.get("expected_caliber") or old_meta.get("expected_caliber"),
            "reduction_meta": meta,
        }
        (REDUCED_DIR / f"{uhash}.json").write_text(json.dumps(reduced_data, indent=2), encoding="utf-8")
        (REDUCED_DIR / f"{uhash}.html").write_text(reduced_html, encoding="utf-8")

        if meta["reduced_size"] < old_size:
            improved += 1
        if meta.get("strategy_used", "").endswith("_fallback"):
            fallbacks += 1

        logger.info(
            "[%d/%d] %s → %d → %d chars (%.0f%%) [%s]%s",
            i + 1,
            len(pending),
            urlparse(url).netloc,
            len(html),
            meta["reduced_size"],
            meta["reduction_ratio"] * 100,
            meta.get("strategy_used", "generic"),
            f" (was {old_size})" if old_size else "",
        )

    print()
    summary = (
        f"Re-reduced: {len(pending)} pages, {improved} improved, "
        f"{skipped} skipped (of {len(pending) + skipped} total)"
    )
    if fallbacks:
        summary += f", {fallbacks} fallbacks (check logs)"
    print(summary)


async def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Fetch and reduce URLs from manifest")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="URL manifest JSON path")
    parser.add_argument("--no-firecrawl", action="store_true", help="Disable Firecrawl fallback")
    parser.add_argument(
        "--delay", type=float, default=FIRECRAWL_RATE_LIMIT_SECONDS, help="Delay between requests (seconds)"
    )
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to process (0 = all)")
    parser.add_argument(
        "--priority-max",
        type=int,
        default=0,
        help="Only process entries with priority <= N (0 = no filter). Manifest entries missing a priority field are excluded when --priority-max is set.",
    )
    parser.add_argument("--rereduce", action="store_true", help="Re-run reduction on fetched HTML without re-fetching")
    parser.add_argument("--domain", type=str, default=None, help="Domain filter for --rereduce (substring match)")
    args = parser.parse_args()

    if args.rereduce:
        _rereduce(args.domain, args.limit)
        return

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

    # Separate cached from pending, then apply priority filter + sort + limit.
    pending = []
    for idx, entry in enumerate(manifest):
        uhash = url_hash(entry["url"])
        reduced_cache = REDUCED_DIR / f"{uhash}.json"
        if reduced_cache.exists():
            stats["skipped"] += 1
            continue
        priority = entry.get("priority", _PRIORITY_MISSING)
        if args.priority_max > 0 and priority > args.priority_max:
            continue
        pending.append((priority, idx, entry))

    # Stable sort: priority ascending (1 = highest), then original manifest order.
    pending.sort(key=lambda t: (t[0], t[1]))
    pending = [entry for _, _, entry in pending]

    if args.limit > 0:
        pending = pending[: args.limit]

    stats["total"] = stats["skipped"] + len(pending)

    for i, entry in enumerate(pending):
        url = entry["url"]
        uhash = url_hash(url)
        reduced_cache = REDUCED_DIR / f"{uhash}.json"

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
            reduced_html, meta = reducer.reduce(result.html, url=url)

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
                "  %s → %d → %d chars (%.0f%%), %s [%s]",
                result.fetcher_backend,
                len(result.html),
                meta["reduced_size"],
                meta["reduction_ratio"] * 100,
                "under target" if meta["under_target"] else "OVER TARGET",
                meta.get("strategy_used", "generic"),
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
