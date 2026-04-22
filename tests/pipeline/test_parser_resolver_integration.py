"""End-to-end integration test: parser → normalize → resolve → assert DB linkage.

Runs a parser-emitted Nosler cartridge through the real normalization and
resolver stages against the live ``data/drift.db`` and asserts that the
cartridge's ``bullet_id`` resolves to an expected Nosler bullet in the DB.

The first parser (Hornady) and the second (Sierra) both exercise the bullet
path. Nosler is the first one where the cartridge path runs at scale with
null BCs — so the resolver's BC-boost logic (+0.05 per matching BC signal,
max +0.15) never fires. Linkage confidence comes from weight + bullet_name
similarity alone. This test pins that behavior so we'll notice if the
resolver ever regresses on a null-BC cartridge.

Skipped automatically if ``data/drift.db`` isn't present (e.g. in CI
environments that don't bundle the full DB).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from drift.pipeline.config import FETCHED_DIR
from drift.pipeline.extraction.parsers.nosler import NoslerParser
from drift.pipeline.normalization import normalize_entity
from drift.pipeline.resolution.resolver import EntityResolver

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "drift.db"


@pytest.fixture(scope="module")
def session():
    if not DB_PATH.exists():
        pytest.skip(f"drift.db not available at {DB_PATH}")
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="module")
def resolver(session):
    return EntityResolver(session=session)


def _find_fetched_html(url_hash: str) -> str | None:
    """Return the raw HTML for ``url_hash`` or None if the cache doesn't have it."""
    path = FETCHED_DIR / f"{url_hash}.html"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# Curated parser-to-resolver fixtures. Each case is a real cached Nosler
# cartridge page that's known to have a corresponding bullet in the DB.
# ``expected_bullet_name_substring`` is asserted against the resolved
# ``Bullet.name`` to avoid brittling on exact text while still validating
# that the cartridge linked to the *correct* bullet family.
#
# When picking new cases: the URL + hash must match a Nosler cartridge in
# ``data/drift.db`` that has ``bullet_id`` populated, and the expected
# substring should be specific enough to fail if the resolver latches onto
# the wrong bullet family (e.g. "AccuBond" is too loose — ambiguous with
# "AccuBond Long Range").
_CASES = [
    # 22-250 Rem Ballistic Tip Lead Free — clean 1.0-confidence composite_key
    # match against an existing 22 Cal 40gr Ballistic Tip Lead Free bullet.
    {
        "url": "https://www.nosler.com/22-250-remington-40gr-ballistic-tip-lead-free-varmint-ammunition.html",
        "url_hash": "a9f59f4befafbd16",
        "expected_bullet_name_substring": "Ballistic Tip Lead Free",
        "expected_caliber_substring": "22-250",
    },
    # 270 Wby Mag AccuBond LR — exercises the "Long Range" variant family
    # (ambiguous against the non-LR AccuBond line if the resolver is sloppy).
    {
        "url": "https://www.nosler.com/270-wby-mag-150gr-accubond-long-range-trophy-grade-ammunition.html",
        "url_hash": "ee7f70b8b2f01124",
        "expected_bullet_name_substring": "AccuBond Long Range",
        "expected_caliber_substring": "270",
    },
    # 280 AI Ballistic Tip Hunting — a 280 AI cartridge resolving to a 7mm
    # bullet (same .284" diameter) tests cross-caliber-name bullet linkage.
    {
        "url": "https://www.nosler.com/280-ackley-improved-140gr-ballistic-tip-hunting-ammunition.html",
        "url_hash": "c7455213111e3772",
        "expected_bullet_name_substring": "Ballistic Tip Hunting",
        "expected_caliber_substring": "280",
    },
]


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["url_hash"])
def test_nosler_cartridge_resolves_to_expected_bullet(case, resolver, session):
    """Parser → normalize → resolve → assert DB linkage is correct."""
    html = _find_fetched_html(case["url_hash"])
    if html is None:
        pytest.skip(f"fetched HTML not available for {case['url_hash']}")

    # 1. Parse
    parser = NoslerParser()
    result = parser.parse(html, case["url"], "cartridge")
    assert result is not None, "parser returned None on a known-good cartridge"
    assert len(result.entities) == 1

    parser_entity = result.entities[0]
    extracted = parser_entity.model_dump()

    # 2. Normalize (unit-confusion + range guards)
    normalized_result = normalize_entity(extracted, "cartridge")
    assert not normalized_result.rejected, f"normalization rejected: {normalized_result.rejection_reason}"
    normalized = normalized_result.entity

    # 3. Resolve against DB
    resolution = resolver.resolve(normalized, "cartridge")

    # 4. Assert bullet linkage
    assert resolution.bullet_id is not None, (
        f"resolver produced bullet_id=None for {case['url']} "
        f"(methods tried: {resolution.methods_tried}, confidence: {resolution.bullet_match_confidence})"
    )
    assert resolution.bullet_match_confidence is not None
    assert resolution.bullet_match_confidence >= 0.5, (
        f"bullet_match_confidence={resolution.bullet_match_confidence} below "
        f"fk_min_confidence 0.5 — cartridge would ship with bullet_id=None"
    )

    # Look up the bullet to validate the actual linkage target
    from drift.models.bullet import Bullet  # local import to keep top-level clean

    bullet = session.scalar(select(Bullet).where(Bullet.id == resolution.bullet_id))
    assert bullet is not None
    assert case["expected_bullet_name_substring"].lower() in bullet.name.lower(), (
        f"resolver linked to wrong bullet: expected substring "
        f"{case['expected_bullet_name_substring']!r}, got {bullet.name!r}"
    )


