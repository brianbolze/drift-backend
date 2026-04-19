"""Normalization step between EXTRACT and RESOLVE.

Catches unit-confusion errors from LLM extraction (metric/imperial mix-ups)
and flags extracted numeric values that fall outside plausible physical
ranges. Mutates a *copy* of the extracted entity dict so the pipeline cache
on disk is unaffected.

Two kinds of guardrails:

1. **Unit-confusion heuristics.** If a numeric field is out of the known
   valid range and a single obvious conversion would land it back inside,
   apply the conversion and record the event. Handles:
     * weight in grams mistakenly stored as grains (``* 15.4324``)
     * muzzle velocity in m/s mistakenly stored as fps (``* 3.28084``)
     * bullet diameter in mm mistakenly stored as inches (``/ 25.4``)
     * bullet/projectile length in mm → inches (``/ 25.4``)

2. **Range flag-don't-store guards.** When no conversion recovers a valid
   value, null the field and emit a warning. Critical fields (bullet
   weight, bullet diameter) mark the whole entity as rejected so
   ``pipeline_store`` skips resolution and storage rather than writing a
   record with known-bad data.

The immediate regression target is the Lapua G580 case in TODO.md where
``6,5 g`` (6.5 grams, ≈100 gr) was extracted into a ``weight_grains=6.5``
field — the grams→grains heuristic now recovers a valid value instead of
letting the downstream resolver choose a wrong caliber family.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from drift.pipeline.config import VALIDATION_RANGES

# Unit conversion constants
GRAINS_PER_GRAM = 15.4324
FPS_PER_MPS = 3.28084
MM_PER_INCH = 25.4


@dataclass
class NormalizationEvent:
    """Audit record for one normalization action taken on a field."""

    field: str
    original_value: float
    normalized_value: float | None
    reason: str  # e.g. "grams_to_grains", "mm_to_inches", "nulled_out_of_range"

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "original_value": self.original_value,
            "normalized_value": self.normalized_value,
            "reason": self.reason,
        }


@dataclass
class NormalizationResult:
    """Outcome of normalizing a single extracted entity."""

    entity: dict
    events: list[NormalizationEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected: bool = False
    rejection_reason: str | None = None

    @property
    def modified(self) -> bool:
        return bool(self.events)


# Fields that are critical to entity identity. If we can't recover a valid
# value for one of these, reject the entity rather than creating a half-baked
# record with unknown diameter/weight.
_CRITICAL_FIELDS: dict[str, set[str]] = {
    "bullet": {"bullet_diameter_inches", "weight_grains"},
    "cartridge": set(),
    "rifle": set(),
}


def _get_value(entity: dict, field_name: str) -> Any:
    """Pull the raw value out of an ExtractedValue dict wrapper (or a scalar)."""
    payload = entity.get(field_name)
    if isinstance(payload, dict):
        return payload.get("value")
    return payload


def _set_value(entity: dict, field_name: str, value: Any) -> None:
    """Write a value back through the ExtractedValue wrapper, preserving metadata."""
    payload = entity.get(field_name)
    if isinstance(payload, dict):
        payload["value"] = value
    else:
        entity[field_name] = value


def _coerce_float(val: Any) -> float | None:
    """Best-effort float conversion; returns None if the value can't be parsed.

    Handles European decimal commas (``"6,5"`` → 6.5) because extractions of
    non-English spec sheets sometimes leak them into numeric fields as strings.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(",", ".").strip())
        except ValueError:
            return None
    return None


def _in_range(value: float, lo: float, hi: float) -> bool:
    return lo <= value <= hi


# Per-field conversion attempts. Each entry is (conversion_factor, reason).
# The conversion is only applied if the resulting value lands inside the
# field's valid range from VALIDATION_RANGES.
_CONVERSION_ATTEMPTS: dict[str, tuple[float, str]] = {
    "weight_grains": (GRAINS_PER_GRAM, "grams_to_grains"),
    "bullet_weight_grains": (GRAINS_PER_GRAM, "grams_to_grains"),
    "muzzle_velocity_fps": (FPS_PER_MPS, "m/s_to_fps"),
    "bullet_diameter_inches": (1.0 / MM_PER_INCH, "mm_to_inches"),
    "length_inches": (1.0 / MM_PER_INCH, "mm_to_inches"),
    "bullet_length_inches": (1.0 / MM_PER_INCH, "mm_to_inches"),
}


def _normalize_field(entity: dict, field_name: str, entity_label: str) -> NormalizationEvent | None:
    """Normalize one field in-place. Returns an event iff a change was made.

    Algorithm:
      1. Read value. If None, no-op.
      2. If value is in valid range, no-op.
      3. If a unit conversion exists for this field, try it. If the converted
         value lands in range, apply the conversion and return a conversion
         event.
      4. Otherwise, null the field (flag-don't-store) and return a nulled event.
    """
    if field_name not in VALIDATION_RANGES:
        return None

    raw = _get_value(entity, field_name)
    if raw is None:
        return None

    val = _coerce_float(raw)
    if val is None:
        return None

    lo, hi = VALIDATION_RANGES[field_name]

    # Coerced-from-string values: even if in range, write the float back so
    # downstream code sees a numeric type. This is a silent cleanup, no event.
    if _in_range(val, lo, hi):
        if not isinstance(raw, (int, float)):
            _set_value(entity, field_name, val)
        return None

    attempt = _CONVERSION_ATTEMPTS.get(field_name)
    if attempt is not None:
        factor, reason = attempt
        converted = val * factor
        if _in_range(converted, lo, hi):
            _set_value(entity, field_name, converted)
            return NormalizationEvent(
                field=field_name,
                original_value=val,
                normalized_value=converted,
                reason=reason,
            )

    # Flag-don't-store: null the value, emit an event.
    _set_value(entity, field_name, None)
    return NormalizationEvent(
        field=field_name,
        original_value=val,
        normalized_value=None,
        reason=f"nulled_out_of_range[{lo},{hi}]",
    )


def normalize_entity(entity: dict, entity_type: str) -> NormalizationResult:
    """Apply unit-confusion heuristics and range guards to one extracted entity.

    Returns a NormalizationResult carrying a normalized copy of the entity,
    along with audit events and warnings. ``rejected=True`` means the entity
    should not be passed to the resolver (a critical identity field was
    outside the plausible range and could not be recovered).
    """
    normalized = copy.deepcopy(entity)
    result = NormalizationResult(entity=normalized)

    name = _get_value(normalized, "name") or _get_value(normalized, "model") or "<unnamed>"
    critical = _CRITICAL_FIELDS.get(entity_type, set())

    for field_name in VALIDATION_RANGES:
        if field_name not in normalized:
            continue
        event = _normalize_field(normalized, field_name, name)
        if event is None:
            continue
        result.events.append(event)

        if event.normalized_value is None:
            result.warnings.append(
                f"{name}: {field_name}={event.original_value} outside valid range "
                f"{VALIDATION_RANGES[field_name]} — nulled"
            )
            if field_name in critical:
                result.rejected = True
                result.rejection_reason = (
                    f"critical field {field_name}={event.original_value} outside valid range "
                    f"{VALIDATION_RANGES[field_name]}; no unit conversion recovers a valid value"
                )
        else:
            result.warnings.append(
                f"{name}: {field_name}={event.original_value} → {event.normalized_value:.4f} "
                f"(applied {event.reason})"
            )

    return result
