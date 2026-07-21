"""SSE stream parser for the Codex Responses API.

Spec §4: consume the FULL stream, then pick the highest-priority result.
Never short-circuit on the first match — partial frames arrive first.
"""
from __future__ import annotations

import json
from collections.abc import Iterator


class ParseError(Exception):
    """Raised when the SSE stream contains no usable image."""


def parse_sse_events(raw: str) -> Iterator[dict]:
    """Yield parsed JSON payloads from each SSE block.

    Skips blocks that don't have a data: line or whose payload isn't JSON.
    """
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        data_line = None
        for line in block.splitlines():
            if line.startswith("data: "):
                data_line = line[len("data: "):]
                break
        if not data_line:
            continue
        try:
            yield json.loads(data_line)
        except json.JSONDecodeError:
            continue


def extract_image_b64(raw: str) -> tuple[str, str]:
    """Walk the full stream, accumulate candidates, return (b64, source_name).

    Priority (per spec §4):
    1. response.output_item.done with image_generation_call (status: completed)
    2. response.completed.response.output[*] for image_generation_call
    3. last response.image_generation_call.partial_image — only if 1 & 2 are
       missing and the stream includes response.completed

    Raises ParseError on response.failed, missing image, or invalid stream.
    """
    final_from_item_done: str | None = None
    final_from_response_completed: str | None = None
    last_partial: str | None = None
    failure_message: str | None = None
    saw_response_completed = False

    for ev in parse_sse_events(raw):
        ev_type = ev.get("type", "")
        if ev_type == "response.failed":
            err = (ev.get("response") or {}).get("error") or {}
            code = err.get("code", "unknown")
            msg = err.get("message", "")
            failure_message = f"{code}: {msg}".strip(": ")
        elif ev_type == "response.output_item.done":
            item = ev.get("item") or {}
            if item.get("type") == "image_generation_call" and item.get("status") == "completed":
                if result := item.get("result"):
                    final_from_item_done = result
        elif ev_type == "response.completed":
            saw_response_completed = True
            outputs = (ev.get("response") or {}).get("output") or []
            for item in outputs:
                if item.get("type") == "image_generation_call":
                    if result := item.get("result"):
                        final_from_response_completed = result
        elif ev_type == "response.image_generation_call.partial_image":
            if frame := ev.get("partial_image_b64"):
                last_partial = frame

    if failure_message:
        raise ParseError(f"backend reported failure: {failure_message}")

    if final_from_item_done:
        return final_from_item_done, "output_item.done"
    if final_from_response_completed:
        return final_from_response_completed, "response.completed"
    if last_partial:
        if saw_response_completed:
            return last_partial, "partial_image"
        raise ParseError(
            "incomplete stream: ended before response.completed; partial image was not saved"
        )

    raise ParseError("stream ended with no image_generation_call result")


def extract_response_metadata(raw: str) -> dict:
    """Pull useful diagnostic fields from the stream (revised_prompt, response_id, usage)."""
    meta: dict = {}
    for ev in parse_sse_events(raw):
        ev_type = ev.get("type", "")
        if ev_type == "response.created":
            resp = ev.get("response") or {}
            meta["response_id"] = resp.get("id")
        elif ev_type == "response.output_item.done":
            item = ev.get("item") or {}
            if item.get("type") == "image_generation_call":
                meta["revised_prompt"] = item.get("revised_prompt") or ""
                meta["resolved_quality"] = item.get("quality")
                meta["resolved_size"] = item.get("size")
        elif ev_type == "response.completed":
            resp = ev.get("response") or {}
            meta["usage"] = resp.get("usage")
            meta["tool_usage"] = resp.get("tool_usage")
    return meta