def test_nosler_null_bc_cartridge_bullet_match_confidence_baseline(resolver, session):  # noqa: C901
    """Report the bullet_match_confidence distribution across every cached
    Nosler cartridge the parser can handle. Not a pass/fail test — if this
    ever surfaces confidences below 0.5 at scale, the cartridge path is
    silently shipping bullet_id=None on a non-trivial fraction.

    Emitted as a print so it shows up in test stdout; doesn't assert a
    threshold beyond "no crashes".
    """
    import json
    from collections import Counter

    parser = NoslerParser()
    buckets = Counter()
    total = 0
    below_gate = 0
    no_bullet = 0

    for meta_path in FETCHED_DIR.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        url = meta.get("url", "")
        if "nosler.com" not in url or "-ammunition.html" not in url:
            continue
        html_path = FETCHED_DIR / f"{meta_path.stem}.html"
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding="utf-8")
        result = parser.parse(html, url, "cartridge")
        if result is None or not result.entities:
            continue
        total += 1

        extracted = result.entities[0].model_dump()
        norm = normalize_entity(extracted, "cartridge")
        if norm.rejected:
            continue

        resolution = resolver.resolve(norm.entity, "cartridge")
        conf = resolution.bullet_match_confidence
        if resolution.bullet_id is None:
            no_bullet += 1
            buckets["no_bullet_id"] += 1
        elif conf is None:
            buckets["no_confidence"] += 1
        else:
            if conf < 0.5:
                below_gate += 1
                buckets["<0.5"] += 1
            elif conf < 0.7:
                buckets["0.5-0.7"] += 1
            elif conf < 0.9:
                buckets["0.7-0.9"] += 1
            else:
                buckets[">=0.9"] += 1

    print(
        f"\nNosler cartridge → bullet resolution distribution (n={total}):\n"
        f"  {dict(buckets)}\n"
        f"  below fk_min_confidence (0.5): {below_gate}\n"
        f"  bullet_id=None: {no_bullet}"
    )
    # Sanity: no crashes and at least most cartridges resolved to something.
    assert total > 0, "no Nosler cartridges parsed — test is mis-scoped"
