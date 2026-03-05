# flake8: noqa: E501 B950 — prompt strings are intentionally long
"""LLM extraction engine — sends reduced HTML to an LLM and parses structured product data.

Uses Claude Haiku as the default model (validated across 5 manufacturer sites in spike).
Supports multiple LLM providers (Anthropic, OpenAI) via the providers abstraction.
"""

from __future__ import annotations

import json
import logging
import re

import pydantic

from drift.pipeline.config import MAX_TOKENS, VALIDATION_RANGES
from drift.pipeline.extraction.providers import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMRequestError,
    create_provider,
)
from drift.pipeline.extraction.schemas import (
    ExtractedBCSource,
    ExtractedBullet,
    ExtractedCartridge,
    ExtractedRifleModel,
)

logger = logging.getLogger(__name__)

# ── Extraction prompts per entity type ───────────────────────────────────────

BULLET_SCHEMA = """\
Extract ALL bullet products from this page. For each bullet, extract:

{
  "name": {"value": "string — full product name", "source_text": "exact text from page", "confidence": 0.0-1.0},
  "manufacturer": {"value": "string — company name", "source_text": "...", "confidence": ...},
  "bullet_diameter_inches": {"value": number, "source_text": "...", "confidence": ...},  // Bullet diameter in inches — e.g. 0.264 for 6.5mm, 0.308 for .30 cal, 0.243 for 6mm, 0.284 for 7mm, 0.338 for .338 cal
  "weight_grains": {"value": number, "source_text": "...", "confidence": ...},
  "bc_g1": {"value": number or null, "source_text": "...", "confidence": ...},
  "bc_g7": {"value": number or null, "source_text": "...", "confidence": ...},
  "length_inches": {"value": number or null, "source_text": "...", "confidence": ...},  // BULLET LENGTH ONLY — the projectile's tip-to-base length. Do NOT extract cartridge OAL (overall length) here.
  "sectional_density": {"value": number or null, "source_text": "...", "confidence": ...},
  "base_type": {"value": "one of: boat_tail, flat_base, rebated_boat_tail, hybrid — or null", "source_text": "...", "confidence": ...},
  "tip_type": {"value": "one of: polymer_tip, hollow_point, open_tip_match, fmj, soft_point, ballistic_tip, meplat — or null", "source_text": "...", "confidence": ...},
  "type_tags": {"value": ["list of: match, hunting, target, varmint, long_range, tactical, plinking"], "source_text": "...", "confidence": ...},
  "used_for": {"value": ["list of: competition, hunting_deer, hunting_elk, hunting_varmint, long_range, precision, self_defense, plinking"], "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null — manufacturer part number", "source_text": "...", "confidence": ...}
}

IMPORTANT: "length_inches" is the BULLET (projectile) length — the physical tip-to-base measurement of \
the projectile itself, typically 0.5–1.8 inches. Do NOT confuse this with cartridge OAL (overall length), \
which is the full assembled round length (bullet seated in the case) and is typically 2.0–3.7 inches. \
If the page only lists OAL/COAL and not the standalone bullet length, set length_inches to null.

Return a JSON array of extracted bullets. If a field is not found on the page, set value to null with confidence 0.0.
"""

CARTRIDGE_SCHEMA = """\
Extract ALL factory-loaded cartridge/ammunition products from this page. For each cartridge, extract:

{
  "name": {"value": "string — full product name", "source_text": "...", "confidence": ...},
  "manufacturer": {"value": "string", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — e.g. '6.5 Creedmoor'", "source_text": "...", "confidence": ...},
  "bullet_name": {"value": "string — name of the bullet used", "source_text": "...", "confidence": ...},
  "bullet_weight_grains": {"value": number, "source_text": "...", "confidence": ...},
  "muzzle_velocity_fps": {"value": integer, "source_text": "...", "confidence": ...},
  "test_barrel_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "round_count": {"value": integer or null — rounds per box, "source_text": "...", "confidence": ...},
  "product_line": {"value": "string or null — e.g. 'Precision Hunter', 'Match'", "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null", "source_text": "...", "confidence": ...}
}

Return a JSON array of extracted cartridges. If a field is not found on the page, set value to null with confidence 0.0.
"""

