"""Shared deterministic entity resolution — single source of truth for name lookups.

Both the YAML curation patches (`drift.curation`) and the pipeline resolver
(`drift.pipeline.resolution.resolver`) call into this module so they cannot
disagree on what a given name means.
"""

from drift.resolution.aliases import LookupResult, lookup_entity

__all__ = ["LookupResult", "lookup_entity"]
