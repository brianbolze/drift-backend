"""Measure how many cartridge → bullet links the relaxed-diameter fallback
recovers across every cached cartridge extraction.

Runs normalize + resolve on every cached cartridge JSON twice — once with
the fallback disabled and once with it enabled — and prints per-manufacturer
recovery counts. Read-only; doesn't touch drift.db.

Usage:
    python scripts/retroactive_resolver_recovery.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from drift.pipeline.config import EXTRACTED_DIR
from drift.pipeline.normalization import normalize_entity
from drift.pipeline.resolution.config import DEFAULT_CONFIG
from drift.pipeline.resolution.resolver import EntityResolver

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "drift.db"


@dataclasses.dataclass
class DomainCounts:
    total: int = 0
    primary_linked: int = 0  # bullet_id set under the primary (non-fallback) run
    with_fallback_linked: int = 0  # bullet_id set with fallback enabled
    recovered: int = 0  # linked only under fallback
    still_unmatched: int = 0  # bullet_id=None in both runs


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower()


def main() -> int:  # noqa: C901
    if not DB_PATH.exists():
        print(f"DB not at {DB_PATH}", file=sys.stderr)
        return 2

    engine = create_engine(f"sqlite:///{DB_PATH}")
    counts: dict[str, DomainCounts] = defaultdict(DomainCounts)

    # Load the cartridge extractions once
    cartridges: list[tuple[str, dict]] = []
    for cache in EXTRACTED_DIR.glob("*.json"):
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("entity_type") != "cartridge":
            continue
        ents = data.get("entities") or []
        if not ents:
            continue
        cartridges.append((data.get("url", ""), ents[0]))

    print(f"Examining {len(cartridges)} cached cartridge extractions...\n")

    # Two passes: primary (no fallback) and with fallback enabled
    no_fallback_cfg = dataclasses.replace(DEFAULT_CONFIG, enable_relaxed_diameter_fallback=False)
    with_fallback_cfg = dataclasses.replace(DEFAULT_CONFIG, enable_relaxed_diameter_fallback=True)

    primary_bullet_ids: dict[int, str | None] = {}
    with Session(engine) as session:
        resolver = EntityResolver(session=session, config=no_fallback_cfg)
        for i, (_url, entity) in enumerate(cartridges):
            norm = normalize_entity(entity, "cartridge")
            if norm.rejected:
                primary_bullet_ids[i] = None
                continue
            res = resolver.resolve(norm.entity, "cartridge")
            primary_bullet_ids[i] = res.bullet_id

    with Session(engine) as session:
        resolver = EntityResolver(session=session, config=with_fallback_cfg)
        for i, (url, entity) in enumerate(cartridges):
            dom = _domain(url)
            c = counts[dom]
            c.total += 1
            if primary_bullet_ids[i] is not None:
                c.primary_linked += 1
            norm = normalize_entity(entity, "cartridge")
            if norm.rejected:
                if primary_bullet_ids[i] is None:
                    c.still_unmatched += 1
                continue
            res = resolver.resolve(norm.entity, "cartridge")
            if res.bullet_id is not None:
                c.with_fallback_linked += 1
                if primary_bullet_ids[i] is None:
                    c.recovered += 1
            else:
                if primary_bullet_ids[i] is None:
                    c.still_unmatched += 1

    # ── Report ──────────────────────────────────────────────────────────
    print(f"{'Domain':<30} {'Total':>6} {'Primary':>8} {'+Fallback':>10} {'Recovered':>10} {'Still-None':>11}")
    print("-" * 82)
    totals = DomainCounts()
    for domain, c in sorted(counts.items(), key=lambda kv: -kv[1].total):
        print(
            f"{domain:<30} {c.total:>6} {c.primary_linked:>8} {c.with_fallback_linked:>10} "
            f"{c.recovered:>10} {c.still_unmatched:>11}"
        )
        totals.total += c.total
        totals.primary_linked += c.primary_linked
        totals.with_fallback_linked += c.with_fallback_linked
        totals.recovered += c.recovered
        totals.still_unmatched += c.still_unmatched
    print("-" * 82)
    print(
        f"{'TOTAL':<30} {totals.total:>6} {totals.primary_linked:>8} {totals.with_fallback_linked:>10} "
        f"{totals.recovered:>10} {totals.still_unmatched:>11}"
    )
    if totals.primary_linked:
        pct = 100.0 * totals.recovered / (totals.total - totals.primary_linked or 1)
        print(
            f"\nRecovery rate on previously-unmatched: "
            f"{totals.recovered}/{totals.total - totals.primary_linked} "
            f"({pct:.1f}%)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
