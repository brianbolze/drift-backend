"""Golden-set regression test for the entity resolver.

Runs a labeled set of extraction → entity_id pairs against the production
SQLite database and asserts per-tier accuracy meets the captured baseline.
Fixtures live in ``tests/fixtures/resolution_golden_set.yaml``.

Purpose: steps 1–3 of the entity resolution refactor retuned every tier of
the resolver without a calibration harness (see ``docs/entity_resolution_review.md``
finding #4). This test locks current behavior so any future tuning pass
catches regressions instead of silently trading away matches.

Design choices:
- We run against ``data/drift.db`` (production SQLite, readonly) rather than
  a synthetic seeded in-memory DB. The point is to exercise real candidate
  pools with their actual ambiguity distribution — a seeded fixture of 5
  bullets can't regress the way 1300 can.
- Accuracy is reported per (entity_type, tier) so failures point at the
  specific tier that regressed. A monolithic "95% overall" number would
  hide a pathological 60% on hard cases behind strong easy-tier performance.
- Baselines are captured floors, not targets. We assert
  ``matched >= baseline`` so improvements don't break the test, but any
  backslide does.
- When ``drift.db`` is missing (fresh clone, CI without DB), the test is
  skipped rather than failed. The database is a checked-in artifact; its
  absence is an environment issue, not a resolver regression.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from drift.pipeline.resolution.config import DEFAULT_CONFIG
from drift.pipeline.resolution.resolver import EntityResolver

# Repo-relative paths
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _REPO_ROOT / "data" / "drift.db"
_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "resolution_golden_set.yaml"


# Per-tier minimum accuracy floors. Values are the observed accuracy on the
# fixture file as of step 4; any regression below these fails the test.
# Tighten only when a real improvement is locked in by adding new fixtures.
_BASELINES: dict[tuple[str, str], float] = {
    ("bullet", "easy"): 1.0,
    ("bullet", "medium"): 1.0,
    ("bullet", "hard"): 0.90,
    ("cartridge", "easy"): 1.0,
    ("cartridge", "medium"): 1.0,
    ("cartridge", "hard"): 1.0,
}


@pytest.fixture(scope="module")
def golden_entries() -> list[dict]:
    if not _FIXTURE_PATH.exists():
        pytest.skip(f"fixture missing: {_FIXTURE_PATH}")
    data = yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["entries"]


@pytest.fixture(scope="module")
def prod_session():
    """Read-only session against the production drift.db.

    Skipped when the file isn't present. The DB is a checked-in artifact, so
    absence means the test environment is incomplete rather than that the
    resolver is broken.
    """
    if not _DB_PATH.exists():
        pytest.skip(f"production DB missing: {_DB_PATH}")
    engine = create_engine(f"sqlite:///{_DB_PATH}")
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _resolve_and_score(session: Session, entries: list[dict]) -> dict[tuple[str, str], dict]:
    """Run the resolver against each fixture entry and bucket outcomes by (entity_type, tier).

    For ``expected_entity_id: null`` fixtures, "correct" means either no match
    or a match below the pipeline_store match threshold (≤ baseline flag
    behavior). Otherwise correct means ``match.entity_id == expected_entity_id``.
    """
    resolver = EntityResolver(session, config=DEFAULT_CONFIG)
    by_bucket: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
            "by_method": defaultdict(int),
            "failures": [],
        }
    )
    for entry in entries:
        entity_type = entry["entity_type"]
        tier = entry["tier"]
        bucket = by_bucket[(entity_type, tier)]
        bucket["total"] += 1

        result = resolver.resolve(entry["extraction"], entity_type)
        match = result.match
        expected = entry["expected_entity_id"]

        if expected is None:
            # Correct when the resolver either didn't match or matched below the
            # pipeline_store threshold (so the entry would be flagged, not auto-matched).
            auto_matched = match.matched and match.confidence >= DEFAULT_CONFIG.match_confidence_threshold
            if not auto_matched:
                bucket["correct"] += 1
                bucket["by_method"]["(flag_or_no_match)"] += 1
            else:
                bucket["failures"].append(
                    f"[{entry['category']}] {entry['description']!r} — false-positive "
                    f"matched {match.entity_id} via {match.method} (conf={match.confidence:.2f})"
                )
        else:
            if match.matched and match.entity_id == expected:
                bucket["correct"] += 1
                bucket["by_method"][match.method or "(none)"] += 1
            else:
                got = match.entity_id or "<no match>"
                bucket["failures"].append(
                    f"[{entry['category']}] {entry['description']!r} — got {got} "
                    f"via {match.method or 'none'} (conf={match.confidence:.2f}), want {expected}"
                )
    return by_bucket


def test_golden_set_per_tier_accuracy(prod_session, golden_entries):
    """Per-tier accuracy on labeled extractions must meet the captured baseline.

    Failure output shows per-bucket accuracy, method breakdown, and the specific
    fixtures that regressed — so a drop on "bullet/hard fuzzy_name" is
    immediately visible without scanning the whole suite.
    """
    outcomes = _resolve_and_score(prod_session, golden_entries)

    report_lines: list[str] = []
    regressed: list[str] = []

    for bucket_key in sorted(outcomes):
        bucket = outcomes[bucket_key]
        total = bucket["total"]
        correct = bucket["correct"]
        pct = correct / total if total else 0.0
        baseline = _BASELINES.get(bucket_key, 0.0)
        methods = ", ".join(f"{m}={n}" for m, n in sorted(bucket["by_method"].items(), key=lambda kv: -kv[1]))
        report_lines.append(
            f"  {bucket_key[0]:<10} {bucket_key[1]:<6} {correct}/{total} = {pct:.0%} "
            f"(baseline {baseline:.0%}) [{methods}]"
        )
        if pct < baseline:
            regressed.append(f"{bucket_key}: {pct:.0%} < baseline {baseline:.0%}")
            for failure in bucket["failures"]:
                report_lines.append(f"      FAIL: {failure}")

    report = "Golden-set resolver accuracy:\n" + "\n".join(report_lines)

    assert not regressed, f"Resolver regression vs baseline — {', '.join(regressed)}\n\n{report}"


def test_golden_set_covers_all_tiers(golden_entries):
    """Sanity: fixture exercises every declared (entity_type, tier) pair.

    If someone deletes the last ``bullet/hard`` fixture the regression test
    above silently loses coverage — this guards against that.
    """
    seen = {(e["entity_type"], e["tier"]) for e in golden_entries}
    expected = set(_BASELINES.keys())
    missing = expected - seen
    assert not missing, f"fixture missing buckets: {missing}"


def test_golden_set_minimum_size(golden_entries):
    """Fixture must have enough entries per bucket for the accuracy numbers to mean anything.

    Fewer than 3 entries per bucket and per-tier accuracy swings 33% per failure —
    baseline floor would be either useless or flaky. Raise this as more real
    extractions get hand-labeled.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for entry in golden_entries:
        counts[(entry["entity_type"], entry["tier"])] += 1
    undersized = {key: n for key, n in counts.items() if n < 3}
    assert not undersized, f"buckets with <3 fixtures: {undersized}"
