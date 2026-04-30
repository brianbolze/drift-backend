"""Tests for scripts/bc_reconcile.py — decision logic + draft rendering.

Decision logic uses lightweight stand-ins for Bullet / BulletBCSource so the
tests don't require a database. End-to-end run against a real DB is exercised
by the dry-run CLI invocation and not unit-tested here.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bc_reconcile.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("bc_reconcile", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bc_reconcile"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


rc = _load_script()


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_source(bc_type: str, bc_value: float, source: str, date: datetime | None = None, url: str | None = None):
    return SimpleNamespace(
        bc_type=bc_type,
        bc_value=bc_value,
        source=source,
        source_date=date,
        source_url=url,
    )


def make_bullet(id_: str, name: str, bc_sources, *, is_locked: bool = False, manufacturer_name: str = "MfrCo", **cols):
    b = SimpleNamespace(
        id=id_,
        name=name,
        is_locked=is_locked,
        bc_sources=bc_sources,
        manufacturer=SimpleNamespace(name=manufacturer_name),
        bc_g1_published=cols.get("bc_g1_published"),
        bc_g1_estimated=cols.get("bc_g1_estimated"),
        bc_g7_published=cols.get("bc_g7_published"),
        bc_g7_estimated=cols.get("bc_g7_estimated"),
    )
    return b


# ── Pure functions ───────────────────────────────────────────────────────────


class TestSpreadPct:
    def test_single_value_zero(self):
        assert rc._spread_pct([0.5]) == 0.0

    def test_identical_values_zero(self):
        assert rc._spread_pct([0.5, 0.5, 0.5]) == 0.0

    def test_computed_correctly(self):
        # min=0.4, max=0.5, mean=0.45, spread = 0.1/0.45 ≈ 0.222
        val = rc._spread_pct([0.4, 0.5])
        assert 0.22 < val < 0.23

    def test_zero_mean_returns_zero(self):
        assert rc._spread_pct([0.0, 0.0]) == 0.0


class TestSourceSortKey:
    def test_priority_ascending(self):
        low = make_source("g1", 0.3, "manufacturer")  # priority 3
        high = make_source("g1", 0.3, "doppler_radar")  # priority 1
        sorted_list = sorted([low, high], key=rc._source_sort_key)
        assert sorted_list[0].source == "doppler_radar"

    def test_unknown_source_deprioritized(self):
        known = make_source("g1", 0.3, "manufacturer")
        unknown = make_source("g1", 0.3, "made_up_source")
        sorted_list = sorted([unknown, known], key=rc._source_sort_key)
        assert sorted_list[0].source == "manufacturer"

    def test_recency_tiebreak(self):
        older = make_source("g1", 0.3, "manufacturer", datetime(2024, 1, 1, tzinfo=timezone.utc))
        newer = make_source("g1", 0.3, "manufacturer", datetime(2026, 1, 1, tzinfo=timezone.utc))
        sorted_list = sorted([older, newer], key=rc._source_sort_key)
        assert sorted_list[0].source_date == newer.source_date


class TestTargetColumn:
    def test_published_for_non_estimated(self):
        assert rc._target_column("g1", "manufacturer") == "bc_g1_published"
        assert rc._target_column("g7", "cartridge_page") == "bc_g7_published"
        assert rc._target_column("g1", "doppler_radar") == "bc_g1_published"

    def test_estimated_routed_separately(self):
        assert rc._target_column("g1", "estimated") == "bc_g1_estimated"
        assert rc._target_column("g7", "estimated") == "bc_g7_estimated"


class TestValuesEqual:
    def test_none_vs_float_false(self):
        assert not rc._values_equal(None, 0.3)

    def test_exact_match_true(self):
        assert rc._values_equal(0.3, 0.3)

    def test_tiny_difference_true(self):
        assert rc._values_equal(0.3, 0.3 + 1e-10)

    def test_meaningful_difference_false(self):
        assert not rc._values_equal(0.3, 0.31)


# ── reconcile_one ────────────────────────────────────────────────────────────


class TestReconcileOne:
    def test_single_source_picks_it(self):
        bullet = make_bullet("b1", "B1", [make_source("g1", 0.4, "manufacturer")])
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileUpdate)
        assert d.new_value == 0.4
        assert d.column == "bc_g1_published"

    def test_no_sources_returns_none(self):
        bullet = make_bullet("b1", "B1", [])
        assert rc.reconcile_one(bullet, "g1") is None

    def test_priority_wins_over_later_insertion(self):
        # Values close together (below G1 threshold) so the priority ladder decides, not review.
        bullet = make_bullet(
            "b1",
            "B1",
            [
                make_source("g1", 0.395, "cartridge_page"),  # priority 4, inserted first
                make_source("g1", 0.405, "manufacturer"),  # priority 3
            ],
        )
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileUpdate)
        assert d.new_value == 0.405
        assert d.chosen.source == "manufacturer"

    def test_concordant_sources_below_threshold_update(self):
        bullet = make_bullet(
            "b1",
            "B1",
            [
                make_source("g1", 0.500, "manufacturer"),
                make_source("g1", 0.505, "manufacturer"),  # 1% spread
            ],
        )
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileUpdate)

    def test_discordant_sources_above_threshold_flag_review(self):
        bullet = make_bullet(
            "b1",
            "B1",
            [
                make_source("g1", 0.400, "manufacturer"),
                make_source("g1", 0.600, "cartridge_page"),  # ~40% spread
            ],
        )
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileReview)
        assert d.spread_pct > 0.08
        # Recommended is the priority-ladder top (manufacturer)
        assert d.recommended.source == "manufacturer"

    def test_g7_threshold_tighter_than_g1(self):
        # 6% spread — above G7 (0.05) but below G1 (0.08)
        sources_g1 = [make_source("g1", 0.500, "manufacturer"), make_source("g1", 0.532, "manufacturer")]
        sources_g7 = [make_source("g7", 0.200, "manufacturer"), make_source("g7", 0.213, "manufacturer")]
        b_g1 = make_bullet("b1", "B1", sources_g1)
        b_g7 = make_bullet("b2", "B2", sources_g7)

        assert isinstance(rc.reconcile_one(b_g1, "g1"), rc.ReconcileUpdate)
        assert isinstance(rc.reconcile_one(b_g7, "g7"), rc.ReconcileReview)

    def test_estimated_only_routes_to_estimated_column(self):
        bullet = make_bullet("b1", "B1", [make_source("g1", 0.4, "estimated")])
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileUpdate)
        assert d.column == "bc_g1_estimated"

    def test_mixed_estimated_and_measured_prefers_measured_column(self):
        bullet = make_bullet(
            "b1",
            "B1",
            [
                make_source("g1", 0.4, "manufacturer"),  # priority 3
                make_source("g1", 0.41, "estimated"),  # priority 6
            ],
        )
        d = rc.reconcile_one(bullet, "g1")
        assert isinstance(d, rc.ReconcileUpdate)
        assert d.column == "bc_g1_published"
        assert d.chosen.source == "manufacturer"


# ── run_reconcile (mutation + stat counting) ────────────────────────────────


class TestRunReconcile:
    def test_is_locked_skipped(self, monkeypatch):
        bullet = make_bullet("b1", "B1", [make_source("g1", 0.5, "manufacturer")], is_locked=True)
        session = SimpleNamespace(
            scalars=lambda _stmt: _FakeScalarResult([bullet]),
        )
        monkeypatch.setattr(rc, "_fetch_bullets", lambda s, bullet_id=None: [bullet])
        stats = rc.run_reconcile(session)
        assert stats.locked_skipped == 1
        assert stats.updated == 0
        assert bullet.bc_g1_published is None  # untouched

    def test_same_value_no_change(self, monkeypatch):
        bullet = make_bullet("b1", "B1", [make_source("g1", 0.500, "manufacturer")], bc_g1_published=0.500)
        monkeypatch.setattr(rc, "_fetch_bullets", lambda s, bullet_id=None: [bullet])
        stats = rc.run_reconcile(SimpleNamespace())
        assert stats.no_change == 1
        assert stats.updated == 0

    def test_update_writes_new_value(self, monkeypatch):
        bullet = make_bullet("b1", "B1", [make_source("g1", 0.480, "manufacturer")], bc_g1_published=0.411)
        monkeypatch.setattr(rc, "_fetch_bullets", lambda s, bullet_id=None: [bullet])
        stats = rc.run_reconcile(SimpleNamespace())
        assert stats.updated == 1
        assert bullet.bc_g1_published == 0.480

    def test_review_required_does_not_touch_column(self, monkeypatch):
        bullet = make_bullet(
            "b1",
            "B1",
            [
                make_source("g1", 0.3, "manufacturer"),
                make_source("g1", 0.6, "cartridge_page"),
            ],
            bc_g1_published=0.411,
        )
        monkeypatch.setattr(rc, "_fetch_bullets", lambda s, bullet_id=None: [bullet])
        stats = rc.run_reconcile(SimpleNamespace())
        assert stats.review_required == 1
        assert stats.updated == 0
        assert bullet.bc_g1_published == 0.411  # untouched


class _FakeScalarResult:  # pragma: no cover
    def __init__(self, items):
        self._items = items

    def __iter__(self):
        return iter(self._items)


# ── Draft YAML rendering ────────────────────────────────────────────────────


class TestDraftRendering:
    def test_renders_comments_and_commented_set(self):
        review = rc.ReconcileReview(
            bullet_id="abc",
            bullet_name="Test Bullet",
            manufacturer_name="TestMfr",
            bc_type="g1",
            spread_pct=0.15,
            threshold=0.08,
            sources=[
                make_source("g1", 0.4, "manufacturer", url="http://a/"),
                make_source("g1", 0.5, "cartridge_page", url="http://b/"),
            ],
            recommended=make_source("g1", 0.4, "manufacturer", url="http://a/"),
        )
        text = rc._render_draft([review])
        assert "patch:" in text
        assert "operations:" in text
        assert "TestMfr" in text
        assert "Test Bullet" in text
        assert "spread:    15.0%" in text
        # The set block must be commented out so the patch can't be applied as-is
        assert "# set:" in text
        assert "#   bc_g1_published: 0.4000" in text
        # No un-commented `set:` in the file — verify by stripping inline whitespace
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("set:"):
                pytest.fail(f"Uncommented set: found — {line!r}")

    def test_quotes_special_chars_in_bullet_name(self):
        review = rc.ReconcileReview(
            bullet_id="abc",
            bullet_name='Weird "quoted" name',
            manufacturer_name="M",
            bc_type="g1",
            spread_pct=0.15,
            threshold=0.08,
            sources=[make_source("g1", 0.4, "manufacturer")],
            recommended=make_source("g1", 0.4, "manufacturer"),
        )
        text = rc._render_draft([review])
        assert '\\"quoted\\"' in text
