"""Merge CoWork research results into the URL manifest.

Takes CoWork's JSON output (which has url, entity_type, expected_manufacturer,
expected_caliber, brief_description, confidence, notes) and adds the required
fields (priority, source_type, discovery_method) before appending to the manifest.

Usage:
    python scripts/merge_cowork_results.py data/pipeline/barnes_bullets.json
    python scripts/merge_cowork_results.py data/pipeline/*.json --dry-run
    python scripts/merge_cowork_results.py data/pipeline/berger_bullets.json --priority 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _ROOT / "data" / "pipeline" / "url_manifest.json"


def _load_manifest(path: Path) -> list[dict]:
    """Load the existing manifest, or return empty list if it doesn't exist."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Failed to parse manifest at {path}: {e}") from e


def _enrich_entry(
    entry: dict,
    priority: int,
    source_type: str,
    discovery_method: str,
) -> dict:
    """Add required fields to a CoWork entry."""
    # CoWork entries already have: url, entity_type, expected_manufacturer,
    # expected_caliber, brief_description, confidence, notes
    #
    # We need to add: priority, source_type, discovery_method

    enriched = entry.copy()
    enriched["priority"] = priority
    enriched["source_type"] = source_type
    enriched["discovery_method"] = discovery_method

    return enriched


def _deduplicate(manifest: list[dict], new_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deduplicate new entries against existing manifest.

    Returns:
        Tuple of (entries_to_add, duplicate_entries)
    """
    existing_urls = {e["url"] for e in manifest}
    to_add = []
    duplicates = []

    for entry in new_entries:
        if entry["url"] in existing_urls:
            duplicates.append(entry)
        else:
            to_add.append(entry)

    return to_add, duplicates


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge CoWork research results into URL manifest")
    parser.add_argument(
        "input_files",
        nargs="+",
        type=Path,
        help="CoWork JSON file(s) to merge",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_MANIFEST_PATH,
        help="Path to URL manifest (default: data/pipeline/url_manifest.json)",
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=1,
        help="Priority to assign to all entries (default: 1)",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default="manufacturer",
        help="Source type (default: manufacturer)",
    )
    parser.add_argument(
        "--discovery-method",
        type=str,
        default="cowork_research",
        help="Discovery method (default: cowork_research)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be added without writing",
    )
    args = parser.parse_args()

    # Load existing manifest
    manifest = _load_manifest(args.manifest)
    print(f"Loaded manifest: {len(manifest)} existing entries")

    # Process each input file
    total_added = 0
    total_duplicates = 0

    for input_file in args.input_files:
        if not input_file.exists():
            print(f"⚠️  Skipping {input_file.name}: file not found")
            continue

        try:
            cowork_data = json.loads(input_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"⚠️  Skipping {input_file.name}: invalid JSON ({e})")
            continue

        if not isinstance(cowork_data, list):
            print(f"⚠️  Skipping {input_file.name}: expected JSON array, got {type(cowork_data).__name__}")
            continue

        # Enrich entries
        enriched = [
            _enrich_entry(
                entry,
                priority=args.priority,
                source_type=args.source_type,
                discovery_method=args.discovery_method,
            )
            for entry in cowork_data
        ]

        # Deduplicate
        to_add, duplicates = _deduplicate(manifest, enriched)

        print(f"\n{input_file.name}:")
        print(f"  {len(cowork_data)} entries in file")
        print(f"  {len(to_add)} new entries")
        print(f"  {len(duplicates)} duplicates (skipped)")

        if to_add:
            # Show sample of what will be added
            print("\n  Sample (first 3):")
            for entry in to_add[:3]:
                print(f"    • {entry['expected_manufacturer']} - {entry['brief_description']}")
            if len(to_add) > 3:
                print(f"    ... and {len(to_add) - 3} more")

        # Add to manifest
        manifest.extend(to_add)
        total_added += len(to_add)
        total_duplicates += len(duplicates)

    print(f"\n{'─' * 60}")
    print("Summary:")
    print(f"  Total new entries: {total_added}")
    print(f"  Total duplicates: {total_duplicates}")
    print(f"  Final manifest size: {len(manifest)}")

    if args.dry_run:
        print("\n✓ Dry run complete (no changes written)")
        return

    # Write manifest
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n✓ Manifest written to {args.manifest}")


if __name__ == "__main__":
    main()
