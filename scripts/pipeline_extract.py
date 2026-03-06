"""Extract structured product data from reduced HTML via LLM.

Supports three modes:
  --batch (default for Anthropic): Submit all pending items as a single batch via
      the Anthropic Message Batches API. Does not count against standard API rate
      limits. 50% cheaper than synchronous calls.
  --sync: Process items one at a time with retry logic. Required for OpenAI.
  --poll BATCH_ID: Resume polling/collecting a previously submitted batch.

Usage:
    python scripts/pipeline_extract.py                        # batch mode (default)
    python scripts/pipeline_extract.py --sync                 # sequential with retries
    python scripts/pipeline_extract.py --sync --provider openai
    python scripts/pipeline_extract.py --poll msgbatch_abc123 # resume a batch
    python scripts/pipeline_extract.py --batch --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from drift.pipeline.config import (
    BATCH_DIR,
    EXTRACTED_DIR,
    MANIFEST_PATH,
    REDUCED_DIR,
    REVIEW_DIR,
)
from drift.pipeline.extraction.engine import ExtractionEngine
from drift.pipeline.extraction.providers import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    create_provider,
)
from drift.pipeline.utils import url_hash

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _url_hash_from_manifest(manifest: list[dict]) -> dict[str, dict]:
    """Build a lookup from url_hash -> manifest entry."""
    return {url_hash(entry["url"]): entry for entry in manifest}


def _infer_provider_from_model(model: str | None) -> str | None:
    """Infer provider from model name if possible."""
    if not model:
        return None
    model_lower = model.lower()
    if any(prefix in model_lower for prefix in ["gpt-", "o1-", "o3-"]):
        return "openai"
    if any(prefix in model_lower for prefix in ["claude-", "haiku-", "sonnet-", "opus-"]):
        return "anthropic"
    return None


def _load_pending_items(  # noqa: C901
    manifest_path: Path,
    limit: int,
    reextract: bool,
) -> tuple[list[dict], dict[str, dict]]:
    """Scan reduced files and return pending items that need extraction.

    Returns:
        Tuple of (pending_items, hash_lookup) where pending_items is a list of dicts
        with keys: url_hash, url, entity_type, reduced_html_path.
    """
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}\nRun pipeline_fetch.py first.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hash_lookup = _url_hash_from_manifest(manifest)

    reduced_files = sorted(REDUCED_DIR.glob("*.json"))
    if not reduced_files:
        raise SystemExit(f"No reduced files found in {REDUCED_DIR}\nRun pipeline_fetch.py first.")

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    entries = reduced_files[:limit] if limit > 0 else reduced_files
    pending = []

    for reduced_json_path in entries:
        uhash = reduced_json_path.stem

        # Check cache — re-extract if previous run returned 0 entities
        extracted_cache = EXTRACTED_DIR / f"{uhash}.json"
        if extracted_cache.exists() and not reextract:
            try:
                cached = json.loads(extracted_cache.read_text(encoding="utf-8"))
                if cached.get("entity_count", 0) == 0:
                    logger.info("Re-extracting %s (previous run returned 0 entities)", uhash)
                else:
                    continue
            except (json.JSONDecodeError, KeyError):
                continue

        # Load metadata
        reduced_meta = json.loads(reduced_json_path.read_text(encoding="utf-8"))
        url = reduced_meta.get("url", uhash)
        entity_type = reduced_meta.get("entity_type")

        if not entity_type:
            manifest_entry = hash_lookup.get(uhash, {})
            entity_type = manifest_entry.get("entity_type")

        if not entity_type:
            logger.warning("SKIP (no entity_type): %s", url)
            continue

        reduced_html_path = REDUCED_DIR / f"{uhash}.html"
        if not reduced_html_path.exists():
            logger.warning("SKIP (no reduced HTML): %s", url)
            continue

        pending.append(
            {
                "url_hash": uhash,
                "url": url,
                "entity_type": entity_type,
                "reduced_html_path": str(reduced_html_path),
            }
        )

    return pending, hash_lookup


def _save_extraction(uhash: str, url: str, entity_type: str, result, flagged_items: list[dict]) -> None:
    """Save an extraction result to the cache and flag if needed."""
    extraction_data = {
        "url": url,
        "url_hash": uhash,
        "entity_type": entity_type,
        "model": result.model,
        "usage": result.usage,
        "entity_count": len(result.entities),
        "entities": result.raw_entities,
        "bc_sources": [bc.model_dump() for bc in result.bc_sources],
        "warnings": result.warnings,
    }

    extracted_cache = EXTRACTED_DIR / f"{uhash}.json"
    extracted_cache.write_text(json.dumps(extraction_data, indent=2), encoding="utf-8")

    if len(result.entities) == 0:
        logger.warning("Saved 0-entity extraction for %s (%s) — will be re-extracted on next run", uhash, url)

    if result.warnings:
        flagged_items.append(
            {
                "url": url,
                "url_hash": uhash,
                "entity_type": entity_type,
                "reason": "validation_warnings",
                "warnings": result.warnings,
            }
        )


def _write_flagged(flagged_items: list[dict]) -> Path | None:
    """Merge flagged items with existing flagged file."""
    if not flagged_items:
        return None

    flagged_path = REVIEW_DIR / "flagged.json"
    existing_flagged: list[dict] = []
    if flagged_path.exists():
        try:
            existing_flagged = json.loads(flagged_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            backup_path = flagged_path.with_suffix(".json.bak")
            logger.warning("Corrupt flagged file at %s — backing up to %s", flagged_path, backup_path)
            import shutil

            shutil.copy2(flagged_path, backup_path)

    existing_hashes = {f["url_hash"] for f in existing_flagged}
    for item in flagged_items:
        if item["url_hash"] not in existing_hashes:
            existing_flagged.append(item)

    flagged_path.write_text(json.dumps(existing_flagged, indent=2), encoding="utf-8")
    return flagged_path


# ── Sync mode ───────────────────────────────────────────────────────────────


def _run_sync(args: argparse.Namespace, provider_name: str) -> None:
    """Sequential extraction with retry logic."""
    pending, _ = _load_pending_items(args.manifest, args.limit, args.reextract)

    total = len(pending)
    reduced_files = sorted(REDUCED_DIR.glob("*.json"))
    all_count = min(len(reduced_files), args.limit) if args.limit > 0 else len(reduced_files)
    skipped = all_count - total

    if total == 0:
        print(f"Nothing to extract ({skipped} cached).")
        return

    logger.info("%d items to extract, %d cached", total, skipped)

    provider = create_provider(provider_name)
    engine = ExtractionEngine(provider=provider, model=args.model)

    stats = {"extracted": 0, "failed": 0, "flagged": 0}
    flagged_items: list[dict] = []
    consecutive_failures = 0
    max_consecutive_failures = 3

    for i, item in enumerate(pending):
        uhash = item["url_hash"]
        url = item["url"]
        entity_type = item["entity_type"]
        reduced_html = Path(item["reduced_html_path"]).read_text(encoding="utf-8")

        logger.info("[%d/%d] EXTRACT (%s): %s", i + 1, total, entity_type, url)

        try:
            result = engine.extract(reduced_html, entity_type)
            _save_extraction(uhash, url, entity_type, result, flagged_items)

            logger.info(
                "  %d entities, %d BC sources, %d warnings, %d input / %d output tokens",
                len(result.entities),
                len(result.bc_sources),
                len(result.warnings),
                result.usage.get("input_tokens", 0),
                result.usage.get("output_tokens", 0),
            )

            if result.warnings:
                stats["flagged"] += 1
                logger.warning("  FLAGGED: %s", result.warnings)

            stats["extracted"] += 1
            consecutive_failures = 0

        except LLMAuthenticationError as e:
            logger.error("  Authentication failed — aborting: %s", e)
            raise SystemExit(1) from e
        except LLMRateLimitError as e:
            logger.error("  Rate limit exhausted after retries — aborting remaining items: %s", e)
            stats["failed"] += 1
            break
        except (LLMProviderError, json.JSONDecodeError) as e:
            logger.exception("  FAILED: %s — %s", url, e)
            stats["failed"] += 1
            consecutive_failures += 1
        except Exception:
            logger.exception("  UNEXPECTED FAILURE: %s", url)
            stats["failed"] += 1
            consecutive_failures += 1

        if consecutive_failures >= max_consecutive_failures:
            logger.error(
                "Aborting: %d consecutive failures — likely a systemic issue",
                consecutive_failures,
            )
            break

    flagged_path = _write_flagged(flagged_items)

    print()
    print(
        f"Done: {stats['extracted']} extracted, {skipped} skipped, "
        f"{stats['failed']} failed, {stats['flagged']} flagged "
        f"(of {skipped + total} total)"
    )
    if flagged_path:
        print(f"Flagged items written to: {flagged_path}")


# ── Batch mode ──────────────────────────────────────────────────────────────


def _run_batch(args: argparse.Namespace) -> None:
    """Batch extraction via Anthropic Message Batches API."""
    from drift.pipeline.extraction.batch import BatchExtractor, BatchItem
    from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

    pending, _ = _load_pending_items(args.manifest, args.limit, args.reextract)

    total = len(pending)
    reduced_files = sorted(REDUCED_DIR.glob("*.json"))
    all_count = min(len(reduced_files), args.limit) if args.limit > 0 else len(reduced_files)
    skipped = all_count - total

    if total == 0:
        print(f"Nothing to extract ({skipped} cached).")
        return

    logger.info("%d items to extract via batch API, %d cached", total, skipped)

    provider = AnthropicProvider()
    engine = ExtractionEngine(provider=provider, model=args.model)
    batch_extractor = BatchExtractor(engine=engine, client=provider.client)

    # Build batch items
    batch_items = []
    item_meta: dict[str, dict] = {}  # url_hash → {url, entity_type}
    for item in pending:
        reduced_html = Path(item["reduced_html_path"]).read_text(encoding="utf-8")
        batch_items.append(
            BatchItem(
                url_hash=item["url_hash"],
                url=item["url"],
                entity_type=item["entity_type"],
                reduced_html=reduced_html,
            )
        )
        item_meta[item["url_hash"]] = {
            "url": item["url"],
            "entity_type": item["entity_type"],
        }

    # Submit and save batch metadata
    batch_id = batch_extractor.submit(batch_items)
    _save_batch_metadata(batch_id, item_meta, engine.model)
    logger.info("Batch metadata saved. You can resume with: --poll %s", batch_id)

    # Poll and collect
    try:
        batch_extractor.poll(batch_id)
    except TimeoutError:
        logger.error("Batch %s did not complete within timeout.", batch_id)
        print(f"\nBatch timed out. Resume later with:\n  python scripts/pipeline_extract.py --poll {batch_id}")
        return

    item_types = {uhash: meta["entity_type"] for uhash, meta in item_meta.items()}
    results = batch_extractor.collect(batch_id, item_types)

    # Save results
    flagged_items: list[dict] = []
    stats = _process_batch_results(results, item_meta, flagged_items)
    flagged_path = _write_flagged(flagged_items)

    print()
    print(
        f"Done (batch {batch_id}): {stats['succeeded']} extracted, {skipped} skipped, "
        f"{stats['errored']} errored, {stats['flagged']} flagged "
        f"(of {skipped + total} total)"
    )
    if flagged_path:
        print(f"Flagged items written to: {flagged_path}")


def _run_poll(args: argparse.Namespace) -> None:
    """Resume polling/collecting a previously submitted batch."""
    from drift.pipeline.extraction.batch import BatchExtractor
    from drift.pipeline.extraction.providers.anthropic_provider import AnthropicProvider

    batch_id = args.poll

    # Load batch metadata
    meta_path = BATCH_DIR / f"{batch_id}.json"
    if not meta_path.exists():
        raise SystemExit(
            f"No batch metadata found at {meta_path}\n"
            f"This batch may have been submitted from a different machine or the metadata was deleted."
        )

    batch_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    item_meta = batch_meta["items"]
    model = batch_meta.get("model")

    logger.info("Resuming batch %s (%d items, model: %s)", batch_id, len(item_meta), model)

    provider = AnthropicProvider()
    engine = ExtractionEngine(provider=provider, model=model)
    batch_extractor = BatchExtractor(engine=engine, client=provider.client)

    # Poll
    try:
        batch_extractor.poll(batch_id)
    except TimeoutError:
        logger.error("Batch %s did not complete within timeout.", batch_id)
        print(f"\nBatch timed out. Resume later with:\n  python scripts/pipeline_extract.py --poll {batch_id}")
        return

    # Collect
    item_types = {uhash: meta["entity_type"] for uhash, meta in item_meta.items()}
    results = batch_extractor.collect(batch_id, item_types)

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    flagged_items: list[dict] = []
    stats = _process_batch_results(results, item_meta, flagged_items)
    flagged_path = _write_flagged(flagged_items)

    print()
    print(
        f"Done (batch {batch_id}): {stats['succeeded']} extracted, "
        f"{stats['errored']} errored, {stats['flagged']} flagged"
    )
    if flagged_path:
        print(f"Flagged items written to: {flagged_path}")


def _process_batch_results(
    results: dict,
    item_meta: dict[str, dict],
    flagged_items: list[dict],
) -> dict[str, int]:
    """Process batch results: save extractions, collect stats. Shared by _run_batch and _run_poll."""
    stats = {"succeeded": 0, "errored": 0, "flagged": 0}

    for uhash, result_item in results.items():
        meta = item_meta.get(uhash, {})
        url = meta.get("url", uhash)
        entity_type = meta.get("entity_type")
        if not entity_type:
            logger.error("Missing entity_type in metadata for %s — marking as errored", uhash)
            stats["errored"] += 1
            continue

        if result_item.status == "succeeded" and result_item.result is not None:
            _save_extraction(uhash, url, entity_type, result_item.result, flagged_items)
            stats["succeeded"] += 1
            if result_item.result.warnings:
                stats["flagged"] += 1
        else:
            logger.warning("  %s: %s — %s", uhash, result_item.status, result_item.error)
            stats["errored"] += 1

    return stats


def _save_batch_metadata(batch_id: str, item_meta: dict[str, dict], model: str) -> None:
    """Save batch metadata so we can resume polling later."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = BATCH_DIR / f"{batch_id}.json"
    meta_path.write_text(
        json.dumps({"batch_id": batch_id, "model": model, "items": item_meta}, indent=2),
        encoding="utf-8",
    )


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract product data from reduced HTML")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="URL manifest JSON path")
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["anthropic", "openai"],
        help="LLM provider (auto-detected from model if not specified)",
    )
    parser.add_argument("--model", type=str, default=None, help="LLM model to use")
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to process (0 = all)")
    parser.add_argument("--reextract", action="store_true", help="Re-extract even if cached")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--batch", action="store_true", help="Use Anthropic batch API (default for Anthropic)")
    mode.add_argument("--sync", action="store_true", help="Sequential extraction with retries")
    mode.add_argument("--poll", type=str, metavar="BATCH_ID", help="Resume polling a submitted batch")

    args = parser.parse_args()

    # Handle --poll mode
    if args.poll:
        _run_poll(args)
        return

    # Determine provider
    provider_name = args.provider
    if not provider_name and args.model:
        provider_name = _infer_provider_from_model(args.model)
        if provider_name:
            logger.info("Auto-detected provider '%s' from model '%s'", provider_name, args.model)
    if not provider_name:
        provider_name = "anthropic"

    # Determine mode: explicit flags take priority, otherwise auto-select
    if args.sync:
        _run_sync(args, provider_name)
    elif args.batch:
        if provider_name != "anthropic":
            raise SystemExit("Batch mode is only supported with Anthropic provider.")
        _run_batch(args)
    else:
        # Auto-select: batch for Anthropic, sync for everything else
        if provider_name == "anthropic":
            logger.info("Auto-selecting batch mode (use --sync to force sequential)")
            _run_batch(args)
        else:
            _run_sync(args, provider_name)


if __name__ == "__main__":
    main()
