"""Sitemap-based URL discovery.

For each configured manufacturer, fetch the sitemap, diff against the current
url_manifest plus the last-seen snapshot, and record new/removed URLs.
Does not modify the manifest — the operator promotes discoveries via
scripts/merge_cowork_results.py after review.

Outputs:
  data/pipeline/sitemaps/<slug>.json                     — last-seen URL snapshot
  data/pipeline/sitemaps/discovered/<slug>_<date>.json   — new URLs (cowork format, ready to merge)
  data/pipeline/sitemaps/discovered_urls.jsonl           — append-only log of all discoveries
  data/pipeline/sitemaps/removed_urls.jsonl              — append-only log of removals

Usage:
    python scripts/sitemap_watch.py                     # all configured manufacturers
    python scripts/sitemap_watch.py --slug hornady      # single manufacturer
    python scripts/sitemap_watch.py --dry-run           # fetch + diff, don't write outputs
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from drift.pipeline.config import (
    DATA_DIR,
    DOMAIN_SITEMAP,
    HTTPX_CONNECT_TIMEOUT_SECONDS,
    HTTPX_HEADERS,
    HTTPX_TIMEOUT_SECONDS,
    MANIFEST_PATH,
    REJECTED_CALIBERS_PATH,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAPS_DIR = DATA_DIR / "sitemaps"
DISCOVERED_DIR = SITEMAPS_DIR / "discovered"
DISCOVERED_LOG = SITEMAPS_DIR / "discovered_urls.jsonl"
REMOVED_LOG = SITEMAPS_DIR / "removed_urls.jsonl"

MAX_SITEMAP_DEPTH = 3  # guard against sitemap-index loops


# ── Fetching ─────────────────────────────────────────────────────────────────


def _fetch_sitemap_document(url: str, client: httpx.Client) -> bytes:
    """Fetch a sitemap URL and return the raw XML bytes (decompressing .gz)."""
    resp = client.get(url)
    resp.raise_for_status()
    body = resp.content
    if url.endswith(".gz") or resp.headers.get("content-type", "").startswith("application/x-gzip"):
        body = gzip.decompress(body)
    # Some sitemaps are served as gzip despite a .xml URL. Sniff the magic bytes.
    elif body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body


def _parse_sitemap_urls(xml_bytes: bytes, client: httpx.Client, depth: int = 0) -> set[str]:
    """Parse a sitemap document and return all <loc> URLs.

    Recurses into <sitemapindex> child sitemaps. Depth-limited to avoid loops.
    """
    if depth > MAX_SITEMAP_DEPTH:
        logger.warning("Sitemap recursion depth exceeded — stopping")
        return set()

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("Failed to parse sitemap XML: %s", e)
        return set()

    # Strip namespace from tag for robustness (some sitemaps lack xmlns)
    tag = root.tag.rsplit("}", 1)[-1]

    if tag == "sitemapindex":
        urls: set[str] = set()
        child_locs = _find_locs(root)
        for child_url in child_locs:
            try:
                child_bytes = _fetch_sitemap_document(child_url, client)
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch child sitemap %s: %s", child_url, e)
                continue
            urls |= _parse_sitemap_urls(child_bytes, client, depth + 1)
        return urls

    if tag == "urlset":
        return set(_find_locs(root))

    logger.warning("Unrecognized sitemap root element: %s", tag)
    return set()


def _find_locs(root: ET.Element) -> list[str]:
    """Return all <loc> text values under root, namespace-agnostic."""
    # Try namespaced first, then fall back to tag-only search.
    locs = [el.text.strip() for el in root.findall(".//sm:loc", SITEMAP_NS) if el.text]
    if locs:
        return locs
    return [el.text.strip() for el in root.iter() if el.tag.endswith("}loc") or el.tag == "loc" if el.text]


# ── Classification ───────────────────────────────────────────────────────────


def _match_any(url: str, patterns: list[str]) -> bool:
    return any(re.search(p, url) for p in patterns)


def _classify_entity_type(url: str, rules: list[tuple[str, str, str]]) -> tuple[str, str]:
    """Return (entity_type, confidence) using the first matching rule.

    rules: list of (pattern, entity_type, confidence) tuples.
    """
    for pattern, entity_type, confidence in rules:
        if re.search(pattern, url):
            return entity_type, confidence
    return "unclassified", "low"


def _has_rejected_caliber(url: str, rejected_patterns: list[str]) -> bool:
    """Check if URL slug likely refers to a rejected caliber.

    URL slugs normalize differently from display names ("9mm-luger" vs "9mm Luger"),
    so we strip non-alphanumerics from both before substring-checking.
    """

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    url_norm = _norm(url)
    return any(_norm(p) in url_norm for p in rejected_patterns if _norm(p))


# ── Snapshot I/O ─────────────────────────────────────────────────────────────


def _load_snapshot(slug: str) -> dict:
    path = SITEMAPS_DIR / f"{slug}.json"
    if not path.exists():
        return {"slug": slug, "urls": [], "last_run_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Corrupt snapshot for %s — treating as empty", slug)
        return {"slug": slug, "urls": [], "last_run_at": None}


def _save_snapshot(slug: str, urls: set[str], sitemap_url: str) -> None:
    SITEMAPS_DIR.mkdir(parents=True, exist_ok=True)
    path = SITEMAPS_DIR / f"{slug}.json"
    payload = {
        "slug": slug,
        "sitemap_url": sitemap_url,
        "last_run_at": datetime.now(tz=timezone.utc).isoformat(),
        "url_count": len(urls),
        "urls": sorted(urls),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")


# ── Per-manufacturer run ─────────────────────────────────────────────────────


def _load_rejected_calibers() -> list[str]:
    if not REJECTED_CALIBERS_PATH.exists():
        return []
    try:
        data = json.loads(REJECTED_CALIBERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data.get("calibers", [])


def _load_manifest_urls(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {e["url"] for e in manifest if "url" in e}


def _build_entry(url: str, slug: str, config: dict, rules: list[tuple[str, str, str]]) -> dict:
    """Build a cowork-format entry for a newly discovered URL."""
    entity_type, confidence = _classify_entity_type(url, rules)
    return {
        "url": url,
        "entity_type": entity_type,
        "expected_manufacturer": config.get("expected_manufacturer", slug),
        "expected_caliber": None,
        "brief_description": None,
        "confidence": confidence,
        "notes": f"Discovered via sitemap ({slug}) on {datetime.now(tz=timezone.utc).date().isoformat()}",
    }


def _filter_urls(urls: set[str], config: dict, rejected_calibers: list[str]) -> set[str]:
    """Apply include/exclude regex plus rejected-caliber filter to a URL set."""
    include = config.get("include_patterns", [])
    exclude = config.get("exclude_patterns", [])

    def keep(u: str) -> bool:
        if include and not _match_any(u, include):
            return False
        if exclude and _match_any(u, exclude):
            return False
        if _has_rejected_caliber(u, rejected_calibers):
            return False
        return True

    return {u for u in urls if keep(u)}


def _write_outputs(
    slug: str,
    sitemap_url: str,
    filtered: set[str],
    new_entries: list[dict],
    removed_records: list[dict],
    discovered_records: list[dict],
) -> str | None:
    """Persist snapshot + discovery artifacts. Returns the per-run discovery filename if any."""
    discovered_filename: str | None = None
    if new_entries:
        DISCOVERED_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        out_path = DISCOVERED_DIR / f"{slug}_{date_str}.json"
        out_path.write_text(json.dumps(new_entries, indent=2, ensure_ascii=False), encoding="utf-8")
        discovered_filename = str(out_path.relative_to(SITEMAPS_DIR.parent.parent))

    _append_jsonl(DISCOVERED_LOG, discovered_records)
    _append_jsonl(REMOVED_LOG, removed_records)
    _save_snapshot(slug, filtered, sitemap_url)
    return discovered_filename


def watch_manufacturer(
    slug: str,
    config: dict,
    manifest_urls: set[str],
    rejected_calibers: list[str],
    client: httpx.Client,
    dry_run: bool,
) -> dict:
    """Run one sitemap pass for a manufacturer. Returns a stats dict."""
    sitemap_url = config["sitemap_url"]
    rules = config.get("entity_type_rules", [])

    logger.info("[%s] fetching %s", slug, sitemap_url)
    try:
        xml_bytes = _fetch_sitemap_document(sitemap_url, client)
    except httpx.HTTPError as e:
        logger.error("[%s] sitemap fetch failed: %s", slug, e)
        return {"slug": slug, "status": "fetch_failed", "error": str(e)}

    all_urls = _parse_sitemap_urls(xml_bytes, client)
    filtered = _filter_urls(all_urls, config, rejected_calibers)
    logger.info("[%s] sitemap=%d filtered=%d", slug, len(all_urls), len(filtered))

    snapshot = _load_snapshot(slug)
    previous = set(snapshot.get("urls", []))
    new_urls = filtered - previous - manifest_urls
    removed_urls = previous - filtered

    new_entries = [_build_entry(u, slug, config, rules) for u in sorted(new_urls)]
    unclassified_count = sum(1 for e in new_entries if e["entity_type"] == "unclassified")

    stats = {
        "slug": slug,
        "status": "ok",
        "sitemap_urls": len(all_urls),
        "filtered": len(filtered),
        "new": len(new_urls),
        "removed": len(removed_urls),
        "unclassified": unclassified_count,
    }

    logger.info(
        "[%s] new=%d (unclassified=%d) removed=%d",
        slug,
        len(new_urls),
        unclassified_count,
        len(removed_urls),
    )

    if dry_run:
        return stats

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    discovered_records = [{"discovered_at": now_iso, "manufacturer_slug": slug, **entry} for entry in new_entries]
    removed_records = [
        {"removed_at": now_iso, "manufacturer_slug": slug, "url": u, "was_in_manifest": u in manifest_urls}
        for u in sorted(removed_urls)
    ]
    discovered_filename = _write_outputs(slug, sitemap_url, filtered, new_entries, removed_records, discovered_records)
    if discovered_filename:
        stats["discovered_file"] = discovered_filename
    return stats


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover new URLs via manufacturer sitemaps")
    parser.add_argument(
        "--slug",
        type=str,
        default=None,
        help="Run only the given manufacturer slug (default: all configured)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + diff + report; do not write snapshot or discovery files",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="URL manifest path for de-duplication (default: data/pipeline/url_manifest.json)",
    )
    args = parser.parse_args()

    if not DOMAIN_SITEMAP:
        raise SystemExit("No manufacturers configured in DOMAIN_SITEMAP (src/drift/pipeline/config.py)")

    # Flatten config by slug
    targets: dict[str, dict] = {}
    for domain, config in DOMAIN_SITEMAP.items():
        slug = config.get("slug", domain.replace(".", "_"))
        targets[slug] = {"domain": domain, **config}

    if args.slug:
        if args.slug not in targets:
            raise SystemExit(f"Unknown slug {args.slug!r}. Configured: {sorted(targets)}")
        targets = {args.slug: targets[args.slug]}

    manifest_urls = _load_manifest_urls(args.manifest)
    rejected_calibers = _load_rejected_calibers()
    logger.info(
        "Manifest: %d URLs | Rejected calibers: %d | Targets: %d",
        len(manifest_urls),
        len(rejected_calibers),
        len(targets),
    )

    all_stats: list[dict] = []
    timeout = httpx.Timeout(HTTPX_TIMEOUT_SECONDS, connect=HTTPX_CONNECT_TIMEOUT_SECONDS)
    with httpx.Client(headers=HTTPX_HEADERS, timeout=timeout, follow_redirects=True) as client:
        for slug, config in targets.items():
            stats = watch_manufacturer(slug, config, manifest_urls, rejected_calibers, client, args.dry_run)
            all_stats.append(stats)

    # Summary
    print()
    print("─" * 60)
    print("Summary:")
    for s in all_stats:
        if s["status"] != "ok":
            print(f"  {s['slug']}: {s['status']} — {s.get('error', '')}")
            continue
        print(
            f"  {s['slug']}: sitemap={s['sitemap_urls']} filtered={s['filtered']} "
            f"new={s['new']} removed={s['removed']} unclassified={s['unclassified']}"
        )
    if args.dry_run:
        print()
        print("✓ Dry run complete (no outputs written)")
    else:
        total_new = sum(s.get("new", 0) for s in all_stats)
        total_removed = sum(s.get("removed", 0) for s in all_stats)
        print()
        print(f"✓ Discovered {total_new} new URLs | {total_removed} removed")
        if total_new:
            print(f"  Per-manufacturer JSON: {DISCOVERED_DIR}")
            print(f"  Append-only log:       {DISCOVERED_LOG}")
            print("  Next: python scripts/merge_cowork_results.py <file> --discovery-method sitemap")


if __name__ == "__main__":
    main()
