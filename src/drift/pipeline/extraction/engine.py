# flake8: noqa: E501 B950 — prompt strings are intentionally long
"""LLM extraction engine — sends reduced HTML to an LLM and parses structured product data.

Uses Claude Haiku as the default model (validated across 5 manufacturer sites in spike).
Supports multiple LLM providers (Anthropic, OpenAI) via the providers abstraction.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from urllib.parse import urlparse

import pydantic

from drift.pipeline.config import MAX_TOKENS, SYNC_MAX_RETRIES, SYNC_RETRY_BASE_SECONDS, VALIDATION_RANGES
from drift.pipeline.extraction.providers import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
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
  "product_line": {"value": "string or null — the bullet's product family name", "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null — manufacturer part number", "source_text": "...", "confidence": ...}
}

IMPORTANT: "length_inches" is the BULLET (projectile) length — the physical tip-to-base measurement of \
the projectile itself, typically 0.5–1.8 inches. Do NOT confuse this with cartridge OAL (overall length), \
which is the full assembled round length (bullet seated in the case) and is typically 2.0–3.7 inches. \
If the page only lists OAL/COAL and not the standalone bullet length, set length_inches to null.

PRODUCT LINE EXTRACTION:
"product_line" is the bullet's branded product family name — the marketing name that identifies the bullet \
design across all calibers and weights. Extract it as a short, clean string without trademark symbols.
Examples:
  "30 Cal .308 178 gr ELD-X®" → product_line: "ELD-X"
  "6.5MM 140 GR HPBT MatchKing (SMK)" → product_line: "MatchKing"
  "0.308 30 CAL TSX BT 168 GR" → product_line: "TSX"
  "Fusion Component Bullet, .308, 180 Grain" → product_line: "Fusion"
  "338 Caliber 225gr Partition (50ct)" → product_line: "Partition"
  "30 Caliber 185 Grain Hybrid Target Rifle Bullet" → product_line: "Hybrid Target"
  "22 Cal .224 55 gr SP Boattail with Cannelure" → product_line: null (generic, no named family)
  "55 GR FMJ Boat Tail" → product_line: null (generic type, not a product family)
Set null for generic bullets described only by their type (SP, FMJ, HP, HPBT, etc.) with no branded family name.

Return a JSON array of extracted bullets. If a field is not found on the page, set value to null with confidence 0.0.
"""

