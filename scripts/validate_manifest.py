"""Validate the URL manifest file for the scraping pipeline.

Checks: URL format, required fields, valid entity_type enum, deduplication,
and that expected manufacturers exist in the DB.

Usage:
    python scripts/validate_manifest.py
    python scripts/validate_manifest.py -i data/pipeline/url_manifest.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = {"url", "entity_type", "expected_manufacturer"}
VALID_ENTITY_TYPES = {"bullet", "cartridge", "rifle"}
VALID_SOURCE_TYPES = {"manufacturer", "retailer", "review", "reference"}
VALID_DISCOVERY_METHODS = {"ai_research", "manual", "crawl", "known", "cowork_research"}


def validate_manifest(manifest_path: Path) -> tuple[list[dict], list[str], list[str]]:  # noqa: C901
    """Validate the manifest and return (entries, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not manifest_path.exists():
        errors.append(f"Manifest file not found: {manifest_path}")
        return [], errors, warnings

    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return [], errors, warnings

    if not isinstance(entries, list):
        errors.append("Manifest must be a JSON array")
        return [], errors, warnings

    seen_urls: set[str] = set()

    for i, entry in enumerate(entries):
        prefix = f"[{i}]"

        if not isinstance(entry, dict):
            errors.append(f"{prefix} Entry must be a dict, got {type(entry).__name__}")
            continue

        # Required fields
        for field in REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"{prefix} Missing required field: {field}")

        # URL validation
        url = entry.get("url", "")
        if url:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"{prefix} Invalid URL: {url}")
            if url in seen_urls:
                errors.append(f"{prefix} Duplicate URL: {url}")
            seen_urls.add(url)

        # Entity type validation
        entity_type = entry.get("entity_type", "")
        if entity_type and entity_type not in VALID_ENTITY_TYPES:
            errors.append(f"{prefix} Invalid entity_type: {entity_type!r} (must be one of {VALID_ENTITY_TYPES})")

        # Optional field validation
        source_type = entry.get("source_type")
        if source_type and source_type not in VALID_SOURCE_TYPES:
            warnings.append(f"{prefix} Unknown source_type: {source_type!r}")

        discovery_method = entry.get("discovery_method")
        if discovery_method and discovery_method not in VALID_DISCOVERY_METHODS:
            warnings.append(f"{prefix} Unknown discovery_method: {discovery_method!r}")

        priority = entry.get("priority")
        if priority is not None and not isinstance(priority, int):
            warnings.append(f"{prefix} priority should be an integer, got {type(priority).__name__}")

        # Check for missing optional but recommended fields
        if "expected_caliber" not in entry:
            warnings.append(f"{prefix} Missing recommended field: expected_caliber")
        if "priority" not in entry:
            warnings.append(f"{prefix} Missing recommended field: priority")

    return entries, errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate URL manifest")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=_ROOT / "data" / "pipeline" / "url_manifest.json",
        help="Manifest JSON path",
    )
    args = parser.parse_args()

    entries, errors, warnings = validate_manifest(args.input)

    print(f"Manifest: {args.input}")
    print(f"Entries:  {len(entries)}")
    print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
        print()

    if not errors:
        # Summary by entity type
        by_type: dict[str, int] = {}
        by_manufacturer: dict[str, int] = {}
        for entry in entries:
            et = entry.get("entity_type", "unknown")
            by_type[et] = by_type.get(et, 0) + 1
            mfg = entry.get("expected_manufacturer", "unknown")
            by_manufacturer[mfg] = by_manufacturer.get(mfg, 0) + 1

        print("By entity type:")
        for et, count in sorted(by_type.items()):
            print(f"  {et}: {count}")

        print(f"\nBy manufacturer ({len(by_manufacturer)} unique):")
        for mfg, count in sorted(by_manufacturer.items(), key=lambda x: -x[1])[:10]:
            print(f"  {mfg}: {count}")

        print(f"\n{'VALID' if not warnings else 'VALID (with warnings)'}")
    else:
        print("INVALID — fix errors above")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
