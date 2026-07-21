from __future__ import annotations

from datetime import datetime, timezone

from naming import (
    output_filename,
    resolve_collision,
    slugify,
)


def test_slugify_basic():
    assert slugify("a yellow taxi at night in rain") == "a-yellow-taxi-at-night-in"


def test_slugify_takes_first_six_words():
    assert slugify("one two three four five six seven eight") == "one-two-three-four-five-six"


def test_slugify_strips_punctuation():
    assert slugify("hello, world! make it bigger?") == "hello-world-make-it-bigger"


def test_slugify_truncates_at_40():
    long = "supercalifragilisticexpialidocious " * 3
    result = slugify(long)
    assert len(result) <= 40
    assert not result.endswith("-")


def test_slugify_empty_when_only_punctuation():
    assert slugify("!!! ??? ...") == "image"


def test_slugify_empty_when_only_emoji():
    assert slugify("🎨🖼️🌅") == "image"


def test_slugify_handles_unicode():
    # Non-ASCII letters get stripped → empty → fallback
    assert slugify("café résumé") == "image"


def test_output_filename_includes_utc_timestamp():
    fixed = datetime(2026, 5, 4, 13, 5, tzinfo=timezone.utc)
    name = output_filename("a coffee mug", "png", now=fixed)
    assert name == "2026-05-04-1305-a-coffee-mug.png"


def test_output_filename_uses_correct_extension():
    fixed = datetime(2026, 5, 4, 13, 5, tzinfo=timezone.utc)
    assert output_filename("x", "jpeg", now=fixed).endswith(".jpg")
    assert output_filename("x", "webp", now=fixed).endswith(".webp")


def test_resolve_collision_returns_path_when_no_conflict(tmp_path):
    path = tmp_path / "2026-05-04-1305-mug.png"
    assert resolve_collision(path) == path


def test_resolve_collision_appends_suffix_2(tmp_path):
    base = tmp_path / "2026-05-04-1305-mug.png"
    base.touch()
    assert resolve_collision(base) == tmp_path / "2026-05-04-1305-mug-2.png"


def test_resolve_collision_walks_through_suffixes(tmp_path):
    base = tmp_path / "2026-05-04-1305-mug.png"
    base.touch()
    (tmp_path / "2026-05-04-1305-mug-2.png").touch()
    (tmp_path / "2026-05-04-1305-mug-3.png").touch()
    assert resolve_collision(base) == tmp_path / "2026-05-04-1305-mug-4.png"
