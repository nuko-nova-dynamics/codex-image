from __future__ import annotations

from transparency import (
    apply_chroma_key_suffix,
    pick_key_color,
    pillow_available,
    warn_subject_key_conflict,
)


def test_pick_key_color_default_is_green():
    assert pick_key_color("a coffee mug") == "#00ff00"


def test_pick_key_color_green_subject_uses_magenta():
    # Green present, magenta absent → first non-conflicting candidate is magenta.
    assert pick_key_color("a green monstera leaf") == "#ff00ff"
    assert pick_key_color("fresh grass blades") == "#ff00ff"


def test_pick_key_color_magenta_subject_falls_back_to_green():
    # Magenta present, green absent → first non-conflicting candidate is green.
    # (Updated v0.1.1: prior behavior returned cyan, which was inconsistent
    # with the "skip mentioned families in order" rule.)
    assert pick_key_color("pink rose petals") == "#00ff00"
    assert pick_key_color("magenta flower") == "#00ff00"


def test_apply_chroma_key_suffix_appends_template():
    result = apply_chroma_key_suffix("a red mug", "#00ff00")
    assert "a red mug" in result
    assert "#00ff00" in result
    assert "no shadows" in result
    assert "no cast shadow" in result


def test_warn_subject_key_conflict_returns_message_when_overlapping():
    msg = warn_subject_key_conflict("a green frog", "#00ff00")
    assert msg is not None
    assert "green" in msg.lower()


def test_warn_subject_key_conflict_returns_none_for_safe_combo():
    assert warn_subject_key_conflict("a red mug", "#00ff00") is None


def test_pick_key_color_prefers_cyan_when_green_and_magenta_both_in_prompt():
    assert pick_key_color("a green frog with pink flowers") == "#00ffff"


def test_pick_key_color_falls_back_to_green_when_all_families_in_prompt():
    assert pick_key_color("green grass, pink rose, cyan accent") == "#00ff00"


def test_pillow_available_is_bool():
    assert isinstance(pillow_available(), bool)


def test_native_suffix_preserves_terminal_punctuation():
    """The docstring promises nothing is stripped or rewritten."""
    from transparency import NATIVE_TRANSPARENCY_SUFFIX, apply_native_transparency_suffix

    assert apply_native_transparency_suffix("a red mug") == (
        f"a red mug. {NATIVE_TRANSPARENCY_SUFFIX}"
    )
    assert apply_native_transparency_suffix("a red mug.") == (
        f"a red mug. {NATIVE_TRANSPARENCY_SUFFIX}"
    )
    # A question mark must survive, and must not gain a stray period.
    assert apply_native_transparency_suffix("what if a mug?") == (
        f"what if a mug? {NATIVE_TRANSPARENCY_SUFFIX}"
    )
    # Abbreviations must not be truncated.
    assert apply_native_transparency_suffix("a flag of the U.S.A.").startswith(
        "a flag of the U.S.A."
    )
