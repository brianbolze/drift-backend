"""Deterministic per-manufacturer parsers.

A parser is a pre-LLM extraction strategy that turns raw HTML into the same
ExtractedBullet / ExtractedCartridge / ExtractedRifleModel objects the LLM
path produces. Parsers are selected by domain via DOMAIN_PARSER in config,
with the LLM as a guaranteed fallback when a parser returns None, raises,
or produces values that fail validation.
"""

from __future__ import annotations

from drift.pipeline.extraction.parsers.base import (
    BaseParser,
    ParsedEntity,
    ParserError,
    ParserResult,
)
from drift.pipeline.extraction.parsers.registry import get_parser_for_domain

__all__ = [
    "BaseParser",
    "ParsedEntity",
    "ParserError",
    "ParserResult",
    "get_parser_for_domain",
]