RIFLE_SCHEMA = """\
Extract ALL rifle model products from this page. For each rifle, extract:

{
  "model": {"value": "string — model name", "source_text": "...", "confidence": ...},
  "manufacturer": {"value": "string", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — chambered caliber", "source_text": "...", "confidence": ...},
  "barrel_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "twist_rate": {"value": "string or null — e.g. '1:8'", "source_text": "...", "confidence": ...},
  "weight_lbs": {"value": number or null, "source_text": "...", "confidence": ...},
  "barrel_material": {"value": "string or null — e.g. 'stainless steel', 'carbon fiber'", "source_text": "...", "confidence": ...},
  "barrel_finish": {"value": "string or null", "source_text": "...", "confidence": ...},
  "model_family": {"value": "string or null — e.g. 'Tikka T3x', 'Ruger Precision'", "source_text": "...", "confidence": ...}
}

Return a JSON array of extracted rifle models. If a field is not found on the page, set value to null with confidence 0.0.
"""

SCHEMAS = {
    "bullet": BULLET_SCHEMA,
    "cartridge": CARTRIDGE_SCHEMA,
    "rifle": RIFLE_SCHEMA,
}

SYSTEM_PROMPT = """\
You are a firearms and ammunition data extraction specialist. Your job is to extract \
structured product data from manufacturer web pages.

Rules:
1. ONLY extract data that is explicitly present on the page. Never guess or infer values.
2. For every extracted field, include "source_text" — the exact snippet from the HTML that supports this value.
3. Set "confidence" between 0.0 and 1.0: 1.0 = explicitly stated, 0.7-0.9 = clearly implied, below 0.7 = uncertain.
4. If a value is not on the page, set it to null with confidence 0.0 and source_text "".
5. Numeric validation ranges:
   - BC (G1/G7): 0.05 to 1.2
   - Muzzle velocity: 400 to 4000 fps
   - Bullet weight: 15 to 750 grains
   - Barrel length: 10 to 34 inches
   - Sectional density: 0.05 to 0.500
   - Bullet diameter: 0.172 to 0.510 inches
   - Bullet length (projectile only, NOT cartridge OAL): 0.2 to 3.0 inches
   - Rifle weight: 2 to 20 lbs
   Flag any values outside these ranges by setting confidence to 0.3 or lower.
6. Return valid JSON only — no markdown fencing, no commentary outside the JSON.
7. CRITICAL DISTINCTION — "bullet length" vs "cartridge OAL":
   - Bullet length (length_inches) = the projectile's tip-to-base measurement, typically 0.5–1.8".
   - Cartridge OAL/COAL = the full assembled round from case head to bullet tip, typically 2.0–3.7".
   These are different measurements. Only extract the projectile length into length_inches. If a page \
only lists OAL/COAL, do NOT use that value for length_inches.
"""


def _parse_json_response(raw_text: str) -> list[dict]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        if match:
            result = json.loads(match.group(1))
        else:
            raise
    if not isinstance(result, list):
        result = [result]
    return result


def validate_ranges(entities: list[dict]) -> list[str]:
    """Check extracted numeric values against known ranges. Returns list of warnings."""
    warnings = []
    for i, entity in enumerate(entities):
        for field, (lo, hi) in VALIDATION_RANGES.items():
            if field not in entity:
                continue
            extracted = entity[field]
            val = extracted.get("value") if isinstance(extracted, dict) else extracted
            if val is None:
                continue
            try:
                num = float(val)
            except (ValueError, TypeError):
                continue
            if num < lo or num > hi:
                name = entity.get("name", {})
                name_val = name.get("value", f"entity[{i}]") if isinstance(name, dict) else name
                warnings.append(f"{name_val}: {field}={num} outside range [{lo}, {hi}]")
    return warnings


