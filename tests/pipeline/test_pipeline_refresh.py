"""Tests for scripts/pipeline_refresh.py — diff classification logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "pipeline_refresh.py"


def _load():
    spec = importlib.util.spec_from_file_location("pipeline_refresh", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_refresh"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pr = _load()


# ── Value comparison ─────────────────────────────────────────────────────────


class TestValuesEqual:
    def test_identical_primitives(self):
        assert pr._values_equal(1, 1)
        assert pr._values_equal("a", "a")

    def test_float_tolerance(self):
        assert pr._values_equal(0.3, 0.3 + 1e-12)

    def test_lists_order_insensitive(self):
        assert pr._values_equal(["a", "b", "c"], ["c", "b", "a"])

    def test_lists_with_unhashable_items(self):
        # Sort would raise TypeError — falls back to direct equality.
        assert pr._values_equal([{"a": 1}], [{"a": 1}])
        assert not pr._values_equal([{"a": 1}], [{"a": 2}])

    def test_none_eq_none(self):
        assert pr._values_equal(None, None)

    def test_none_neq_value(self):
        assert not pr._values_equal(None, "x")


class TestUnwrap:
    def test_extracted_value_shape_unwrapped(self):
        assert pr._unwrap({"value": "x", "source_text": "...", "confidence": 0.9}) == "x"

    def test_plain_scalar_passed_through(self):
        assert pr._unwrap(0.5) == 0.5
        assert pr._unwrap("x") == "x"
        assert pr._unwrap(None) is None

    def test_dict_missing_keys_passed_through(self):
        assert pr._unwrap({"value": 1}) == {"value": 1}  # no source_text / confidence


class TestNumericClose:
    def test_close_floats(self):
        assert pr._numeric_close(0.500, 0.510, 0.05)  # 2% < 5% threshold

    def test_far_floats(self):
        assert not pr._numeric_close(0.500, 0.600, 0.05)  # ~18% > 5%

    def test_both_zero(self):
        assert pr._numeric_close(0.0, 0.0, 0.05)

    def test_non_numeric_returns_false(self):
        assert not pr._numeric_close("a", "b", 0.05)


# ── Field classification ─────────────────────────────────────────────────────


class TestClassifyField:
    def test_identical(self):
        assert pr._classify_field("name", "Foo", "Foo") == "identical"

    def test_gap_fill(self):
        assert pr._classify_field("product_line", None, "ELD-X") == "gap_fill"
        assert pr._classify_field("product_line", "", "ELD-X") == "gap_fill"

    def test_regression(self):
        assert pr._classify_field("base_type", "boat_tail", None) == "regression"

    def test_bc_small_change_is_safe(self):
        assert pr._classify_field("bc_g1", 0.500, 0.510) == "value_change_safe"

    def test_bc_big_change_is_material(self):
        # BC_DRIFT_SAFE_PCT = 0.05, delta 20% → material
        assert pr._classify_field("bc_g1", 0.500, 0.600) == "value_change_material"

    def test_material_field_value_change(self):
        assert pr._classify_field("name", "Foo", "Bar") == "value_change_material"

    def test_non_material_field_value_change_is_safe(self):
        assert pr._classify_field("product_line", "ELD-X", "ELD Match") == "value_change_safe"


# ── Entity diff ─────────────────────────────────────────────────────────────


class TestDiffEntity:
    def test_all_identical_entities(self):
        e1 = {"name": "A", "bc_g1": 0.5}
        e2 = {"name": "A", "bc_g1": 0.5}
        diff = pr.diff_entity(e1, e2, ["name", "bc_g1"])
        assert not diff.has_changes()
        assert diff.classification() == "noise"

    def test_gap_fill_entity_classified_safe(self):
        e1 = {"name": "A", "product_line": None}
        e2 = {"name": "A", "product_line": "ELD-X"}
        diff = pr.diff_entity(e1, e2, ["name", "product_line"])
        assert diff.has_changes()
        assert diff.classification() == "safe_update"

    def test_regression_entity_classified_review(self):
        e1 = {"name": "A", "base_type": "boat_tail"}
        e2 = {"name": "A", "base_type": None}
        diff = pr.diff_entity(e1, e2, ["name", "base_type"])
        assert diff.classification() == "review_required"

    def test_material_value_change_review(self):
        e1 = {"name": "A", "weight_grains": 140}
        e2 = {"name": "A", "weight_grains": 143}
        diff = pr.diff_entity(e1, e2, ["name", "weight_grains"])
        assert diff.classification() == "review_required"


class TestAlignEntities:
    def test_equal_lengths(self):
        old = [{"a": 1}, {"a": 2}]
        new = [{"a": 1}, {"a": 2}]
        pairs, missing, extra = pr._align_entities(old, new)
        assert len(pairs) == 2
        assert missing == 0
        assert extra == 0

    def test_cache_has_more(self):
        old = [{"a": 1}, {"a": 2}, {"a": 3}]
        new = [{"a": 1}]
        pairs, missing, extra = pr._align_entities(old, new)
        assert len(pairs) == 1
        assert missing == 2
        assert extra == 0

    def test_parser_has_more(self):
        old = [{"a": 1}]
        new = [{"a": 1}, {"a": 2}, {"a": 3}]
        pairs, missing, extra = pr._align_entities(old, new)
        assert len(pairs) == 1
        assert missing == 0
        assert extra == 2
