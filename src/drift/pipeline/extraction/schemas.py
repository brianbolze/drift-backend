"""Extraction schemas — Pydantic models for LLM-extracted product data.

Every extracted field is wrapped in ExtractedValue[T] which carries
the raw value, the source text from the HTML, and a confidence score.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Fields:
    """Field definitions for extraction schemas."""

    @staticmethod
    def value():
        return Field(..., description="The extracted value")

    @staticmethod
    def source_text():
        return Field(
            "",
            description="Exact snippet from the HTML that supports this value",
            examples=["6.5mm .264 140 gr ELD Match"],
        )

    @staticmethod
    def confidence():
        return Field(
            0.0,
            ge=0.0,
            le=1.0,
            description="LLM self-assessed confidence: 1.0 = explicit, 0.7-0.9 = implied, <0.7 = uncertain",
            examples=[0.95],
        )


class ExtractedValue(BaseModel, Generic[T]):
    """Wrapper for every LLM-extracted field: value + provenance."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: T = Fields.value()
    source_text: str = Fields.source_text()
    confidence: float = Fields.confidence()


class ExtractedBullet(BaseModel):
    """Bullet product data extracted from a manufacturer page."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: ExtractedValue[str]
    manufacturer: ExtractedValue[str]
    bullet_diameter_inches: ExtractedValue[float]
    weight_grains: ExtractedValue[float]
    bc_g1: ExtractedValue[float | None]
    bc_g7: ExtractedValue[float | None]
    length_inches: ExtractedValue[float | None] = Field(
        ...,
        description="Bullet (projectile) tip-to-base length in inches. "
        "NOT cartridge OAL/COAL. Typically 0.5–1.8 inches.",
    )
    sectional_density: ExtractedValue[float | None]
    base_type: ExtractedValue[str | None]
    tip_type: ExtractedValue[str | None]
    type_tags: ExtractedValue[list[str] | None]
    used_for: ExtractedValue[list[str] | None]
    sku: ExtractedValue[str | None]


class ExtractedCartridge(BaseModel):
    """Factory-loaded cartridge data extracted from a manufacturer page."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: ExtractedValue[str]
    manufacturer: ExtractedValue[str]
    caliber: ExtractedValue[str | None]
    bullet_name: ExtractedValue[str | None]
    bullet_weight_grains: ExtractedValue[float | None]
    bc_g1: ExtractedValue[float | None]
    bc_g7: ExtractedValue[float | None]
    bullet_length_inches: ExtractedValue[float | None] = Field(
        ...,
        description="Bullet (projectile) tip-to-base length in inches. "
        "NOT cartridge OAL/COAL. Typically 0.5–1.8 inches.",
    )
    muzzle_velocity_fps: ExtractedValue[int | None]
    test_barrel_length_inches: ExtractedValue[float | None]
    round_count: ExtractedValue[int | None]
    product_line: ExtractedValue[str | None]
    sku: ExtractedValue[str | None]


class ExtractedRifleModel(BaseModel):
    """Rifle model data extracted from a manufacturer page."""

    model_config = ConfigDict(str_strip_whitespace=True)

    model: ExtractedValue[str]
    manufacturer: ExtractedValue[str]
    caliber: ExtractedValue[str]
    barrel_length_inches: ExtractedValue[float | None]
    twist_rate: ExtractedValue[str | None]
    weight_lbs: ExtractedValue[float | None]
    barrel_material: ExtractedValue[str | None]
    barrel_finish: ExtractedValue[str | None]
    model_family: ExtractedValue[str | None]


class ExtractedBCSource(BaseModel):
    """BC observation extracted alongside a bullet for multi-source audit trail."""

    model_config = ConfigDict(str_strip_whitespace=True)

    bullet_name: str
    bc_type: Literal["g1", "g7"]
    bc_value: float
    source: Literal["manufacturer", "cartridge_page", "applied_ballistics", "doppler_radar", "independent_test", "estimated"] = (
        "manufacturer"
    )
    source_methodology: str | None = None