def _extract_bc_sources(entity: dict) -> list[ExtractedBCSource]:
    """Extract ExtractedBCSource entries from a bullet entity's BC fields."""
    sources = []
    name = entity.get("name", {})
    bullet_name = name.get("value", "") if isinstance(name, dict) else str(name)

    for bc_field, bc_type in [("bc_g1", "g1"), ("bc_g7", "g7")]:
        if bc_field not in entity:
            continue
        extracted = entity[bc_field]
        val = extracted.get("value") if isinstance(extracted, dict) else extracted
        if val is None:
            continue
        try:
            bc_val = float(val)
        except (ValueError, TypeError):
            logger.warning("Unparseable BC value for %s.%s: %r", bullet_name, bc_field, val)
            continue
        sources.append(
            ExtractedBCSource(
                bullet_name=bullet_name,
                bc_type=bc_type,
                bc_value=bc_val,
                source="manufacturer",
            )
        )
    return sources


EntityType = ExtractedBullet | ExtractedCartridge | ExtractedRifleModel

_SCHEMA_MAP: dict[str, type[EntityType]] = {
    "bullet": ExtractedBullet,
    "cartridge": ExtractedCartridge,
    "rifle": ExtractedRifleModel,
}


class ExtractionResult:
    """Result of extracting entities from a single page."""

    def __init__(
        self,
        entities: list[EntityType],
        raw_entities: list[dict],
        bc_sources: list[ExtractedBCSource],
        warnings: list[str],
        model: str,
        usage: dict,
    ):
        self.entities = entities
        self.raw_entities = raw_entities
        self.bc_sources = bc_sources
        self.warnings = warnings
        self.model = model
        self.usage = usage


class ExtractionEngine:
    """Sends reduced HTML to an LLM and parses structured product data."""

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        model: str | None = None,
    ):
        if provider is None:
            provider = create_provider("anthropic")
        self._provider = provider
        self._model = model or provider.default_model

    def extract(self, reduced_html: str, entity_type: str) -> ExtractionResult:
        """Extract entities from reduced HTML.

        Args:
            reduced_html: HTML that has been through the reducer.
            entity_type: One of "bullet", "cartridge", "rifle".

        Returns:
            ExtractionResult with parsed entities, BC sources, and validation warnings.
        """
        if entity_type not in SCHEMAS:
            raise ValueError(f"Unknown entity_type: {entity_type!r}. Must be one of {list(SCHEMAS.keys())}")

        schema = SCHEMAS[entity_type]
        user_prompt = f"{schema}\n\nHere is the HTML content to extract from:\n\n{reduced_html}"

        logger.info("Extracting %s entities with %s (%d chars input)", entity_type, self._model, len(reduced_html))

        try:
            llm_response = self._provider.complete(
                system=SYSTEM_PROMPT,
                user_message=user_prompt,
                model=self._model,
                max_tokens=MAX_TOKENS,
            )
        except LLMAuthenticationError:
            raise
        except LLMRequestError as e:
            raise ValueError(
                f"LLM request failed for {entity_type} extraction " f"({len(reduced_html)} chars input): {e}"
            ) from e

        raw_text = llm_response.text
        usage = {
            "input_tokens": llm_response.input_tokens,
            "output_tokens": llm_response.output_tokens,
        }

        logger.info(
            "Response: %d chars, %d input / %d output tokens",
            len(raw_text),
            usage["input_tokens"],
            usage["output_tokens"],
        )

        # Parse JSON
        raw_entities = _parse_json_response(raw_text)

        # Validate ranges
        warnings = validate_ranges(raw_entities)
        if warnings:
            logger.warning("Range warnings: %s", warnings)

        # Parse into Pydantic models
        pydantic_class = _SCHEMA_MAP[entity_type]
        entities: list[EntityType] = []
        for raw in raw_entities:
            try:
                entities.append(pydantic_class.model_validate(raw))
            except pydantic.ValidationError as e:
                logger.warning("Failed to parse %s entity: %s", entity_type, e)
                warnings.append(f"Parse error: {e}")

        # Extract BC sources for bullets
        bc_sources: list[ExtractedBCSource] = []
        if entity_type == "bullet":
            for raw in raw_entities:
                bc_sources.extend(_extract_bc_sources(raw))

        return ExtractionResult(
            entities=entities,
            raw_entities=raw_entities,
            bc_sources=bc_sources,
            warnings=warnings,
            model=self._model,
            usage=usage,
        )
