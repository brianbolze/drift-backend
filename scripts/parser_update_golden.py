"""Re-run a parser over its golden-set fixtures and overwrite ``.expected.json``.

Usage:
    python scripts/parser_update_golden.py hornady            # refresh all cases
    python scripts/parser_update_golden.py hornady --only bullet_with_g7

Committers review the resulting diff before merging. This is the only
sanctioned way to regenerate expected-JSON; don't hand-edit the files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from drift.pipeline.extraction.parsers.registry import _instantiate

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "parsers"


def update(parser_name: str, only: str | None) -> int:
    parser = _instantiate(parser_name)
    if parser is None:
        print(f"Unknown parser: {parser_name}", file=sys.stderr)
        return 2

    fixture_dir = FIXTURES_ROOT / parser_name
    if not fixture_dir.exists():
        print(f"No fixture directory: {fixture_dir}", file=sys.stderr)
        return 2

    updated = 0
    skipped = 0

    for html_path in sorted(fixture_dir.glob("*.html")):
        if only and html_path.stem != only:
            continue
        expected_path = html_path.with_suffix(".expected.json")
        if not expected_path.exists():
            print(f"  SKIP (no .expected.json): {html_path.name}")
            skipped += 1
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        html = html_path.read_text(encoding="utf-8")
        result = parser.parse(html, expected["url"], expected["entity_type"])

        if expected.get("expect_none"):
            if result is not None:
                print(f"  WARN: {html_path.name} expected None but parser returned a result")
            else:
                print(f"  OK:   {html_path.name} (still declines)")
            continue

        if result is None:
            print(f"  FAIL: {html_path.name} — parser now returns None (was a success)")
            return 1

        new_expected = {
            "url": expected["url"],
            "entity_type": expected["entity_type"],
            "entities": [e.model_dump() for e in result.entities],
            "bc_sources": [bc.model_dump() for bc in result.bc_sources],
        }
        expected_path.write_text(json.dumps(new_expected, indent=2), encoding="utf-8")
        print(f"  WROTE: {html_path.name}")
        updated += 1

    print(f"\nUpdated {updated} fixture(s), skipped {skipped}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate parser golden fixtures.")
    parser.add_argument("parser_name", help="Parser short name (e.g. 'hornady')")
    parser.add_argument("--only", help="Refresh only a single case by stem (e.g. 'bullet_with_g7')")
    args = parser.parse_args()
    return update(args.parser_name, args.only)


if __name__ == "__main__":
    sys.exit(main())
