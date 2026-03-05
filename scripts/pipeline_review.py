"""Review CLI for flagged extraction items.

Displays flagged items from the pipeline for manual review, allowing
the operator to accept, reject, or skip each item.

Usage:
    python scripts/pipeline_review.py                 # interactive review
    python scripts/pipeline_review.py --list           # list all flagged items
    python scripts/pipeline_review.py --stats          # show summary stats
"""

from __future__ import annotations

import argparse
import json
import logging

from drift.pipeline.config import EXTRACTED_DIR, REVIEW_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_flagged() -> list[dict]:
    """Load flagged items from the review directory."""
    flagged_path = REVIEW_DIR / "flagged.json"
    if not flagged_path.exists():
        return []
    try:
        return json.loads(flagged_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return []


def _load_store_report() -> dict | None:
    """Load the store report if it exists."""
    from drift.pipeline.config import STORE_REPORT_PATH

    if not STORE_REPORT_PATH.exists():
        return None
    try:
        return json.loads(STORE_REPORT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return None


def _load_extraction(url_hash: str) -> dict | None:
    """Load an extraction result by URL hash."""
    path = EXTRACTED_DIR / f"{url_hash}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return None


def _print_entity(entity: dict, indent: int = 4) -> None:
    """Pretty-print an extracted entity's key fields."""
    prefix = " " * indent
    for key, val in entity.items():
        if isinstance(val, dict) and "value" in val:
            conf = val.get("confidence", 0)
            marker = "✓" if conf >= 0.7 else "?" if conf >= 0.4 else "✗"
            print(f"{prefix}{marker} {key}: {val['value']} (conf={conf:.2f})")
        elif isinstance(val, list):
            print(f"{prefix}  {key}: {val}")
        else:
            print(f"{prefix}  {key}: {val}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all flagged items."""
    flagged = _load_flagged()
    if not flagged:
        print("No flagged items found.")
        return

    print(f"\n{'='*70}")
    print(f"Flagged Items: {len(flagged)}")
    print(f"{'='*70}\n")

    for i, item in enumerate(flagged):
        status = item.get("status", "pending")
        marker = {"accepted": "✓", "rejected": "✗", "pending": "○"}.get(status, "?")
        print(f"  {marker} [{i+1}] {item.get('entity_type', '?'):10s} | {item.get('url', '?')}")
        print(f"       Reason: {item.get('reason', '?')}")
        if item.get("warnings"):
            for w in item["warnings"]:
                print(f"       ⚠ {w}")
        print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Show summary statistics."""
    flagged = _load_flagged()
    report = _load_store_report()

    print(f"\n{'='*70}")
    print("Pipeline Status")
    print(f"{'='*70}\n")

    # Extraction stats
    extracted_files = list(EXTRACTED_DIR.glob("*.json"))
    print(f"Extracted files: {len(extracted_files)}")

    # Flagged stats
    print(f"Flagged items:   {len(flagged)}")
    if flagged:
        by_reason: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in flagged:
            reason = item.get("reason", "unknown")
            status = item.get("status", "pending")
            by_reason[reason] = by_reason.get(reason, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        print("  By reason:")
        for reason, count in sorted(by_reason.items()):
            print(f"    {reason}: {count}")
        print("  By status:")
        for status, count in sorted(by_status.items()):
            print(f"    {status}: {count}")

    # Store report
    if report:
        print(f"\nStore report ({report.get('mode', '?')}):")
        for etype, counts in report.get("stats", {}).items():
            print(
                f"  {etype}: {counts.get('created', 0)} created, "
                f"{counts.get('matched', 0)} matched, "
                f"{counts.get('flagged', 0)} flagged"
            )
    print()


def cmd_review(args: argparse.Namespace) -> None:  # noqa: C901
    """Interactive review of flagged items."""
    flagged = _load_flagged()
    if not flagged:
        print("No flagged items to review.")
        return

    pending = [item for item in flagged if item.get("status", "pending") == "pending"]
    if not pending:
        print("All flagged items have been reviewed.")
        return

    print(f"\n{len(pending)} items to review (of {len(flagged)} total flagged)\n")

    for i, item in enumerate(pending):
        print(f"\n{'─'*70}")
        print(f"Item {i+1}/{len(pending)}")
        print(f"{'─'*70}")
        print(f"  URL:         {item.get('url', '?')}")
        print(f"  Type:        {item.get('entity_type', '?')}")
        print(f"  Reason:      {item.get('reason', '?')}")

        if item.get("warnings"):
            print("  Warnings:")
            for w in item["warnings"]:
                print(f"    ⚠ {w}")

        # Show extracted entities if available
        extraction = _load_extraction(item.get("url_hash", ""))
        if extraction:
            entities = extraction.get("entities", [])
            print(f"\n  Extracted {len(entities)} entities:")
            for j, entity in enumerate(entities):
                name = entity.get("name", {})
                name_val = name.get("value", "?") if isinstance(name, dict) else str(name)
                print(f"\n  Entity {j+1}: {name_val}")
                _print_entity(entity)

        print()
        while True:
            choice = input("  [a]ccept / [r]eject / [s]kip / [q]uit? ").strip().lower()
            if choice in ("a", "accept"):
                item["status"] = "accepted"
                print("  → Accepted")
                break
            elif choice in ("r", "reject"):
                item["status"] = "rejected"
                print("  → Rejected")
                break
            elif choice in ("s", "skip"):
                print("  → Skipped")
                break
            elif choice in ("q", "quit"):
                print("  → Quitting review")
                _save_flagged(flagged)
                return
            else:
                print("  Invalid choice. Use a/r/s/q.")

    _save_flagged(flagged)
    print(f"\nReview complete. Updated {REVIEW_DIR / 'flagged.json'}")


def _save_flagged(flagged: list[dict]) -> None:
    """Save flagged items back to disk."""
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "flagged.json").write_text(json.dumps(flagged, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review flagged pipeline items")
    parser.add_argument("--list", action="store_true", dest="do_list", help="List all flagged items")
    parser.add_argument("--stats", action="store_true", help="Show summary statistics")
    args = parser.parse_args()

    if args.do_list:
        cmd_list(args)
    elif args.stats:
        cmd_stats(args)
    else:
        cmd_review(args)


if __name__ == "__main__":
    main()
