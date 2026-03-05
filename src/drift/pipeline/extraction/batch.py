# flake8: noqa: E501 — log format strings are intentionally long
"""Batch extraction via the Anthropic Message Batches API.

Submits all pending extraction requests as a single batch for server-side
processing. No rate limits, 50% cheaper than synchronous API calls, and
typically completes in minutes.

Usage:
    from drift.pipeline.extraction.batch import BatchExtractor, BatchItem
    extractor = BatchExtractor(engine=engine, client=anthropic_client)
    results = extractor.run(items)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from drift.pipeline.config import BATCH_MAX_WAIT_SECONDS, BATCH_POLL_INTERVAL_SECONDS, MAX_TOKENS
from drift.pipeline.extraction.engine import ExtractionEngine, ExtractionResult

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class BatchItem:
    """A single item to be extracted in a batch."""

    url_hash: str
    url: str
    entity_type: str
    reduced_html: str


@dataclasses.dataclass(slots=True)
class BatchResultItem:
    """Result for a single item in a batch."""

    url_hash: str
    status: str  # "succeeded" | "errored" | "expired" | "canceled"
    result: ExtractionResult | None = None
    error: str | None = None
    usage: dict | None = None


class BatchExtractor:
    """Orchestrates batch extraction using the Anthropic Message Batches API."""

    def __init__(self, engine: ExtractionEngine, client: anthropic.Anthropic):
        self._engine = engine
        self._client = client

    def submit(self, items: list[BatchItem]) -> str:
        """Submit a batch of extraction requests.

        Args:
            items: List of BatchItems to extract.

        Returns:
            The batch ID string for polling/collecting results.
        """
        requests = []
        for item in items:
            system_prompt, user_message = self._engine.build_messages(item.reduced_html, item.entity_type)
            requests.append(
                Request(
                    custom_id=item.url_hash,
                    params=MessageCreateParamsNonStreaming(
                        model=self._engine.model,
                        max_tokens=MAX_TOKENS,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_message}],
                    ),
                )
            )

        logger.info("Submitting batch of %d extraction requests...", len(requests))
        batch = self._client.messages.batches.create(requests=requests)
        logger.info("Batch created: %s (status: %s)", batch.id, batch.processing_status)
        return batch.id

    def poll(
        self,
        batch_id: str,
        timeout: float = BATCH_MAX_WAIT_SECONDS,
        interval: float = BATCH_POLL_INTERVAL_SECONDS,
    ) -> dict:
        """Poll until the batch completes or timeout is reached.

        Args:
            batch_id: The batch ID to poll.
            timeout: Max seconds to wait (default: BATCH_MAX_WAIT_SECONDS).
            interval: Seconds between polls (default: BATCH_POLL_INTERVAL_SECONDS).

        Returns:
            Dict with final batch status info.

        Raises:
            TimeoutError: If the batch doesn't complete within the timeout.
        """
        start = time.monotonic()
        last_log = ""

        while True:
            batch = self._client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts

            status_line = (
                f"succeeded={counts.succeeded} processing={counts.processing} "
                f"errored={counts.errored} expired={counts.expired} "
                f"canceled={counts.canceled}"
            )

            if status_line != last_log:
                logger.info("Batch %s: %s [%s]", batch_id, batch.processing_status, status_line)
                last_log = status_line

            if batch.processing_status == "ended":
                logger.info("Batch %s completed.", batch_id)
                return {
                    "batch_id": batch_id,
                    "status": batch.processing_status,
                    "succeeded": counts.succeeded,
                    "errored": counts.errored,
                    "expired": counts.expired,
                    "canceled": counts.canceled,
                }

            elapsed = time.monotonic() - start
            if elapsed + interval > timeout:
                raise TimeoutError(
                    f"Batch {batch_id} did not complete within {timeout}s "
                    f"(last status: {batch.processing_status}, {status_line})"
                )

            time.sleep(interval)

    def collect(self, batch_id: str, item_types: dict[str, str]) -> dict[str, BatchResultItem]:
        """Download and parse results for a completed batch.

        Args:
            batch_id: The batch ID to collect results from.
            item_types: Mapping of url_hash → entity_type (needed for parsing).

        Returns:
            Dict mapping url_hash → BatchResultItem.
        """
        results: dict[str, BatchResultItem] = {}

        for entry in self._client.messages.batches.results(batch_id):
            url_hash = entry.custom_id
            entity_type = item_types.get(url_hash, "bullet")

            if entry.result.type == "succeeded":
                message = entry.result.message
                raw_text = message.content[0].text if message.content else ""
                usage = {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                }

                try:
                    extraction_result = self._engine.parse_response(raw_text, entity_type, usage=usage)
                    results[url_hash] = BatchResultItem(
                        url_hash=url_hash,
                        status="succeeded",
                        result=extraction_result,
                        usage=usage,
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse batch result for %s: %s", url_hash, e)
                    results[url_hash] = BatchResultItem(
                        url_hash=url_hash,
                        status="errored",
                        error=f"Parse error: {e}",
                    )

            elif entry.result.type == "errored":
                error_msg = str(entry.result.error) if hasattr(entry.result, "error") else "Unknown error"
                logger.warning("Batch item %s errored: %s", url_hash, error_msg)
                results[url_hash] = BatchResultItem(
                    url_hash=url_hash,
                    status="errored",
                    error=error_msg,
                )

            elif entry.result.type == "expired":
                logger.warning("Batch item %s expired (not processed within 24h)", url_hash)
                results[url_hash] = BatchResultItem(
                    url_hash=url_hash,
                    status="expired",
                    error="Request expired before processing",
                )

            elif entry.result.type == "canceled":
                results[url_hash] = BatchResultItem(
                    url_hash=url_hash,
                    status="canceled",
                    error="Batch was canceled",
                )

        return results

    def run(
        self,
        items: list[BatchItem],
        item_types: dict[str, str] | None = None,
        timeout: float = BATCH_MAX_WAIT_SECONDS,
    ) -> tuple[str, dict[str, BatchResultItem]]:
        """Submit, poll, and collect — full batch lifecycle.

        Args:
            items: List of BatchItems to extract.
            item_types: Optional pre-built url_hash → entity_type mapping.
                If None, built from items.
            timeout: Max seconds to wait for batch completion.

        Returns:
            Tuple of (batch_id, results dict).
        """
        if item_types is None:
            item_types = {item.url_hash: item.entity_type for item in items}

        batch_id = self.submit(items)
        self.poll(batch_id, timeout=timeout)
        results = self.collect(batch_id, item_types)
        return batch_id, results
