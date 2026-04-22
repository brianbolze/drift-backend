"""Domain → parser lookup.

Mirrors the DOMAIN_REDUCER_STRATEGY pattern: a single-line config flag in
``drift.pipeline.config.DOMAIN_PARSER`` enables a parser for a given domain.
Lazy-import the concrete parser class inside the lookup to avoid circular
imports between the parsers package and the engine.
"""

from __future__ import annotations

from drift.pipeline.config import DOMAIN_PARSER
from drift.pipeline.extraction.parsers.base import BaseParser


def get_parser_for_domain(domain: str) -> BaseParser | None:
    """Return a parser instance for ``domain``, or None if no parser is registered."""
    parser_name = DOMAIN_PARSER.get(domain)
    if not parser_name:
        return None
    return _instantiate(parser_name)


def _instantiate(name: str) -> BaseParser | None:
    """Lazy-import + instantiate a parser by its short name."""
    if name == "hornady":
        from drift.pipeline.extraction.parsers.hornady import HornadyParser

        return HornadyParser()
    if name == "sierra":
        from drift.pipeline.extraction.parsers.sierra import SierraParser

        return SierraParser()
    return None