CARTRIDGE_SCHEMA = """\
Extract ALL factory-loaded cartridge/ammunition products from this page. For each cartridge, extract:

{
  "name": {"value": "string — full product name", "source_text": "...", "confidence": ...},
  "manufacturer": {"value": "string", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — e.g. '6.5 Creedmoor'", "source_text": "...", "confidence": ...},
  "bullet_name": {"value": "string — the bullet's product family name", "source_text": "...", "confidence": ...},
  "bullet_weight_grains": {"value": number, "source_text": "...", "confidence": ...},
  "bc_g1": {"value": number or null, "source_text": "...", "confidence": ...},
  "bc_g7": {"value": number or null, "source_text": "...", "confidence": ...},
  "bullet_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},  // BULLET LENGTH ONLY — the projectile's tip-to-base length. Do NOT extract cartridge OAL (overall length) here.
  "muzzle_velocity_fps": {"value": integer, "source_text": "...", "confidence": ...},
  "test_barrel_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "round_count": {"value": integer or null — rounds per box, "source_text": "...", "confidence": ...},
  "product_line": {"value": "string or null — the ammo product line, e.g. 'Precision Hunter', 'Gold Medal'", "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null", "source_text": "...", "confidence": ...}
}

IMPORTANT: "bullet_length_inches" is the BULLET (projectile) length — the physical tip-to-base measurement of \
the projectile itself, typically 0.5–1.8 inches. Do NOT confuse this with cartridge OAL (overall length), \
which is the full assembled round length (bullet seated in the case) and is typically 2.0–3.7 inches. \
If the page only lists OAL/COAL and not the standalone bullet length, set bullet_length_inches to null.

BULLET NAME EXTRACTION:
"bullet_name" is the bullet's product family name — the short branded name that identifies the projectile design. \
Extract it as a clean, short string without trademark symbols (no ®, ™). Do NOT include caliber, weight, \
manufacturer prefixes, or verbose descriptions — just the product family name.
Examples:
  Page says "ELD-X®" → bullet_name: "ELD-X"
  Page says "SST® (Super Shock Tip)" → bullet_name: "SST"
  Page says "Barnes Triple-Shock X Bullet (TSX)" → bullet_name: "TSX"
  Page says "Sierra MatchKing BTHP" → bullet_name: "MatchKing"
  Page says "Fusion Soft Point" → bullet_name: "Fusion"
  Page says "Nosler Partition" → bullet_name: "Partition"
  Page says "Jacketed Soft Point" → bullet_name: "Jacketed Soft Point" (generic, no product family — keep as-is)
Note: "product_line" is the AMMO line (e.g. "Precision Hunter"), "bullet_name" is the BULLET family (e.g. "ELD-X"). \
These are different fields — a Hornady Precision Hunter cartridge uses an ELD-X bullet.

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
7. Keep "source_text" short (under 80 chars). Use plain text only — never copy raw JSON, HTML tags, \
   or structured markup into source_text. If the supporting text is longer, truncate with "...".
8. CRITICAL DISTINCTION — "bullet length" vs "cartridge OAL":
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


def _extract_bc_sources(entity: dict, *, entity_type: str = "bullet") -> list[ExtractedBCSource]:
    """Extract ExtractedBCSource entries from a bullet or cartridge entity's BC fields.

    For bullet entities, uses the entity's ``name`` as the bullet_name and sets
    source to ``"manufacturer"``.
    For cartridge entities, prefers ``bullet_name`` (the loaded projectile),
    falling back to the cartridge ``name`` if bullet_name is absent or empty.
    Sets source to ``"cartridge_page"`` to distinguish from the bullet's own page.
    """
    sources = []

    # Determine the bullet name to attribute the BC to
    if entity_type == "cartridge":
        bn = entity.get("bullet_name", {})
        bullet_name = bn.get("value", "") if isinstance(bn, dict) else str(bn) if bn else ""
        # Fall back to cartridge name if bullet_name is empty
        if not bullet_name:
            n = entity.get("name", {})
            bullet_name = n.get("value", "") if isinstance(n, dict) else str(n)
        if not bullet_name:
            logger.warning("Cartridge entity has BC data but no bullet_name or name — skipping BC source extraction")
            return sources
        source = "cartridge_page"
    else:
        n = entity.get("name", {})
        bullet_name = n.get("value", "") if isinstance(n, dict) else str(n)
        source = "manufacturer"

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
                source=source,
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
    """Result of extracting entities from a single page.

    ``extraction_method`` records which path produced the result:
    ``"parser"`` — deterministic parser succeeded; ``usage`` is zero.
    ``"parser_fellthrough_to_llm"`` — a parser applied but couldn't handle
    the page; the LLM ran and produced this result.
    ``"llm"`` — no parser was registered/applicable for the domain.
    """

    def __init__(
        self,
        entities: list[EntityType],
        raw_entities: list[dict],
        bc_sources: list[ExtractedBCSource],
        warnings: list[str],
        model: str,
        usage: dict,
        extraction_method: str = "llm",
        parser_name: str | None = None,
    ):
        self.entities = entities
        self.raw_entities = raw_entities
        self.bc_sources = bc_sources
        self.warnings = warnings
        self.model = model
        self.usage = usage
        self.extraction_method = extraction_method
        self.parser_name = parser_name


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

    def build_messages(self, reduced_html: str, entity_type: str) -> tuple[str, str]:
        """Build the (system_prompt, user_message) pair for a given extraction.

        Args:
            reduced_html: HTML that has been through the reducer.
            entity_type: One of "bullet", "cartridge", "rifle".

        Returns:
            Tuple of (system_prompt, user_message).
        """
        if entity_type not in SCHEMAS:
            raise ValueError(f"Unknown entity_type: {entity_type!r}. Must be one of {list(SCHEMAS.keys())}")
        schema = SCHEMAS[entity_type]
        user_message = f"{schema}\n\nHere is the HTML content to extract from:\n\n{reduced_html}"
        return SYSTEM_PROMPT, user_message

    def parse_response(self, raw_text: str, entity_type: str, usage: dict | None = None) -> ExtractionResult:
        """Parse raw LLM response text into an ExtractionResult.

        Args:
            raw_text: The raw JSON text returned by the LLM.
            entity_type: One of "bullet", "cartridge", "rifle".
            usage: Optional dict with "input_tokens" and "output_tokens".

        Returns:
            ExtractionResult with parsed entities, BC sources, and validation warnings.
        """
        if entity_type not in _SCHEMA_MAP:
            raise ValueError(f"Unknown entity_type: {entity_type!r}. Must be one of {list(_SCHEMA_MAP.keys())}")

        raw_entities = _parse_json_response(raw_text)

        warnings = validate_ranges(raw_entities)
        if warnings:
            logger.warning("Range warnings: %s", warnings)

        pydantic_class = _SCHEMA_MAP[entity_type]
        entities: list[EntityType] = []
        for raw in raw_entities:
            try:
                entities.append(pydantic_class.model_validate(raw))
            except pydantic.ValidationError as e:
                logger.warning("Failed to parse %s entity: %s", entity_type, e)
                warnings.append(f"Parse error: {e}")

        bc_sources: list[ExtractedBCSource] = []
        if entity_type in ("bullet", "cartridge"):
            for raw in raw_entities:
                bc_sources.extend(_extract_bc_sources(raw, entity_type=entity_type))

        return ExtractionResult(
            entities=entities,
            raw_entities=raw_entities,
            bc_sources=bc_sources,
            warnings=warnings,
            model=self._model,
            usage=usage or {},
        )

    @property
    def model(self) -> str:
        """The model string this engine uses."""
        return self._model

    def _resolve_parser(self, url: str, entity_type: str):  # -> BaseParser | None
        """Return the registered parser for ``url``'s domain when applicable."""
        from drift.pipeline.extraction.parsers import get_parser_for_domain

        domain = urlparse(url).netloc.lower()
        parser = get_parser_for_domain(domain)
        if parser is None or entity_type not in parser.supported_entity_types:
            return None
        return parser

    def try_parse(
        self,
        url: str,
        entity_type: str,
        raw_html: str | None,
    ) -> ExtractionResult | None:
        """Attempt deterministic parser extraction for ``url``.

        Returns an ExtractionResult (with ``extraction_method="parser"``) when
        a parser is registered for the domain, the parser produces a valid
        result, and all entities pass validation ranges + the Pydantic gate.

        Returns ``None`` in every fallthrough case — no parser registered,
        entity type unsupported, raw HTML missing, parser returned None,
        parser raised, or parser output failed validation. Callers should
        fall through to the LLM path.
        """
        from drift.pipeline.extraction.parsers import ParserError

        parser = self._resolve_parser(url, entity_type)
        if parser is None:
            return None
        if not raw_html:
            logger.debug("Parser %s: no raw HTML available for %s — LLM fallback", parser.name, url)
            return None

        try:
            parser_result = parser.parse(raw_html, url, entity_type)
        except ParserError as e:
            logger.warning("Parser %s raised ParserError on %s: %s — LLM fallback", parser.name, url, e)
            return None
        except Exception:
            logger.exception("Parser %s raised unexpectedly on %s — LLM fallback", parser.name, url)
            return None

        if parser_result is None:
            logger.debug("Parser %s declined %s — LLM fallback", parser.name, url)
            return None

        if entity_type not in _SCHEMA_MAP:
            logger.warning(
                "Parser %s returned result for unknown entity_type %r — LLM fallback", parser.name, entity_type
            )
            return None

        raw_entities = [e.model_dump() for e in parser_result.entities]
        range_warnings = validate_ranges(raw_entities)
        if range_warnings:
            logger.warning(
                "Parser %s produced out-of-range values on %s: %s — LLM fallback",
                parser.name,
                url,
                range_warnings,
            )
            return None

        # Pydantic gate — no-op in the happy case, catches drift if a parser
        # ever returns a dict shape the current schema can't load.
        pydantic_class = _SCHEMA_MAP[entity_type]
        validated: list[EntityType] = []
        for raw in raw_entities:
            try:
                validated.append(pydantic_class.model_validate(raw))
            except pydantic.ValidationError as e:
                logger.warning(
                    "Parser %s produced Pydantic-invalid entity on %s: %s — LLM fallback",
                    parser.name,
                    url,
                    e,
                )
                return None

        return ExtractionResult(
            entities=validated,
            raw_entities=raw_entities,
            bc_sources=list(parser_result.bc_sources),
            warnings=list(parser_result.warnings),
            model=self._model,
            usage={"input_tokens": 0, "output_tokens": 0},
            extraction_method="parser",
            parser_name=parser.name,
        )

    def extract(
        self,
        reduced_html: str,
        entity_type: str,
        *,
        url: str | None = None,
        raw_html: str | None = None,
    ) -> ExtractionResult:
        """Extract entities from reduced HTML (synchronous, single request).

        When ``url`` and ``raw_html`` are both provided, the engine first tries
        a deterministic parser for the URL's domain. On any fallthrough
        condition (no parser, parser returns None, raises, or produces
        invalid output), the LLM path runs exactly as before — the resulting
        ExtractionResult carries ``extraction_method="parser_fellthrough_to_llm"``
        so telemetry can distinguish it from a pure-LLM run.

        Uses exponential backoff on rate limit errors for the LLM path.
        """
        fellthrough_from_parser = False
        if url:
            applicable_parser = self._resolve_parser(url, entity_type) if raw_html else None
            if applicable_parser is not None:
                parser_result = self.try_parse(url, entity_type, raw_html)
                if parser_result is not None:
                    return parser_result
                fellthrough_from_parser = True

        system_prompt, user_message = self.build_messages(reduced_html, entity_type)

        logger.info("Extracting %s entities with %s (%d chars input)", entity_type, self._model, len(reduced_html))

        llm_response = None
        for attempt in range(SYNC_MAX_RETRIES + 1):
            try:
                llm_response = self._provider.complete(
                    system=system_prompt,
                    user_message=user_message,
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                )
                break
            except LLMAuthenticationError:
                raise
            except LLMRateLimitError as e:
                if attempt == SYNC_MAX_RETRIES:
                    raise
                delay = SYNC_RETRY_BASE_SECONDS * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.1fs: %s", attempt + 1, SYNC_MAX_RETRIES, delay, e
                )
                time.sleep(delay)
            except LLMRequestError as e:
                raise ValueError(
                    f"LLM request failed for {entity_type} extraction ({len(reduced_html)} chars input): {e}"
                ) from e
            except LLMProviderError as e:
                if attempt == SYNC_MAX_RETRIES:
                    raise
                delay = SYNC_RETRY_BASE_SECONDS * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Transient error (attempt %d/%d), retrying in %.1fs: %s", attempt + 1, SYNC_MAX_RETRIES, delay, e
                )
                time.sleep(delay)

        if llm_response is None:
            raise RuntimeError("LLM response was None after retry loop — this should not happen")

        usage = {
            "input_tokens": llm_response.input_tokens,
            "output_tokens": llm_response.output_tokens,
            "cache_creation_input_tokens": llm_response.cache_creation_input_tokens,
            "cache_read_input_tokens": llm_response.cache_read_input_tokens,
        }

        logger.info(
            "Response: %d chars, %d input / %d output tokens (cache write=%s, read=%s)",
            len(llm_response.text),
            usage["input_tokens"],
            usage["output_tokens"],
            usage["cache_creation_input_tokens"],
            usage["cache_read_input_tokens"],
        )

        llm_result = self.parse_response(llm_response.text, entity_type, usage=usage)
        if fellthrough_from_parser:
            llm_result.extraction_method = "parser_fellthrough_to_llm"
        return llm_result
