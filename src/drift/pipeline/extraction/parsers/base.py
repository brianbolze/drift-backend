"""Base types for deterministic per-manufacturer parsers."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod

from drift.pipeline.extraction.schemas import (
    ExtractedBCSource,
    ExtractedBullet,
    ExtractedCartridge,
    ExtractedRifleModel,
)

ParsedEntity = ExtractedBullet | ExtractedCartridge | ExtractedRifleModel


class ParserError(Exception):
    """Parser tried to handle the page but hit an unexpected condition.

    Parsers raise this when they identified the page as one they should parse
    but failed partway through (e.g. malformed embedded JSON). The engine
    catches it and falls through to the LLM path.
    """


@dataclasses.dataclass(frozen=True, slots=True)
class ParserResult:
    """Result returned by a parser's ``parse()`` method.

    Mirrors the downstream contract of the LLM extraction path: a list of
    parsed entities, any BC sources attributable to them, and warnings
    accumulated during parsing (non-fatal).
    """

    entities: list[ParsedEntity]
    bc_sources: list[ExtractedBCSource]
    warnings: list[str] = dataclasses.field(default_factory=list)


class BaseParser(ABC):
    """Abstract base for deterministic per-manufacturer parsers.

    Concrete parsers set ``name`` (used for registry lookup + telemetry) and
    ``supported_entity_types`` (subset of {"bullet", "cartridge", "rifle"}).
    """

    name: str = ""
    supported_entity_types: frozenset[str] = frozenset()

    @abstractmethod
    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:
        """Parse entities from raw HTML.

        Returns:
            ParserResult on success (even with empty entities list if the
            page legitimately holds no products).
            ``None`` when the parser cannot confidently handle this page —
            the engine falls through to the LLM path.

        Raises:
            ParserError when the parser recognized the page shape but hit an
            unexpected condition. Callers (the engine) catch this and fall
            through to the LLM path.
        """
