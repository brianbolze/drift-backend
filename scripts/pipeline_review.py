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
from collections import defaultdict
from urllib.parse import urlparse

from drift.pipeline.config import DOMAIN_PARSER, EXTRACTED_DIR, REVIEW_DIR

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
        logger.warning("Could not parse flagged items at %s", flagged_path)
        return []


def _load_store_report() -> dict | None:
    """Load the store report if it exists."""
    from drift.pipeline.config import STORE_REPORT_PATH

    if not STORE_REPORT_PATH.exists():
        return None
    try:
        return json.loads(STORE_REPORT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse store report at %s", STORE_REPORT_PATH)
        return None


_METHOD_KEYS = ("parser", "parser_fellthrough_to_llm", "llm", "legacy")


def _extraction_method_breakdown() -> tuple[dict[str, dict[str, int]], int]:
    """Walk the extracted cache and count extraction_method per domain.

    Returns (per_domain_counts, total_files). ``legacy`` buckets cache files
    written before the ``extraction_method`` field existed — they pre-date
    the parser tier so including them in the parser-rate calculation would
    make every domain look broken until the cache rolls over. The parser-
    rate ratio below is computed only over non-legacy records.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {k: 0 for k in _METHOD_KEYS})
    total = 0
    for cache_file in EXTRACTED_DIR.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            continue
        url = data.get("url", "")
        domain = urlparse(url).netloc.lower() or "<unknown>"
        method = data.get("extraction_method")
        if method is None:
            method = "legacy"
        elif method not in _METHOD_KEYS:
            method = "llm"  # defensive: unknown value
        counts[domain][method] += 1
        total += 1
    return dict(counts), total


def _print_extraction_method_breakdown() -> None:  # noqa: C901
    """Print per-domain extraction-method rollup. Highlights domains with a
    registered parser — low parser-rate on those is the leading indicator
    that a manufacturer redesigned their site and the parser is stale."""
    counts, total = _extraction_method_breakdown()
    if total == 0:
        return

    print(f"\n{'='*82}")
    print("Extraction-method breakdown")
    print(f"{'='*82}\n")

    rows_registered: list[tuple[str, dict[str, int]]] = []
    rows_other: list[tuple[str, dict[str, int]]] = []
    small_agg = {k: 0 for k in _METHOD_KEYS}
    small_domains = 0

    for domain, c in counts.items():
        domain_total = sum(c.values())
        if domain in DOMAIN_PARSER:
            rows_registered.append((domain, c))
        elif domain_total < 10:
            for k in small_agg:
                small_agg[k] += c[k]
            small_domains += 1
        else:
            rows_other.append((domain, c))

    rows_registered.sort(key=lambda r: -r[1]["parser"])
    rows_other.sort(key=lambda r: -sum(r[1].values()))

    header = f"  {'Domain':<38} {'Parser':>7} {'Fallthru':>9} " f"{'LLM':>5} {'Legacy':>7} {'Total':>6}  Parser%"
    print(header)
    print(f"  {'-'*38} {'-'*7} {'-'*9} {'-'*5} {'-'*7} {'-'*6}  {'-'*7}")

    def _row(label: str, c: dict[str, int], flag_parser: bool) -> str:
        dt = sum(c.values())
        parser_pct_str = "—"
        if flag_parser:
            denom = c["parser"] + c["parser_fellthrough_to_llm"] + c["llm"]
            if denom > 0:
                parser_pct_str = f"{100 * c['parser'] / denom:.1f}%"
        return (
            f"  {label:<38} {c['parser']:>7} {c['parser_fellthrough_to_llm']:>9} "
            f"{c['llm']:>5} {c['legacy']:>7} {dt:>6}  {parser_pct_str:>7}"
        )

    if rows_registered:
        print("  Registered parser domains:")
        for domain, c in rows_registered:
            print(_row(domain, c, flag_parser=True))
    if rows_other:
        print("\n  Other domains (≥10 items):")
        for domain, c in rows_other:
            print(_row(domain, c, flag_parser=False))
    if small_domains:
        print(f"\n  Aggregated ({small_domains} domains with <10 items):")
        print(_row(f"<{small_domains} small domains>", small_agg, flag_parser=False))

    grand = {k: 0 for k in _METHOD_KEYS}
    for c in counts.values():
        for k in grand:
            grand[k] += c[k]
    print(
        f"\n  Totals: {grand['parser']} parser, "
        f"{grand['parser_fellthrough_to_llm']} fallthrough, "
        f"{grand['llm']} llm, {grand['legacy']} legacy  "
        f"(of {total} cached extractions)"
    )

    # Drift-detection hint for parser domains whose parser-rate dropped.
    # Only trigger when the parser-era sample size is big enough (≥20) to
    # avoid noise from small post-rollout windows.
    for domain, c in rows_registered:
        denom = c["parser"] + c["parser_fellthrough_to_llm"] + c["llm"]
        if denom < 20:
            continue
        rate = c["parser"] / denom
        if rate < 0.80:
            print(
                f"\n  ⚠ {domain}: parser rate {rate*100:.1f}% "
                f"over {denom} parser-era records — below 80%. "
                f"Check whether the site structure changed."
            )


def _load_extraction(url_hash: str) -> dict | None:
    """Load an extraction result by URL hash."""
    path = EXTRACTED_DIR / f"{url_hash}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse extraction at %s", path)
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
    _print_extraction_method_breakdown()

    flagged = _load_flagged()
    if not flagged:
        print("\nNo flagged items found.")
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
    _print_extraction_method_breakdown()

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
