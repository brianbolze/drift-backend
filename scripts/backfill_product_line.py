"""Backfill product_line for existing bullets using LLM batch inference.

Reads all bullets without product_line from the database, sends them to an LLM
in batches to derive the product family name, and updates the DB.

Usage:
    python scripts/backfill_product_line.py                  # dry-run
    python scripts/backfill_product_line.py --commit         # write to DB
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Force-load .env (override=True) so empty shell vars don't block it
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from sqlalchemy import select  # noqa: E402

from drift.database import get_session_factory  # noqa: E402
from drift.models.bullet import Bullet  # noqa: E402
from drift.models.manufacturer import Manufacturer  # noqa: E402
from drift.pipeline.extraction.providers import create_provider  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # bullets per LLM call

BACKFILL_PROMPT = """\
For each bullet below, extract the product family name — the branded marketing name that \
identifies the bullet design across calibers and weights. Return ONLY the family name as a \
short string, without trademark symbols (no ®, ™). Return null for generic bullets described \
only by their type (SP, FMJ, HP, HPBT, etc.) with no branded family name.

Examples:
  "30 Cal .308 178 gr ELD-X®" → "ELD-X"
  "6.5MM 140 GR HPBT MatchKing (SMK)" → "MatchKing"
  "0.308 30 CAL TSX BT 168 GR" → "TSX"
  "Fusion Component Bullet, .308, 180 Grain" → "Fusion"
  "338 Caliber 225gr Partition (50ct)" → "Partition"
  "22 Cal .224 55 gr SP Boattail with Cannelure" → null
  "55 GR FMJ Boat Tail" → null
  "30 Caliber 185 Grain Hybrid Target Rifle Bullet" → "Hybrid Target"
  "165 GR CX" → "CX"
  "120 gr GMX" → "GMX"

Return a JSON array with one object per bullet, in the same order as the input:
[{"id": "...", "product_line": "..." or null}, ...]

Bullets:
"""


def _build_batch(bullets: list[tuple[str, str, str]]) -> str:
    """Build the bullet list portion of the prompt."""
    lines = []
    for bullet_id, name, manufacturer in bullets:
        lines.append(f"  {json.dumps({'id': bullet_id, 'name': name, 'manufacturer': manufacturer})}")
    return "\n".join(lines)


def _apply_batch_results(session, batch_tuples, results, commit: bool) -> tuple[int, int]:
    """Apply LLM results for a single batch. Returns (updated, skipped)."""
    updated = skipped = 0
    for (bullet_id, bullet_name, _mfr), result in zip(batch_tuples, results, strict=True):
        if not isinstance(result, dict):
            logger.error("  INVALID RESULT for %s: expected dict, got %s", bullet_name, type(result).__name__)
            skipped += 1
            continue

        # Validate ID matches (guard against LLM reordering)
        result_id = result.get("id")
        if result_id is not None and str(result_id) != bullet_id:
            logger.warning("  ID MISMATCH for %s: expected %s, got %s — skipping", bullet_name, bullet_id, result_id)
            skipped += 1
            continue

        if "product_line" not in result:
            logger.warning("  MALFORMED: %s — result dict missing 'product_line' key", bullet_name)
            skipped += 1
            continue

        pl = result["product_line"]
        if pl is None:
            skipped += 1
            logger.debug("  SKIP (generic): %s", bullet_name)
            continue

        pl = str(pl).strip()
        if not pl:
            skipped += 1
            continue

        bullet = session.get(Bullet, bullet_id)
        if bullet is None:
            logger.warning("  NOT FOUND: bullet_id=%s (%s) — stale session?", bullet_id, bullet_name)
            skipped += 1
        elif bullet.is_locked:
            logger.info("  SKIP (locked): %s -> would set product_line=%r", bullet_name, pl)
            skipped += 1
        else:
            logger.info("  UPDATE: %s -> product_line=%r", bullet_name, pl)
            if commit:
                bullet.product_line = pl
            updated += 1
    return updated, skipped


def _extract_json(text: str) -> str:
    """Strip markdown fences and preamble to get raw JSON."""
    import re

    # Try markdown-fenced JSON first: ```json ... ```
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Find first '[' and last ']' — the JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text.strip()


def _call_llm(provider, prompt: str, model: str) -> list[dict]:
    """Send prompt to LLM and parse JSON response."""
    response = provider.complete(
        system="You are a firearms data specialist. Return valid JSON only, no markdown fences or preamble.",
        user_message=prompt,
        model=model,
        max_tokens=4096,
    )
    return json.loads(_extract_json(response.text))


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Backfill bullet.product_line via LLM")
    parser.add_argument("--commit", action="store_true", help="Write to DB (default is dry-run)")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="LLM model to use")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    logger.info("Running in %s mode with model %s", mode, args.model)

    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        # session.execute (not scalars) — multi-column select from a join, not a single ORM entity
        rows = list(
            session.execute(
                select(Bullet.id, Bullet.name, Manufacturer.name)
                .join(Manufacturer, Bullet.manufacturer_id == Manufacturer.id)
                .where(Bullet.product_line.is_(None))
                .order_by(Manufacturer.name, Bullet.name)
            )
        )
        logger.info("Found %d bullets without product_line", len(rows))

        if not rows:
            return

        provider = create_provider("anthropic")
        updated = skipped = errors = 0
        total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start : batch_start + BATCH_SIZE]
            batch_tuples = [(str(r[0]), str(r[1]), str(r[2])) for r in batch]
            batch_num = batch_start // BATCH_SIZE + 1

            logger.info("Processing batch %d/%d (%d bullets)", batch_num, total_batches, len(batch))

            try:
                results = _call_llm(provider, BACKFILL_PROMPT + _build_batch(batch_tuples), args.model)
            except json.JSONDecodeError as e:
                logger.error("Batch %d returned unparseable JSON: %s", batch_num, e)
                errors += len(batch)
                continue
            except OSError as e:
                logger.error("Batch %d LLM call failed (transient): %s", batch_num, e)
                errors += len(batch)
                continue

            if not isinstance(results, list) or len(results) != len(batch):
                logger.error("Batch %d: expected %d results, got %d", batch_num, len(batch), len(results))
                errors += len(batch)
                continue

            batch_updated, batch_skipped = _apply_batch_results(session, batch_tuples, results, args.commit)
            updated += batch_updated
            skipped += batch_skipped

            if batch_start + BATCH_SIZE < len(rows):
                time.sleep(1)

        if errors > 0 and errors >= len(rows):
            logger.error("All %d bullets failed — aborting without commit", len(rows))
            session.rollback()
            print(f"\nBackfill FAILED ({mode}): all {len(rows)} bullets errored")
            sys.exit(1)

        if args.commit:
            if errors > 0:
                logger.warning("Committing partial results: %d updated, %d errors", updated, errors)
            session.commit()
            logger.info("Committed to database")
        else:
            session.rollback()
            logger.info("Dry-run complete — no changes written")

        print(f"\nBackfill results ({mode}):")
        print(f"  Updated: {updated}")
        print(f"  Skipped (generic/locked): {skipped}")
        print(f"  Errors: {errors}")
        print(f"  Total: {len(rows)}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
