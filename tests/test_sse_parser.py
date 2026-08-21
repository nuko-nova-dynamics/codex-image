from __future__ import annotations

import pytest
from sse_parser import (
    ParseError,
    extract_image_b64,
    extract_response_metadata,
    parse_sse_events,
)


def test_parse_events_yields_each_event(fixture_dir):
    raw = (fixture_dir / "sse_completed.txt").read_text()
    events = list(parse_sse_events(raw))
    types = [e["type"] for e in events]
    assert "response.created" in types
    assert "response.output_item.done" in types
    assert "response.completed" in types


def test_extract_prefers_completed_item_over_partial(fixture_dir):
    raw = (fixture_dir / "sse_completed.txt").read_text()
    b64, source = extract_image_b64(raw)
    assert b64 == "RklOQUw="
    assert source == "output_item.done"


def test_extract_falls_back_to_partial_when_no_completed(fixture_dir):
    raw = (fixture_dir / "sse_only_partial.txt").read_text()
    b64, source = extract_image_b64(raw)
    assert b64 == "T05MWVBBUlRJQUw="
    assert source == "partial_image"


def test_extract_rejects_partial_from_incomplete_stream():
    raw = (
        "event: response.created\n"
        'data: {"type":"response.created","response":{"id":"resp_1"}}\n\n'
        "event: response.image_generation_call.partial_image\n"
        'data: {"type":"response.image_generation_call.partial_image",'
        '"partial_image_b64":"VFJVTkNBVEVE","partial_image_index":0}\n\n'
    )
    with pytest.raises(ParseError, match="incomplete stream"):
        extract_image_b64(raw)


def test_extract_raises_on_failure_event(fixture_dir):
    raw = (fixture_dir / "sse_error.txt").read_text()
    with pytest.raises(ParseError, match="rate_limit_exceeded"):
        extract_image_b64(raw)


def test_extract_raises_when_stream_has_no_image():
    raw = "event: response.created\ndata: {}\n\n"
    with pytest.raises(ParseError, match="no image"):
        extract_image_b64(raw)


def test_extract_accepts_result_when_status_is_generating(fixture_dir):
    """Real backend shape: output_item.done carries the result while still
    reporting status='generating', and response.completed.output is empty.
    Observed twice on live streams (2026-08-21)."""
    raw = (fixture_dir / "sse_generating_status.txt").read_text()
    b64, source = extract_image_b64(raw)
    assert b64 == "RklOQUw="
    assert source == "output_item.done"


def test_metadata_captures_image_model_and_resolved_background(fixture_dir):
    """The backend echoes its resolved tool config on the response object.
    We record what it actually used rather than what we asked for."""
    raw = (fixture_dir / "sse_generating_status.txt").read_text()
    meta = extract_response_metadata(raw)
    assert meta["image_model"] == "gpt-image-2-codex"
    assert meta["resolved_background"] == "transparent"
    assert meta["resolved_size"] == "1536x1024"


def test_metadata_omits_image_model_when_backend_sends_none(fixture_dir):
    raw = (fixture_dir / "sse_completed.txt").read_text()
    meta = extract_response_metadata(raw)
    assert meta.get("image_model") is None
    assert meta["resolved_background"] == "opaque"
